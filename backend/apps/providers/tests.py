import json
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import Account
from utils.crypto import decrypt_value, encrypt_value
from .auth_sessions import AuthorizationSessionStore
from .clients.midea_cloud.client import MideaCloudClient
from .clients.midea_cloud.lua_codec import MideaLuaCodec, ensure_lua_support_files, lua_runtime_available
from .clients.midea_cloud.mappings import UPSTREAM_MAPPING_ROOT, audit_device_mapping, get_device_mapping
from .models import PlatformAuth
from .services import HomeAssistantAuthService, MbApi2020AuthService, MideaCloudAuthService, MijiaAuthService
from .clients.mbapi2020.client import MbApi2020Client


class PlatformAuthAPITest(TestCase):
    def setUp(self):
        AuthorizationSessionStore.reset()
        self.client = Client()
        self.account = Account.objects.create(
            email="provider-test@example.com",
            name="Provider Test",
            password="pwd",
        )
        self.auth_headers = {"HTTP_X_WANNY_EMAIL": self.account.email}
        self.url = reverse('providers:platform_auth_upsert')
        self.detail_url = lambda platform_name: reverse('providers:platform_auth_detail', args=[platform_name])
        self.login_url = lambda platform_name: reverse('providers:platform_auth_login', args=[platform_name])
        self.authorize_url = lambda platform_name: reverse('providers:platform_auth_authorize', args=[platform_name])

    def test_upsert_platform_auth(self):
        payload = {
            "platform": "wechat",
            "payload": {
                "access_token": "mock-token-123",
                "uid": "1111",
            },
        }

        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(PlatformAuth.objects.count(), 1)

        auth_obj = PlatformAuth.objects.first()
        self.assertEqual(auth_obj.account, self.account)
        self.assertEqual(auth_obj.platform_name, "wechat")
        self.assertEqual(auth_obj.auth_payload['access_token'], "mock-token-123")
        self.assertEqual(response.json()["provider"]["status"], "connected")

    def test_missing_platform_name(self):
        response = self.client.post(
            self.url,
            data=json.dumps({"payload": {}}),
            content_type="application/json",
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(PlatformAuth.objects.count(), 0)

    def test_list_platform_auths_includes_supported_platforms_and_masks_sensitive_payload(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="wechat",
            auth_payload={
                "access_token": "mock-token-123",
                "refresh_token": "refresh-token-456",
                "wxid": "wxid_edison",
            },
            is_active=True,
        )

        response = self.client.get(self.url, **self.auth_headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")

        providers = {provider["platform"]: provider for provider in payload["providers"]}
        self.assertIn("wechat", providers)
        self.assertIn("mijia", providers)
        self.assertIn("home_assistant", providers)
        self.assertIn("midea_cloud", providers)
        self.assertIn("mbapi2020", providers)
        self.assertEqual(providers["wechat"]["status"], "connected")
        self.assertTrue(providers["wechat"]["configured"])
        self.assertNotEqual(
            providers["wechat"]["payload_preview"]["access_token"],
            "mock-token-123",
        )
        self.assertEqual(providers["mijia"]["status"], "not_connected")
        self.assertFalse(providers["mijia"]["configured"])

    def test_get_mijia_platform_detail_returns_supported_placeholder_when_not_configured(self):
        response = self.client.get(self.detail_url("mijia"), **self.auth_headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()["provider"]
        self.assertEqual(payload["platform"], "mijia")
        self.assertEqual(payload["display_name_zh"], "米家")
        self.assertEqual(payload["status"], "not_connected")
        self.assertFalse(payload["configured"])

    def test_get_xiaomi_alias_returns_mijia_platform_detail(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="mijia",
            auth_payload={"serviceToken": "mi-token-123"},
            is_active=True,
        )

        response = self.client.get(self.detail_url("xiaomi"), **self.auth_headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()["provider"]
        self.assertEqual(payload["platform"], "mijia")
        self.assertEqual(payload["display_name_zh"], "米家")
        self.assertEqual(payload["status"], "connected")

    def test_upsert_mijia_platform_auth(self):
        payload = {
            "platform": "mijia",
            "payload": {
                "access_token": "mi-token-123",
                "user_id": "mijia-user-1",
            },
        }

        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        auth_obj = PlatformAuth.objects.get(account=self.account, platform_name="mijia")
        self.assertEqual(auth_obj.auth_payload["access_token"], "mi-token-123")
        self.assertEqual(response.json()["provider"]["status"], "connected")

    def test_upsert_xiaomi_alias_stores_mijia_platform_auth(self):
        payload = {
            "platform": "xiaomi",
            "payload": {
                "serviceToken": "mi-token-456",
                "userId": "mijia-user-2",
            },
        }

        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(PlatformAuth.objects.filter(account=self.account, platform_name="mijia").count(), 1)
        self.assertEqual(PlatformAuth.objects.filter(platform_name="xiaomi").count(), 0)
        auth_obj = PlatformAuth.objects.get(account=self.account, platform_name="mijia")
        self.assertEqual(auth_obj.auth_payload["serviceToken"], "mi-token-456")
        self.assertEqual(response.json()["provider"]["platform"], "mijia")

    def test_patch_platform_auth_merges_payload_and_updates_active(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="wechat",
            auth_payload={"access_token": "mock-token-123"},
            is_active=True,
        )

        response = self.client.patch(
            self.detail_url("wechat"),
            data=json.dumps(
                {
                    "payload": {"wxid": "wxid_edison"},
                    "is_active": False,
                }
            ),
            content_type="application/json",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        auth_obj = PlatformAuth.objects.get(account=self.account, platform_name="wechat")
        self.assertFalse(auth_obj.is_active)
        self.assertEqual(auth_obj.auth_payload["access_token"], "mock-token-123")
        self.assertEqual(auth_obj.auth_payload["wxid"], "wxid_edison")
        self.assertEqual(response.json()["provider"]["status"], "disabled")

    def test_delete_platform_auth_removes_record(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="wechat",
            auth_payload={"access_token": "mock-token-123"},
            is_active=True,
        )

        response = self.client.delete(self.detail_url("wechat"), **self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(PlatformAuth.objects.count(), 0)

    def test_mijia_login_endpoint_returns_provider_from_service(self):
        auth_obj = PlatformAuth.objects.create(
            account=self.account,
            platform_name="mijia",
            auth_payload={"serviceToken": "mi-token-123", "userId": "mijia-user-1"},
            is_active=True,
        )

        with patch("providers.views.MijiaAuthService.login_and_store", return_value=auth_obj):
            response = self.client.post(self.login_url("mijia"), **self.auth_headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["provider"]["platform"], "mijia")
        self.assertEqual(payload["provider"]["status"], "connected")

    def test_authorize_wechat_endpoint_returns_pending_session(self):
        with patch("providers.views.WeChatAuthorizationService.start_session") as mocked_start:
            mocked_start.return_value = AuthorizationSessionStore.create(
                platform="wechat",
                auth_kind="link",
                status="pending",
                title="微信授权进行中",
                instruction="请打开授权链接。",
                detail="等待扫码确认。",
                action_url="https://wechat.example/qr",
            )

            response = self.client.post(
                self.authorize_url("wechat"),
                data=json.dumps({"force": True}),
                content_type="application/json",
                **self.auth_headers,
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["session"]["platform"], "wechat")
        self.assertEqual(payload["session"]["status"], "pending")
        self.assertEqual(payload["session"]["auth_kind"], "link")

    def test_authorize_mijia_endpoint_returns_pending_qr_session(self):
        with patch("providers.views.MijiaAuthorizationService.start_session") as mocked_start:
            mocked_start.return_value = AuthorizationSessionStore.create(
                platform="mijia",
                auth_kind="qr",
                status="pending",
                title="米家授权进行中",
                instruction="请扫描二维码。",
                detail="等待米家 App 确认。",
                image_url="https://mijia.example/qr.png",
                verification_url="https://mijia.example/login",
            )

            response = self.client.post(
                self.authorize_url("mijia"),
                data=json.dumps({}),
                content_type="application/json",
                **self.auth_headers,
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["session"]["platform"], "mijia")
        self.assertEqual(payload["session"]["auth_kind"], "qr")
        self.assertEqual(payload["session"]["image_url"], "https://mijia.example/qr.png")

    def test_authorize_home_assistant_endpoint_validates_and_stores_payload(self):
        auth_obj = PlatformAuth.objects.create(
            account=self.account,
            platform_name="home_assistant",
            auth_payload={
                "base_url": "http://ha.local:8123",
                "access_token": "ha-token",
                "instance_name": "My HA",
            },
            is_active=True,
        )

        with patch("providers.views.HomeAssistantAuthService.validate_and_store", return_value=auth_obj):
            response = self.client.post(
                self.authorize_url("ha"),
                data=json.dumps(
                    {
                        "payload": {
                            "base_url": "http://ha.local:8123",
                            "access_token": "ha-token",
                        }
                    }
                ),
                content_type="application/json",
                **self.auth_headers,
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["provider"]["platform"], "home_assistant")
        self.assertEqual(payload["session"]["auth_kind"], "form")
        self.assertEqual(payload["session"]["status"], "completed")

    def test_authorize_midea_cloud_endpoint_validates_and_stores_payload(self):
        auth_obj = PlatformAuth.objects.create(
            account=self.account,
            platform_name="midea_cloud",
            auth_payload={
                "account": "demo@example.com",
                "access_token": "midea-token",
                "instance_name": "Midea",
            },
            is_active=True,
        )

        with patch("providers.views.MideaCloudAuthService.validate_and_store", return_value=auth_obj):
            response = self.client.post(
                self.authorize_url("midea"),
                data=json.dumps(
                    {
                        "payload": {
                            "account": "demo@example.com",
                            "access_token": "midea-token",
                        }
                    }
                ),
                content_type="application/json",
                **self.auth_headers,
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["provider"]["platform"], "midea_cloud")
        self.assertEqual(payload["session"]["auth_kind"], "form")
        self.assertEqual(payload["session"]["status"], "completed")

    def test_authorize_midea_cloud_endpoint_persists_account_password_payload(self):
        with patch.object(
            MideaCloudClient,
            "get_account_profile",
            return_value={
                "account": "demo@example.com",
                "api_base": "https://midea.example.com",
                "server_name": "美的美居",
                "nickname": "Edison",
                "homes": [{"id": "1001", "name": "我的家"}],
                "auth_state": {
                    "server": 2,
                    "server_name": "美的美居",
                    "api_base": "https://midea.example.com",
                    "device_id": "device-123",
                    "access_token": "midea-token",
                },
            },
        ), patch("devices.services.DeviceDashboardService.sync_after_provider_change") as mocked_sync:
            response = self.client.post(
                self.authorize_url("midea"),
                data=json.dumps(
                    {
                        "payload": {
                            "username": "demo@example.com",
                            "password": "secret",
                            "server": "美的美居",
                            "base_url": "https://midea.example.com/",
                        }
                    }
                ),
                content_type="application/json",
                **self.auth_headers,
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["provider"]["platform"], "midea_cloud")
        self.assertEqual(payload["provider"]["status"], "connected")
        self.assertEqual(payload["session"]["status"], "completed")
        mocked_sync.assert_called_once_with(self.account, trigger="connect_midea_cloud")

        auth_obj = PlatformAuth.objects.get(account=self.account, platform_name="midea_cloud")
        self.assertEqual(auth_obj.auth_payload["account"], "demo@example.com")
        self.assertNotEqual(auth_obj.auth_payload["password"], "secret")
        self.assertEqual(decrypt_value(auth_obj.auth_payload["password"]), "secret")
        self.assertEqual(auth_obj.auth_payload["server"], 2)
        self.assertEqual(auth_obj.auth_payload["api_base"], "https://midea.example.com")
        self.assertEqual(auth_obj.auth_payload["access_token"], "midea-token")
        self.assertEqual(auth_obj.auth_payload["instance_name"], "Midea (美的美居)")

    def test_authorize_midea_cloud_endpoint_masks_password_in_provider_preview(self):
        with patch.object(
            MideaCloudClient,
            "get_account_profile",
            return_value={
                "account": "demo@example.com",
                "api_base": "https://midea.example.com",
                "server_name": "美的美居",
                "nickname": "Edison",
                "homes": [],
                "auth_state": {
                    "server": 2,
                    "server_name": "美的美居",
                    "api_base": "https://midea.example.com",
                    "access_token": "midea-token",
                },
            },
        ), patch("devices.services.DeviceDashboardService.sync_after_provider_change"):
            self.client.post(
                self.authorize_url("midea"),
                data=json.dumps(
                    {
                        "payload": {
                            "account": "demo@example.com",
                            "password": "secret",
                            "server": 2,
                        }
                    }
                ),
                content_type="application/json",
                **self.auth_headers,
            )

        detail_response = self.client.get(self.detail_url("midea"), **self.auth_headers)
        self.assertEqual(detail_response.status_code, 200)
        provider = detail_response.json()["provider"]
        self.assertEqual(provider["platform"], "midea_cloud")
        self.assertNotEqual(provider["payload_preview"]["password"], "secret")
        self.assertEqual(provider["payload_preview"]["password"], "se***et")

    def test_authorize_mbapi2020_endpoint_validates_and_stores_payload(self):
        auth_obj = PlatformAuth.objects.create(
            account=self.account,
            platform_name="mbapi2020",
            auth_payload={
                "account": "driver@example.com",
                "access_token": "mb-token",
                "instance_name": "Mercedes-Benz (Europe)",
            },
            is_active=True,
        )

        with patch("providers.views.MbApi2020AuthService.validate_and_store", return_value=auth_obj), patch(
            "devices.services.DeviceDashboardService.sync_after_provider_change"
        ) as mocked_sync:
            response = self.client.post(
                self.authorize_url("mercedes"),
                data=json.dumps(
                    {
                        "payload": {
                            "account": "driver@example.com",
                            "access_token": "mb-token",
                            "region": "Europe",
                        }
                    }
                ),
                content_type="application/json",
                **self.auth_headers,
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["provider"]["platform"], "mbapi2020")
        self.assertEqual(payload["session"]["auth_kind"], "form")
        self.assertEqual(payload["session"]["status"], "completed")
        mocked_sync.assert_called_once_with(self.account, trigger="connect_mbapi2020")

    def test_authorize_get_returns_latest_session_for_platform(self):
        AuthorizationSessionStore.create(
            platform="wechat",
            auth_kind="link",
            status="scanned",
            title="微信授权进行中",
            instruction="请在微信中确认。",
            detail="二维码已扫描。",
            action_url="https://wechat.example/qr",
        )

        response = self.client.get(self.authorize_url("wechat"), **self.auth_headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["session"]["status"], "scanned")
        self.assertEqual(payload["session"]["platform"], "wechat")


class MijiaAuthServiceTest(TestCase):
    def setUp(self):
        AuthorizationSessionStore.reset()
        self.account = Account.objects.create(
            email="mijia-test@example.com",
            name="Mijia Test",
            password="pwd",
        )

    def test_write_auth_file_from_db_loads_active_mijia_payload(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="mijia",
            auth_payload={"serviceToken": "mi-token-123", "userId": "mijia-user-1"},
            is_active=True,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            auth_file = Path(temp_dir) / "auth.json"
            MijiaAuthService.write_auth_file_from_db(account=self.account, auth_file_path=auth_file)

            with open(auth_file, "r", encoding="utf-8") as f:
                payload = json.load(f)

        self.assertEqual(payload["serviceToken"], "mi-token-123")
        self.assertEqual(payload["userId"], "mijia-user-1")

    def test_login_and_store_persists_mijia_api_auth_payload_to_platform_auth(self):
        class FakeMijiaAPI:
            def __init__(self, auth_data_path):
                self.auth_data_path = auth_data_path
                self.auth_data = {}

            def login(self):
                self.auth_data = {
                    "serviceToken": "mi-token-123",
                    "userId": "mijia-user-1",
                    "cUserId": "c-user-1",
                }
                with open(self.auth_data_path, "w", encoding="utf-8") as f:
                    json.dump(self.auth_data, f)
                return self.auth_data

        with tempfile.TemporaryDirectory() as temp_dir:
            auth_file = Path(temp_dir) / "auth.json"
            with patch("providers.services.mijiaAPI", FakeMijiaAPI):
                auth_obj = MijiaAuthService.login_and_store(self.account, auth_file)

        self.assertEqual(auth_obj.platform_name, "mijia")
        self.assertTrue(auth_obj.is_active)
        self.assertEqual(auth_obj.account, self.account)
        self.assertEqual(auth_obj.auth_payload["serviceToken"], "mi-token-123")


class HomeAssistantAuthServiceTest(TestCase):
    def setUp(self):
        self.account = Account.objects.create(
            email="ha-test@example.com",
            name="HA Test",
            password="pwd",
        )

    def test_validate_and_store_persists_home_assistant_payload(self):
        class FakeResponse:
            def __init__(self, payload, headers=None):
                self._payload = payload
                self.headers = headers or {}

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        with patch(
            "providers.services.requests.get",
            side_effect=[
                FakeResponse({"message": "API running."}, headers={"X-HA-Version": "2026.3.0"}),
                FakeResponse({"location_name": "My Home", "time_zone": "Asia/Shanghai", "unit_system": {"temperature": "C"}}),
            ],
        ):
            auth_obj = HomeAssistantAuthService.validate_and_store(
                self.account,
                {
                    "base_url": "http://ha.local:8123/",
                    "access_token": "ha-token",
                },
            )

        self.assertEqual(auth_obj.platform_name, "home_assistant")
        self.assertEqual(auth_obj.auth_payload["base_url"], "http://ha.local:8123")
        self.assertEqual(auth_obj.auth_payload["instance_name"], "My Home")
        self.assertEqual(auth_obj.auth_payload["version"], "2026.3.0")

    def test_get_graph_returns_registry_payload(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="home_assistant",
            auth_payload={
                "base_url": "http://ha.local:8123",
                "access_token": "ha-token",
            },
            is_active=True,
        )

        registry_payload = {
            "areas": [{"area_id": "kitchen", "name": "厨房"}],
            "devices": [{"id": "device-fridge", "area_id": "kitchen", "name": "多开门冰箱"}],
            "entities": [{"entity_id": "sensor.fridge_cold", "device_id": "device-fridge"}],
        }
        with patch.object(
            HomeAssistantAuthService,
            "get_states",
            return_value=(
                {"location_name": "My Home"},
                [{"entity_id": "sensor.fridge_cold", "state": "4", "attributes": {}}],
            ),
        ), patch.object(
            HomeAssistantAuthService,
            "_fetch_registry_via_websocket",
            new=AsyncMock(return_value=registry_payload),
        ):
            config, states, registry = HomeAssistantAuthService.get_graph(self.account)

        self.assertEqual(config["location_name"], "My Home")
        self.assertEqual(states[0]["entity_id"], "sensor.fridge_cold")
        self.assertEqual(registry["areas"][0]["name"], "厨房")


class MideaCloudAuthServiceTest(TestCase):
    def setUp(self):
        self.account = Account.objects.create(
            email="midea-cloud-test@example.com",
            name="Midea Test",
            password="pwd",
        )

    def test_validate_and_store_normalizes_alias_fields(self):
        with patch.object(MideaCloudClient, "get_account_profile", return_value={
                "account": "demo@example.com",
                "api_base": "https://midea.example.com",
                "server_name": "美的美居",
                "nickname": "Edison",
                "homes": [{"id": "1001", "name": "我的家"}],
                "auth_state": {
                    "server": 2,
                    "server_name": "美的美居",
                    "api_base": "https://midea.example.com",
                    "device_id": "device-123",
                    "access_token": "midea-token",
                },
            }):
            auth_obj = MideaCloudAuthService.validate_and_store(
                self.account,
                {
                    "username": "demo@example.com",
                    "password": "secret",
                    "base_url": "https://midea.example.com/",
                },
            )

        self.assertEqual(auth_obj.platform_name, "midea_cloud")
        self.assertEqual(auth_obj.auth_payload["account"], "demo@example.com")
        self.assertEqual(auth_obj.auth_payload["access_token"], "midea-token")
        self.assertEqual(auth_obj.auth_payload["api_base"], "https://midea.example.com")
        self.assertEqual(auth_obj.auth_payload["nickname"], "Edison")
        self.assertEqual(auth_obj.auth_payload["homes"][0]["id"], "1001")
        self.assertNotEqual(auth_obj.auth_payload["password"], "secret")
        self.assertEqual(decrypt_value(auth_obj.auth_payload["password"]), "secret")

    def test_get_client_decrypts_stored_password(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="midea_cloud",
            auth_payload={
                "account": "demo@example.com",
                "password": encrypt_value("secret"),
                "server": 2,
                "api_base": "https://midea.example.com",
            },
            is_active=True,
        )
        client = MideaCloudAuthService.get_client(self.account)

        self.assertEqual(client.payload["password"], "secret")


class MbApi2020AuthServiceTest(TestCase):
    def setUp(self):
        self.account = Account.objects.create(
            email="mbapi-test@example.com",
            name="MB Test",
            password="pwd",
        )

    def test_validate_and_store_persists_profile_and_tokens(self):
        with patch.object(MbApi2020Client, "get_account_profile", return_value={
                "account": "driver@example.com",
                "api_base": "https://bff.emea-prod.mobilesdk.mercedes-benz.com",
                "region": "Europe",
                "locale": "en-GB",
                "nickname": "Driver",
                "vehicles": [{"vin": "W1N123", "name": "E 300"}],
                "auth_state": {
                    "access_token": "mb-token",
                    "refresh_token": "mb-refresh",
                    "region": "Europe",
                    "api_base": "https://bff.emea-prod.mobilesdk.mercedes-benz.com",
                    "locale": "en-GB",
                },
            }):
            auth_obj = MbApi2020AuthService.validate_and_store(
                self.account,
                {
                    "account": "driver@example.com",
                    "access_token": "mb-token",
                    "refresh_token": "mb-refresh",
                    "region": "eu",
                },
            )

        self.assertEqual(auth_obj.platform_name, "mbapi2020")
        self.assertEqual(auth_obj.auth_payload["account"], "driver@example.com")
        self.assertEqual(auth_obj.auth_payload["access_token"], "mb-token")
        self.assertEqual(auth_obj.auth_payload["refresh_token"], "mb-refresh")
        self.assertEqual(auth_obj.auth_payload["region"], "Europe")
        self.assertEqual(auth_obj.auth_payload["vehicles"][0]["vin"], "W1N123")

    def test_get_client_reads_active_payload(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="mbapi2020",
            auth_payload={
                "account": "driver@example.com",
                "access_token": "mb-token",
                "region": "Europe",
            },
            is_active=True,
        )

        client = MbApi2020AuthService.get_client(self.account)
        self.assertEqual(client.payload["access_token"], "mb-token")
        self.assertEqual(client.payload["region"], "Europe")

    def test_get_client_persists_refreshed_token_state(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="mbapi2020",
            auth_payload={
                "account": "driver@example.com",
                "access_token": "expired-token",
                "refresh_token": "refresh-token",
                "region": "Europe",
                "expires_at": 1,
                "device_guid": "device-guid-1",
            },
            is_active=True,
        )

        client = MbApi2020AuthService.get_client(self.account)

        with patch.object(client.session, "get") as mocked_get, patch.object(client.session, "post") as mocked_post:
            mocked_get.return_value.raise_for_status.return_value = None
            mocked_post.return_value.raise_for_status.return_value = None
            mocked_post.return_value.json.return_value = {
                "access_token": "new-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600,
            }

            token = client._ensure_access_token()

        self.assertEqual(token, "new-token")
        auth_obj = PlatformAuth.objects.get(account=self.account, platform_name="mbapi2020")
        self.assertEqual(auth_obj.auth_payload["access_token"], "new-token")
        self.assertEqual(auth_obj.auth_payload["refresh_token"], "new-refresh-token")
        self.assertEqual(auth_obj.auth_payload["device_guid"], "device-guid-1")


class MbApi2020ClientTest(TestCase):
    def test_validate_payload_requires_access_token(self):
        with self.assertRaises(ValueError):
            MbApi2020Client.validate_payload({"region": "Europe"})

    def test_validate_payload_normalizes_region_alias_and_expires_in(self):
        payload = MbApi2020Client.validate_payload(
            {
                "access_token": "mb-token",
                "region": "eu",
                "expires_in": 3600,
            }
        )

        self.assertEqual(payload["region"], "Europe")
        self.assertGreater(payload["expires_at"], int(time.time()))

    def test_get_account_profile_uses_user_and_vehicle_endpoints(self):
        client = MbApi2020Client(
            {
                "account": "driver@example.com",
                "access_token": "mb-token",
                "region": "Europe",
            }
        )

        with patch.object(
            client,
            "_request_json",
            side_effect=[
                {"email": "driver@example.com", "firstName": "Edison"},
                {"items": [{"vin": "W1N123", "modelName": "EQE", "licensePlate": "沪A12345"}]},
            ],
        ):
            profile = client.get_account_profile()

        self.assertEqual(profile["account"], "driver@example.com")
        self.assertEqual(profile["nickname"], "Edison")
        self.assertEqual(profile["vehicles"][0]["vin"], "W1N123")
        self.assertEqual(profile["vehicles"][0]["model"], "EQE")

    def test_extract_vehicle_list_supports_assigned_vehicles_shape(self):
        items = MbApi2020Client._extract_vehicle_list(
            {
                "assignedVehicles": [
                    {"vin": "W1N123", "licensePlate": "沪A12345"},
                ]
            }
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["vin"], "W1N123")

    def test_list_devices_enriches_vehicle_with_status_and_command_capabilities(self):
        client = MbApi2020Client(
            {
                "account": "driver@example.com",
                "access_token": "mb-token",
                "region": "China",
                "pin": "1234",
            }
        )

        with patch.object(client, "list_vehicles", return_value=[{"vin": "W1N123", "name": "EQE"}]), patch.object(
            client,
            "get_vehicle_capabilities",
            return_value={"vehicle": {"modelName": "EQE"}, "features": {"DOORS_LOCK": True}},
        ), patch.object(
            client,
            "get_vehicle_command_capabilities",
            return_value={"commands": [{"commandName": "DOORS_LOCK", "isAvailable": True}]},
        ), patch.object(
            client,
            "get_vehicle_status",
            return_value={"status_payload": {"doorlockstatusvehicle": "locked"}},
        ):
            devices = client.list_devices()

        self.assertEqual(devices[0]["vin"], "W1N123")
        self.assertEqual(devices[0]["region"], "China")
        self.assertTrue(devices[0]["pin_available"])
        self.assertEqual(devices[0]["status_payload"]["doorlockstatusvehicle"], "locked")

    def test_execute_control_builds_and_sends_supported_command(self):
        client = MbApi2020Client(
            {
                "account": "driver@example.com",
                "access_token": "mb-token",
                "region": "China",
            }
        )

        with patch.object(client, "_build_command_message", return_value=b"payload") as mocked_build, patch.object(
            client,
            "_send_command_over_websocket",
            new_callable=AsyncMock,
        ) as mocked_send:
            client.execute_control(
                vehicle_id="W1N123",
                control={
                    "key": "door_lock",
                    "action_params": {"command_name": "DOORS_LOCK"},
                },
            )

        mocked_build.assert_called_once_with("W1N123", "DOORS_LOCK", pin="")
        mocked_send.assert_awaited_once_with(b"payload")

    def test_refresh_access_token_runs_preflight_and_updates_headers(self):
        client = MbApi2020Client(
            {
                "account": "driver@example.com",
                "access_token": "expired-token",
                "refresh_token": "refresh-token",
                "region": "Europe",
                "expires_at": 1,
                "device_guid": "device-guid-1",
            }
        )

        with patch.object(client.session, "get") as mocked_get, patch.object(client.session, "post") as mocked_post:
            mocked_get.return_value.raise_for_status.return_value = None
            mocked_post.return_value.raise_for_status.return_value = None
            mocked_post.return_value.json.return_value = {
                "access_token": "new-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 1800,
            }

            token = client._ensure_access_token()

        self.assertEqual(token, "new-token")
        mocked_get.assert_called_once()
        self.assertIn("/v1/config", mocked_get.call_args.args[0])
        self.assertEqual(mocked_post.call_args.kwargs["headers"]["X-Device-Id"], "device-guid-1")
        self.assertEqual(client.payload["refresh_token"], "new-refresh-token")
        self.assertGreater(client.payload["expires_at"], int(time.time()))


class MideaCloudClientTest(TestCase):
    def test_validate_payload_requires_password_without_token(self):
        with self.assertRaises(ValueError):
            MideaCloudClient.validate_payload(
                {
                    "account": "demo@example.com",
                    "server": 2,
                }
            )

    def test_get_account_profile_uses_cloud_login_and_home_listing(self):
        client = MideaCloudClient(
            {
                "account": "demo@example.com",
                "password": "secret",
                "server": 2,
            }
        )

        with patch.object(client.cloud_api, "login", return_value=True) as mocked_login, patch.object(
            client.cloud_api,
            "list_homes",
            return_value={"1001": "我的家", "1002": "父母家"},
        ):
            profile = client.get_account_profile()

        mocked_login.assert_called_once()
        self.assertEqual(profile["server_name"], "美的美居")
        self.assertEqual(profile["homes"][0]["id"], "1001")
        self.assertEqual(profile["homes"][1]["name"], "父母家")

    def test_list_devices_enriches_status_payload(self):
        client = MideaCloudClient(
            {
                "account": "demo@example.com",
                "password": "secret",
                "server": 2,
                "selected_homes": ["1001"],
            }
        )

        with patch.object(client.cloud_api, "login", return_value=True), patch.object(
            client.cloud_api,
            "list_homes",
            return_value={"1001": "我的家"},
        ), patch.object(
            client.cloud_api,
            "list_appliances",
            return_value={
                998877: {
                    "name": "客厅空调",
                    "type": 0xAC,
                    "sn": "123456789ABCDEFG",
                    "sn8": "9ABCDEFG",
                    "category": "air_conditioner",
                    "smart_product_id": "sp-1",
                    "model_number": "KFR-35GW",
                    "manufacturer_code": "0000",
                    "model": "9ABCDEFG",
                    "online": True,
                    "home_name": "我的家",
                    "room_name": "客厅",
                    "home_id": "1001",
                }
            },
        ), patch.object(
            client.cloud_api,
            "get_device_status",
            return_value={"power": "on", "target_temperature": 24},
        ):
            devices = client.list_devices()

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["id"], "998877")
        self.assertEqual(devices[0]["room_name"], "客厅")
        self.assertEqual(devices[0]["status_payload"]["power"], "on")
        self.assertIn("_meta", devices[0]["status_payload"])

    def test_list_devices_uses_mapping_queries_and_downloads_lua(self):
        client = MideaCloudClient(
            {
                "account": "demo@example.com",
                "password": "secret",
                "server": 2,
                "selected_homes": ["1001"],
            }
        )

        with patch.object(client.cloud_api, "login", return_value=True), patch.object(
            client.cloud_api,
            "list_homes",
            return_value={"1001": "我的家"},
        ), patch.object(
            client.cloud_api,
            "list_appliances",
            return_value={
                998877: {
                    "name": "客厅空调",
                    "type": 0xAC,
                    "sn": "123456789ABCDEFG",
                    "sn8": "9ABCDEFG",
                    "category": "wall-air-conditioner",
                    "smart_product_id": "sp-1",
                    "model_number": "KFR-35GW",
                    "manufacturer_code": "0000",
                    "model": "9ABCDEFG",
                    "online": True,
                    "home_name": "我的家",
                    "room_name": "客厅",
                    "home_id": "1001",
                }
            },
        ), patch.object(
            client.cloud_api,
            "get_device_status",
            side_effect=[
                {"power": "on"},
                {"indoor_humidity": 51},
                {"indoor_temperature": 27},
            ],
        ) as mocked_status, patch.object(
            client.cloud_api,
            "download_lua",
            return_value=Path("/tmp/test.lua"),
        ) as mocked_download:
            devices = client.list_devices()

        self.assertEqual(devices[0]["status_payload"]["power"], "on")
        self.assertEqual(devices[0]["status_payload"]["indoor_humidity"], 51)
        self.assertEqual(devices[0]["status_payload"]["indoor_temperature"], 27)
        self.assertEqual(devices[0]["status_payload"]["_meta"]["lua_file"], "/tmp/test.lua")
        self.assertIn("lua_runtime_available", devices[0]["status_payload"]["_meta"])
        self.assertGreaterEqual(mocked_status.call_count, 3)
        mocked_download.assert_called_once()

    def test_upstream_mapping_root_is_symlinked_to_submodule(self):
        self.assertTrue(UPSTREAM_MAPPING_ROOT.exists())
        self.assertTrue(UPSTREAM_MAPPING_ROOT.is_symlink())

    def test_get_device_mapping_loads_upstream_ac_mapping_without_homeassistant_installed(self):
        mapping = get_device_mapping(0xAC, sn8="", category="wall-air-conditioner")

        self.assertTrue(mapping["controls"])
        keys = {control["key"] for control in mapping["controls"]}
        self.assertIn("thermostat:hvac_mode", keys)
        self.assertIn("thermostat:target_temperature", keys)

    def test_get_device_mapping_prefers_subtype_specific_mapping(self):
        mapping = get_device_mapping(0x21, sn8="00000000", subtype="68", category="")

        switch_controls = [control for control in mapping["controls"] if control["kind"] == "toggle"]
        self.assertEqual(len(switch_controls), 1)
        self.assertEqual(switch_controls[0]["key"], "endpoint_1_OnOff")
        self.assertEqual(switch_controls[0]["label"], "endpoint_1_name")
        self.assertEqual(
            switch_controls[0]["actions"]["turn_on"],
            {"endpoint_1_OnOff": "1"},
        )

    def test_get_device_mapping_keeps_multiple_button_controls_distinct(self):
        mapping = get_device_mapping(0x21, sn8="00000000", subtype="78", category="")

        action_controls = [control for control in mapping["controls"] if control["kind"] == "action"]
        self.assertEqual(len(action_controls), 4)
        keys = {control["key"] for control in action_controls}
        self.assertEqual(
            keys,
            {"endpoint_1_OnOff", "endpoint_2_OnOff", "endpoint_3_OnOff", "endpoint_4_OnOff"},
        )

    def test_get_device_mapping_preserves_sensor_semantics_from_upstream(self):
        mapping = get_device_mapping(0xFA, sn8="", category="")

        pm25_control = next(control for control in mapping["controls"] if control["key"] == "pm25")
        self.assertEqual(pm25_control["unit"], "ug/m3")
        self.assertEqual(pm25_control["group_label"], "环境")
        self.assertEqual(pm25_control["device_class"], "pm25")

    def test_get_device_mapping_marks_half_degree_temperature_transform(self):
        mapping = get_device_mapping(0x21, sn8="NOTFOUND", subtype="999", category="")

        target_control = next(
            control for control in mapping["controls"] if control["key"] == "thermostat:target_temperature"
        )
        self.assertEqual(
            target_control["value_transform"],
            {
                "type": "temperature_halves",
                "integer_key": "temperature",
                "fraction_key": "small_temperature",
            },
        )

    def test_get_device_mapping_keeps_refrigerator_zone_temperature_controls_distinct(self):
        mapping = get_device_mapping(0xCA, sn8="", category="")

        keys = {control["key"] for control in mapping["controls"]}
        self.assertIn("storage_zone:target_temperature", keys)
        self.assertIn("freezing_zone:target_temperature", keys)

        storage_control = next(
            control for control in mapping["controls"] if control["key"] == "storage_zone:target_temperature"
        )
        freezing_control = next(
            control for control in mapping["controls"] if control["key"] == "freezing_zone:target_temperature"
        )
        self.assertEqual(storage_control["group_label"], "冷藏区")
        self.assertEqual(storage_control["control_key"], "storage_temperature")
        self.assertEqual(freezing_control["group_label"], "冷冻区")
        self.assertEqual(freezing_control["control_key"], "freezing_temperature")

    def test_get_device_mapping_translates_dishwasher_controls_to_user_facing_labels(self):
        mapping = get_device_mapping(0xE1, sn8="760064AC", subtype="3", category="dishwasher")

        controls = {control["key"]: control for control in mapping["controls"]}
        self.assertEqual(controls["waterswitch"]["label"], "热水开关")
        self.assertEqual(controls["waterswitch"]["group_label"], "整机")
        self.assertEqual(controls["work_status"]["label"], "工作状态")
        self.assertEqual(controls["work_status"]["group_label"], "整机")
        self.assertEqual(controls["wash_mode"]["label"], "洗涤模式")
        self.assertEqual(controls["wash_mode"]["group_label"], "模式")
        option_labels = [option["label"] for option in controls["wash_mode"]["options"]]
        self.assertIn("智能洗", option_labels)
        self.assertIn("强力洗", option_labels)

    def test_audit_device_mapping_reports_raw_labels_for_untranslated_controls(self):
        issues = audit_device_mapping(
            0xFF,
            "default",
            {
                "controls": [
                    {
                        "key": "pcad_status",
                        "label": "PcadStatus",
                        "kind": "sensor",
                        "group_label": "运行状态",
                        "options": [],
                    }
                ]
            },
        )

        self.assertTrue(any(issue["issue"] == "raw_label" for issue in issues))

    def test_audit_device_mapping_does_not_flag_translated_dishwasher_controls_as_raw(self):
        mapping = get_device_mapping(0xE1, sn8="760064AC", subtype="3", category="dishwasher")
        issues = audit_device_mapping(0xE1, "760064AC", mapping)

        problem_keys = {
            issue["control_key"]
            for issue in issues
            if issue["issue"] in {"raw_label", "raw_option_label"}
        }
        self.assertNotIn("waterswitch", problem_keys)
        self.assertNotIn("work_status", problem_keys)
        self.assertNotIn("wash_mode", problem_keys)

    def test_ensure_lua_support_files_creates_cjson_and_bit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cjson_path, bit_path = ensure_lua_support_files(Path(temp_dir))

            self.assertTrue(cjson_path.exists())
            self.assertTrue(bit_path.exists())
            self.assertEqual(cjson_path.name, "cjson.lua")
            self.assertEqual(bit_path.name, "bit.lua")

    def test_lua_codec_loads_device_script_when_runtime_available(self):
        if not lua_runtime_available():
            self.skipTest("lupa runtime is not available")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            ensure_lua_support_files(temp_path)
            lua_file = temp_path / "demo.lua"
            lua_file.write_text(
                """
                function jsonToData(param)
                  return param
                end

                function dataToJson(param)
                  return param
                end
                """.strip(),
                encoding="utf-8",
            )

            codec = MideaLuaCodec(lua_file, device_type="T0xAC", sn="123456789ABCDEFG", subtype="KFR-35GW")

            query_payload = codec.build_query({"power": "on"})

        self.assertIsInstance(query_payload, str)
        self.assertIn('"power": "on"', query_payload)

    def test_execute_control_falls_back_to_generic_nested_payload(self):
        client = MideaCloudClient(
            {
                "account": "demo@example.com",
                "password": "secret",
                "server": 2,
            }
        )

        with patch.object(client.cloud_api, "login", return_value=True), patch.object(
            client,
            "get_device",
            return_value={
                "id": "998877",
                "appliance_code": 998877,
                "device_type": 0xAC,
                "sn": "123456789ABCDEFG",
                "model_number": "KFR-35GW",
                "manufacturer_code": "0000",
                "status_payload": {
                    "power": "on",
                    "_meta": {"lua_file": "/tmp/test.lua"},
                },
            },
        ), patch.object(
            client.cloud_api,
            "send_device_control",
            return_value=True,
        ) as mocked_send:
            client.execute_control(
                device_id="998877",
                control={
                    "key": "target_temperature",
                    "action_params": {"control_key": "mode.target_temperature"},
                },
                value=26,
            )

        mocked_send.assert_called_once()
        payload = mocked_send.call_args.kwargs
        self.assertEqual(payload["control"], {"mode": {"target_temperature": 26}})
        self.assertEqual(payload["status"], {"power": "on"})

    def test_execute_control_merges_centralized_fields_from_current_status(self):
        client = MideaCloudClient(
            {
                "account": "demo@example.com",
                "password": "secret",
                "server": 2,
            }
        )

        with patch.object(client.cloud_api, "login", return_value=True), patch(
            "providers.clients.midea_cloud.client.get_device_mapping",
            return_value={"centralized": ["run_mode", "fan_speed"]},
        ), patch.object(
            client,
            "get_device",
            return_value={
                "id": "2468",
                "appliance_code": 2468,
                "device_type": 0xAC,
                "sn": "123456789ABCDEFG",
                "sn8": "9ABCDEFG",
                "category": "wall-air-conditioner",
                "model_number": "KFR-35GW",
                "manufacturer_code": "0000",
                "status_payload": {
                    "run_mode": "2",
                    "fan_speed": "3",
                    "_meta": {},
                },
            },
        ), patch.object(
            client.cloud_api,
            "send_device_control",
            return_value=True,
        ) as mocked_send:
            client.execute_control(
                device_id="2468",
                control={
                    "key": "power",
                    "kind": "toggle",
                    "action_params": {"control_key": "power"},
                },
                value="1",
            )

        mocked_send.assert_called_once()
        payload = mocked_send.call_args.kwargs
        self.assertEqual(payload["control"], {"power": "1", "run_mode": "2", "fan_speed": "3"})

    def test_execute_control_applies_half_degree_temperature_transform(self):
        client = MideaCloudClient(
            {
                "account": "demo@example.com",
                "password": "secret",
                "server": 2,
            }
        )

        with patch.object(client.cloud_api, "login", return_value=True), patch.object(
            client,
            "get_device",
            return_value={
                "id": "998877",
                "appliance_code": 998877,
                "device_type": 0xAC,
                "sn": "123456789ABCDEFG",
                "sn8": "9ABCDEFG",
                "category": "wall-air-conditioner",
                "model_number": "KFR-35GW",
                "manufacturer_code": "0000",
                "status_payload": {"power": "on", "_meta": {}},
            },
        ), patch(
            "providers.clients.midea_cloud.client.get_device_mapping",
            return_value={"centralized": []},
        ), patch.object(
            client.cloud_api,
            "send_device_control",
            return_value=True,
        ) as mocked_send:
            client.execute_control(
                device_id="998877",
                control={
                    "key": "target_temperature",
                    "action_params": {
                        "control_key": "target_temperature",
                        "control_template": {"temperature": "{value}"},
                        "value_transform": {
                            "type": "temperature_halves",
                            "integer_key": "temperature",
                            "fraction_key": "small_temperature",
                        },
                    },
                },
                value=24.5,
            )

        payload = mocked_send.call_args.kwargs
        self.assertEqual(payload["control"], {"temperature": 24, "small_temperature": 5})


class MbApi2020ClientNormalizationTest(TestCase):
    def test_normalize_vehicle_prefers_baumuster_description_for_model(self):
        vehicle = {
            "vin": "LE4LG4GB2SL195893",
            "name": "214",
            "model": "214",
            "licensePlate": "川GPT032",
            "salesRelatedInformation": {
                "baumuster": {
                    "baumusterDescription": "E 300 L 豪华型轿车",
                }
            },
        }

        normalized = MbApi2020Client._normalize_vehicle(vehicle).to_dict()

        self.assertEqual(normalized["model"], "E 300 L 豪华型轿车")
        self.assertEqual(normalized["name"], "214")

    def test_extract_attribute_value_recurses_nested_value_dict(self):
        payload = {
            "value": {
                "value": {
                    "int_value": 418,
                }
            }
        }

        self.assertEqual(MbApi2020Client._extract_attribute_value(payload), 418)

    def test_extract_attribute_value_returns_none_for_nil_value_payload(self):
        payload = {
            "timestamp": "1775057071",
            "status": 4,
            "nil_value": True,
            "timestamp_in_ms": "1775057071072",
            "distance_unit": "KILOMETERS",
        }

        self.assertIsNone(MbApi2020Client._extract_attribute_value(payload))
