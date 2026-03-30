import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, Client
from django.urls import reverse

from .auth_sessions import AuthorizationSessionStore
from .models import PlatformAuth
from .services import XiaomiAuthService


class PlatformAuthAPITest(TestCase):
    def setUp(self):
        AuthorizationSessionStore.reset()
        self.client = Client()
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
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(PlatformAuth.objects.count(), 1)

        auth_obj = PlatformAuth.objects.first()
        self.assertEqual(auth_obj.platform_name, "wechat")
        self.assertEqual(auth_obj.auth_payload['access_token'], "mock-token-123")
        self.assertEqual(response.json()["provider"]["status"], "connected")

    def test_missing_platform_name(self):
        response = self.client.post(
            self.url,
            data=json.dumps({"payload": {}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(PlatformAuth.objects.count(), 0)

    def test_list_platform_auths_includes_supported_platforms_and_masks_sensitive_payload(self):
        PlatformAuth.objects.create(
            platform_name="wechat",
            auth_payload={
                "access_token": "mock-token-123",
                "refresh_token": "refresh-token-456",
                "wxid": "wxid_edison",
            },
            is_active=True,
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")

        providers = {provider["platform"]: provider for provider in payload["providers"]}
        self.assertIn("wechat", providers)
        self.assertIn("xiaomi", providers)
        self.assertEqual(providers["wechat"]["status"], "connected")
        self.assertTrue(providers["wechat"]["configured"])
        self.assertNotEqual(
            providers["wechat"]["payload_preview"]["access_token"],
            "mock-token-123",
        )
        self.assertEqual(providers["xiaomi"]["status"], "not_connected")
        self.assertFalse(providers["xiaomi"]["configured"])

    def test_get_xiaomi_platform_detail_returns_supported_placeholder_when_not_configured(self):
        response = self.client.get(self.detail_url("xiaomi"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()["provider"]
        self.assertEqual(payload["platform"], "xiaomi")
        self.assertEqual(payload["display_name_zh"], "米家")
        self.assertEqual(payload["status"], "not_connected")
        self.assertFalse(payload["configured"])

    def test_get_mijia_alias_returns_xiaomi_platform_detail(self):
        PlatformAuth.objects.create(
            platform_name="xiaomi",
            auth_payload={"serviceToken": "mi-token-123"},
            is_active=True,
        )

        response = self.client.get(self.detail_url("mijia"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()["provider"]
        self.assertEqual(payload["platform"], "xiaomi")
        self.assertEqual(payload["display_name_zh"], "米家")
        self.assertEqual(payload["status"], "connected")

    def test_upsert_xiaomi_platform_auth(self):
        payload = {
            "platform": "xiaomi",
            "payload": {
                "access_token": "mi-token-123",
                "user_id": "xiaomi-user-1",
            },
        }

        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        auth_obj = PlatformAuth.objects.get(platform_name="xiaomi")
        self.assertEqual(auth_obj.auth_payload["access_token"], "mi-token-123")
        self.assertEqual(response.json()["provider"]["status"], "connected")

    def test_upsert_mijia_alias_stores_xiaomi_platform_auth(self):
        payload = {
            "platform": "mijia",
            "payload": {
                "serviceToken": "mi-token-456",
                "userId": "xiaomi-user-2",
            },
        }

        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(PlatformAuth.objects.filter(platform_name="xiaomi").count(), 1)
        self.assertEqual(PlatformAuth.objects.filter(platform_name="mijia").count(), 0)
        auth_obj = PlatformAuth.objects.get(platform_name="xiaomi")
        self.assertEqual(auth_obj.auth_payload["serviceToken"], "mi-token-456")
        self.assertEqual(response.json()["provider"]["platform"], "xiaomi")

    def test_patch_platform_auth_merges_payload_and_updates_active(self):
        PlatformAuth.objects.create(
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
        )

        self.assertEqual(response.status_code, 200)
        auth_obj = PlatformAuth.objects.get(platform_name="wechat")
        self.assertFalse(auth_obj.is_active)
        self.assertEqual(auth_obj.auth_payload["access_token"], "mock-token-123")
        self.assertEqual(auth_obj.auth_payload["wxid"], "wxid_edison")
        self.assertEqual(response.json()["provider"]["status"], "disabled")

    def test_delete_platform_auth_removes_record(self):
        PlatformAuth.objects.create(
            platform_name="wechat",
            auth_payload={"access_token": "mock-token-123"},
            is_active=True,
        )

        response = self.client.delete(self.detail_url("wechat"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(PlatformAuth.objects.count(), 0)

    def test_xiaomi_login_endpoint_returns_provider_from_service(self):
        auth_obj = PlatformAuth.objects.create(
            platform_name="xiaomi",
            auth_payload={"serviceToken": "mi-token-123", "userId": "xiaomi-user-1"},
            is_active=True,
        )

        with patch("providers.views.XiaomiAuthService.login_and_store", return_value=auth_obj):
            response = self.client.post(self.login_url("xiaomi"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["provider"]["platform"], "xiaomi")
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
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["session"]["platform"], "wechat")
        self.assertEqual(payload["session"]["status"], "pending")
        self.assertEqual(payload["session"]["auth_kind"], "link")

    def test_authorize_xiaomi_endpoint_returns_pending_qr_session(self):
        with patch("providers.views.XiaomiAuthorizationService.start_session") as mocked_start:
            mocked_start.return_value = AuthorizationSessionStore.create(
                platform="xiaomi",
                auth_kind="qr",
                status="pending",
                title="米家授权进行中",
                instruction="请扫描二维码。",
                detail="等待米家 App 确认。",
                image_url="https://xiaomi.example/qr.png",
                verification_url="https://xiaomi.example/login",
            )

            response = self.client.post(
                self.authorize_url("xiaomi"),
                data=json.dumps({}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["session"]["platform"], "xiaomi")
        self.assertEqual(payload["session"]["auth_kind"], "qr")
        self.assertEqual(payload["session"]["image_url"], "https://xiaomi.example/qr.png")

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

        response = self.client.get(self.authorize_url("wechat"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["session"]["status"], "scanned")
        self.assertEqual(payload["session"]["platform"], "wechat")


class XiaomiAuthServiceTest(TestCase):
    def setUp(self):
        AuthorizationSessionStore.reset()

    def test_write_auth_file_from_db_loads_active_xiaomi_payload(self):
        PlatformAuth.objects.create(
            platform_name="xiaomi",
            auth_payload={"serviceToken": "mi-token-123", "userId": "xiaomi-user-1"},
            is_active=True,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            auth_file = Path(temp_dir) / "auth.json"
            XiaomiAuthService.write_auth_file_from_db(auth_file)

            with open(auth_file, "r", encoding="utf-8") as f:
                payload = json.load(f)

        self.assertEqual(payload["serviceToken"], "mi-token-123")
        self.assertEqual(payload["userId"], "xiaomi-user-1")

    def test_login_and_store_persists_mijia_api_auth_payload_to_platform_auth(self):
        class FakeMijiaAPI:
            def __init__(self, auth_data_path):
                self.auth_data_path = auth_data_path
                self.auth_data = {}

            def login(self):
                self.auth_data = {
                    "serviceToken": "mi-token-123",
                    "userId": "xiaomi-user-1",
                    "cUserId": "c-user-1",
                }
                with open(self.auth_data_path, "w", encoding="utf-8") as f:
                    json.dump(self.auth_data, f)
                return self.auth_data

        with tempfile.TemporaryDirectory() as temp_dir:
            auth_file = Path(temp_dir) / "auth.json"
            with patch("providers.services.mijiaAPI", FakeMijiaAPI):
                auth_obj = XiaomiAuthService.login_and_store(auth_file)

        self.assertEqual(auth_obj.platform_name, "xiaomi")
        self.assertTrue(auth_obj.is_active)
        self.assertEqual(auth_obj.auth_payload["serviceToken"], "mi-token-123")
