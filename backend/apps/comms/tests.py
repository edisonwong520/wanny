import json
import os
import tempfile
from unittest.mock import patch

from django.test import TestCase

from providers.models import PlatformAuth

from .management.commands.runwechatbot import Command


class RunWeChatBotCommandTest(TestCase):
    def test_prepare_wechat_credentials_waits_until_platform_auth_has_wechat_payload(self):
        command = Command()

        with tempfile.TemporaryDirectory() as temp_dir:
            cred_file = os.path.join(temp_dir, "wechat_credentials.json")
            with open(cred_file, "w", encoding="utf-8") as f:
                json.dump({"stale": True}, f)

            sleep_calls = {"count": 0}

            def fake_sleep(_seconds):
                sleep_calls["count"] += 1
                if sleep_calls["count"] == 1:
                    PlatformAuth.objects.create(
                        platform_name="wechat",
                        auth_payload={"access_token": "mock-token-123", "wxid": "wxid_edison"},
                        is_active=True,
                    )

            with patch("comms.management.commands.runwechatbot.time.sleep", side_effect=fake_sleep):
                command._prepare_wechat_credentials(cred_file)

            self.assertEqual(sleep_calls["count"], 1)
            with open(cred_file, "r", encoding="utf-8") as f:
                payload = json.load(f)

            self.assertEqual(payload["access_token"], "mock-token-123")
            self.assertEqual(payload["wxid"], "wxid_edison")
