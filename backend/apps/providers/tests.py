import json
from django.test import TestCase, Client
from django.urls import reverse

from .models import PlatformAuth


class PlatformAuthAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('providers:platform_auth_upsert')
        self.detail_url = lambda platform_name: reverse('providers:platform_auth_detail', args=[platform_name])

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
        self.assertIn("mijia", providers)
        self.assertEqual(providers["wechat"]["status"], "connected")
        self.assertTrue(providers["wechat"]["configured"])
        self.assertNotEqual(
            providers["wechat"]["payload_preview"]["access_token"],
            "mock-token-123",
        )
        self.assertEqual(providers["mijia"]["status"], "not_connected")
        self.assertFalse(providers["mijia"]["configured"])

    def test_get_platform_detail_returns_supported_placeholder_when_not_configured(self):
        response = self.client.get(self.detail_url("mijia"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()["provider"]
        self.assertEqual(payload["platform"], "mijia")
        self.assertEqual(payload["status"], "not_connected")
        self.assertFalse(payload["configured"])

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
