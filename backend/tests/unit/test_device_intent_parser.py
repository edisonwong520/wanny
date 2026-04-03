from unittest.mock import AsyncMock, patch

from django.test import TestCase

from accounts.models import Account
from comms.device_intent import (
    _postprocess_ai_result,
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

    def test_should_check_device_intent_accepts_dynamic_keyword_cache(self):
        self.assertTrue(
            should_check_device_intent(
                "check aircon status",
                keyword_cache={
                    "devices": {"aircon"},
                    "rooms": set(),
                    "controls": set(),
                    "actions": set(),
                    "colloquial": set(),
                    "mapping": {"aircon": "空调"},
                    "payloads": {},
                },
            )
        )

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

    def test_invalid_json_from_device_intent_falls_back_to_chat(self):
        import asyncio

        with patch(
            "comms.device_intent._heuristic_parse_device_intent",
            return_value=None,
        ), patch(
            "comms.device_intent._build_device_prompt_context",
            new=AsyncMock(return_value=("无设备", "无控制能力")),
        ), patch(
            "comms.device_intent.AIAgent.generate_json",
            new=AsyncMock(
                return_value={
                    "type": "simple",
                    "response": "[系统报错] 模型没有正确返回 JSON 格式，意图解析失败。",
                }
            ),
        ):
            result = asyncio.run(
                analyze_device_intent(
                    "今天天气怎么样",
                    self.account,
                    command_mode=False,
                )
            )

        self.assertEqual(result["type"], "CHAT")
        self.assertEqual(result["response"], "我刚才没有理解清楚，您可以换种说法再发一次。")

    def test_invalid_json_from_device_intent_in_command_mode_returns_unsupported(self):
        import asyncio

        with patch(
            "comms.device_intent._heuristic_parse_device_intent",
            return_value=None,
        ), patch(
            "comms.device_intent._build_device_prompt_context",
            new=AsyncMock(return_value=("无设备", "无控制能力")),
        ), patch(
            "comms.device_intent.AIAgent.generate_json",
            new=AsyncMock(
                return_value={
                    "type": "simple",
                    "response": "[系统报错] 模型没有正确返回 JSON 格式，意图解析失败。",
                }
            ),
        ):
            result = asyncio.run(
                analyze_device_intent(
                    "帮我查天气",
                    self.account,
                    command_mode=True,
                )
            )

        self.assertEqual(result["type"], "UNSUPPORTED_COMMAND")
        self.assertEqual(result["reason"], "device_intent_invalid_json")

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

    def test_postprocess_ai_result_normalizes_target_temperature_key(self):
        result = _postprocess_ai_result(
            {
                "type": "DEVICE_QUERY",
                "device": "空调",
                "control_key": "climate.bedroom_ac:target_temperature",
            },
            user_msg="我想知道卧室现在有多热",
        )

        self.assertEqual(result["control_key"], "temperature")

    def test_postprocess_ai_result_corrects_vehicle_fuel_query(self):
        result = _postprocess_ai_result(
            {
                "type": "DEVICE_QUERY",
                "device": "车",
                "control_key": "power",
            },
            user_msg="帮我看看车子还剩多少油",
        )

        self.assertEqual(result["control_key"], "tanklevelpercent")
