import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import Account
from .auth_sessions import AuthorizationSessionStore
from .models import PlatformAuth
from .services import HomeAssistantAuthService, MijiaAuthService


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
