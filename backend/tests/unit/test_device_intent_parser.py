from unittest.mock import AsyncMock, patch

from django.test import TestCase

from accounts.models import Account
from comms.device_intent import (
    analyze_device_intent,
    detect_command_mode,
    should_check_device_intent,
    strip_wakeup_prefix,
)


class DeviceIntentParserTest(TestCase):
    def setUp(self):
        self.account = Account.objects.create(
            email="unit-device-intent@example.com",
            name="Unit Device Intent",
            password="pwd",
        )

    def test_detect_command_mode_supports_jarvis_and_chinese_prefix(self):
        self.assertEqual(detect_command_mode("jarvis, 把客厅灯关了"), "command")
        self.assertEqual(detect_command_mode("贾维斯：把空调调到 24 度"), "command")
        self.assertEqual(detect_command_mode("今天天气怎么样"), "default")

    def test_strip_wakeup_prefix_uses_same_rules_as_command_mode(self):
        self.assertEqual(strip_wakeup_prefix("jarvis，把客厅灯关了"), "把客厅灯关了")
        self.assertEqual(strip_wakeup_prefix("贾维斯：调亮一点"), "调亮一点")
        self.assertEqual(strip_wakeup_prefix("普通消息"), "普通消息")

    def test_should_check_device_intent_uses_fast_keyword_filter(self):
        self.assertTrue(should_check_device_intent("把卧室空调调到 24 度"))
        self.assertTrue(should_check_device_intent("查下客厅灯状态"))
        self.assertFalse(should_check_device_intent("帮我写个总结"))

    def test_analyze_device_intent_heuristic_handles_relative_adjustment(self):
        import asyncio

        result = asyncio.run(
            analyze_device_intent(
                "把客厅灯调暗一点",
                self.account,
                command_mode=True,
            )
        )

        self.assertEqual(result["type"], "DEVICE_CONTROL")
        self.assertEqual(result["room"], "客厅")
        self.assertEqual(result["control_key"], "brightness")
        self.assertEqual(result["value"], "-10%")

    def test_analyze_device_intent_query_returns_device_query(self):
        import asyncio

        result = asyncio.run(
            analyze_device_intent(
                "查下卧室空调多少度",
                self.account,
                command_mode=False,
            )
        )

        self.assertEqual(result["type"], "DEVICE_QUERY")
        self.assertEqual(result["room"], "卧室")
        self.assertEqual(result["device"], "空调")
        self.assertEqual(result["control_key"], "temperature")

    def test_command_mode_never_allows_chat_fallback(self):
        import asyncio

        with patch(
            "comms.device_intent._heuristic_parse_device_intent",
            return_value=None,
        ), patch(
            "comms.device_intent._build_device_prompt_context",
            new=AsyncMock(return_value=("无设备", "无控制能力")),
        ), patch(
            "comms.device_intent.AIAgent.generate_json",
            new=AsyncMock(return_value={"type": "CHAT", "response": "只是聊天"}),
        ):
            result = asyncio.run(
                analyze_device_intent(
                    "这周安排怎么样",
                    self.account,
                    command_mode=True,
                )
            )

        self.assertEqual(result["type"], "UNSUPPORTED_COMMAND")
        self.assertEqual(result["reason"], "chat_not_allowed_in_command_mode")

    def test_command_mode_returns_unsupported_command_when_unmatched(self):
        import asyncio

        result = asyncio.run(
            analyze_device_intent(
                "帮我安排下周会议",
                self.account,
                command_mode=True,
            )
        )

        self.assertEqual(result["type"], "UNSUPPORTED_COMMAND")
        self.assertEqual(result["reason"], "heuristic_unmatched")
