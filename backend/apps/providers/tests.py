import json
from django.test import TestCase, Client
from django.urls import reverse
from .models import PlatformAuth

class PlatformAuthAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('providers:platform_auth_upsert')

    def test_upsert_platform_auth(self):
        payload = {
            "platform": "mijia",
            "payload": {
                "access_token": "mock-token-123",
                "uid": "1111"
            }
        }
        
        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PlatformAuth.objects.count(), 1)
        
        auth_obj = PlatformAuth.objects.first()
        self.assertEqual(auth_obj.platform_name, "mijia")
        self.assertEqual(auth_obj.auth_payload['access_token'], "mock-token-123")

    def test_missing_platform_name(self):
        response = self.client.post(
            self.url,
            data=json.dumps({"payload": {}}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(PlatformAuth.objects.count(), 0)
