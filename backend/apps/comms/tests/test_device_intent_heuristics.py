import asyncio
import os
from unittest.mock import AsyncMock, patch

from django.test import TransactionTestCase

from accounts.models import Account
from comms.command_router import route_command
from comms.device_intent import _heuristic_parse_device_intent, analyze_device_intent
from comms.models import LearnedKeyword
from devices.models import DeviceControl, DeviceRoom, DeviceSnapshot


class DeviceIntentHeuristicTest(TransactionTestCase):
    def setUp(self):
        self.account = Account.objects.create(
            email="intent@example.com",
            name="Intent Test",
            password="pwd",
        )
        room = DeviceRoom.objects.create(
            account=self.account,
            slug="living-room",
            name="客厅",
            climate="26°C",
            summary="测试房间",
            sort_order=10,
        )
        device = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="ha:ac-1",
            room=room,
            name="空调",
            category="空调",
            status=DeviceSnapshot.StatusChoices.ONLINE,
            telemetry="制冷",
            capabilities=["temperature"],
            sort_order=10,
        )
        self.control = DeviceControl.objects.create(
            account=self.account,
            device=device,
            external_id="ha:ac-1:temperature",
            parent_external_id="ha:ac-1:temperature",
            source_type=DeviceControl.SourceTypeChoices.HA_ENTITY,
            kind=DeviceControl.KindChoices.RANGE,
            key="climate.living_room_ac:target_temperature",
            label="空调 目标温度",
            writable=True,
            value=26,
            unit="°C",
            range_spec={"min": 16, "max": 30, "step": 1},
            sort_order=10,
        )

    def test_heuristic_parse_temperature_command(self):
        result = asyncio.run(
            analyze_device_intent("把客厅空调调到24度", self.account, command_mode=True)
        )
        self.assertEqual(result["type"], "DEVICE_CONTROL")

    def test_heuristic_parse_english_turn_on_command(self):
        result = _heuristic_parse_device_intent("turn on the living room light", command_mode=False)

        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "DEVICE_CONTROL")
        self.assertEqual(result["room"], "客厅")
        self.assertEqual(result["device"], "灯")
        self.assertEqual(result["control_key"], "power")
        self.assertEqual(result["value"], True)

    def test_heuristic_question_about_device_state_prefers_query_over_control(self):
        result = _heuristic_parse_device_intent("冰箱是开着的吗", command_mode=False)

        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "DEVICE_QUERY")
        self.assertEqual(result["device"], "冰箱")
        self.assertEqual(result["control_key"], "power")

    def test_heuristic_question_with_is_it_on_in_chinese_prefers_query(self):
        result = _heuristic_parse_device_intent("客厅主灯是不是还开着", command_mode=False)

        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "DEVICE_QUERY")
        self.assertEqual(result["room"], "客厅")
        self.assertEqual(result["device"], "主灯")
        self.assertEqual(result["control_key"], "power")

    def test_heuristic_question_with_open_not_open_phrase_prefers_query(self):
        result = _heuristic_parse_device_intent("空调现在开没开", command_mode=False)

        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "DEVICE_QUERY")
        self.assertEqual(result["device"], "空调")
        self.assertEqual(result["control_key"], "power")

    def test_heuristic_question_with_brightness_state_phrase_prefers_query(self):
        result = _heuristic_parse_device_intent("灯是不是亮着", command_mode=False)

        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "DEVICE_QUERY")
        self.assertEqual(result["device"], "灯")
        self.assertIn(result["control_key"], {"power", "brightness"})

    def test_heuristic_question_with_lock_state_phrase_prefers_query(self):
        result = _heuristic_parse_device_intent("车门锁上了吗", command_mode=False)

        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "DEVICE_QUERY")
        self.assertEqual(result["control_key"], "doorlockstatusvehicle")

    def test_heuristic_question_with_still_on_colloquial_phrase_prefers_query(self):
        result = _heuristic_parse_device_intent("冰箱还开着没", command_mode=False)

        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "DEVICE_QUERY")
        self.assertEqual(result["device"], "冰箱")
        self.assertEqual(result["control_key"], "power")

    def test_heuristic_question_with_is_open_status_phrase_prefers_query(self):
        result = _heuristic_parse_device_intent("冰箱现在是不是处于开启状态", command_mode=False)

        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "DEVICE_QUERY")
        self.assertEqual(result["device"], "冰箱")
        self.assertEqual(result["control_key"], "power")

    def test_heuristic_question_with_lock_colloquial_phrase_prefers_query(self):
        result = _heuristic_parse_device_intent("帮我看看车门现在锁着没有", command_mode=False)

        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "DEVICE_QUERY")
        self.assertEqual(result["control_key"], "doorlockstatusvehicle")

    def test_heuristic_question_with_light_confirmation_phrase_prefers_query(self):
        result = _heuristic_parse_device_intent("我想确认一下客厅主灯现在是不是还亮着", command_mode=False)

        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "DEVICE_QUERY")
        self.assertEqual(result["room"], "客厅")
        self.assertEqual(result["device"], "主灯")
        self.assertIn(result["control_key"], {"power", "brightness"})

    def test_heuristic_english_fridge_question_prefers_query(self):
        result = _heuristic_parse_device_intent("is the fridge still on", command_mode=False)

        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "DEVICE_QUERY")
        self.assertEqual(result["device"], "冰箱")
        self.assertEqual(result["control_key"], "power")

    def test_heuristic_english_vehicle_lock_question_prefers_query(self):
        result = _heuristic_parse_device_intent("is the car locked", command_mode=False)

        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "DEVICE_QUERY")
        self.assertEqual(result["device"], "车")
        self.assertEqual(result["control_key"], "doorlockstatusvehicle")

    def test_heuristic_english_temperature_question_prefers_query(self):
        result = _heuristic_parse_device_intent("what's the bedroom temperature", command_mode=False)

        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "DEVICE_QUERY")
        self.assertEqual(result["room"], "卧室")
        self.assertEqual(result["control_key"], "temperature")

    def test_heuristic_english_temperature_control_is_not_misclassified_as_query(self):
        result = _heuristic_parse_device_intent("set bedroom temperature to 24", command_mode=False)

        if result is not None:
            self.assertNotEqual(result["type"], "DEVICE_QUERY")

    def test_route_command_marks_english_input_for_normalization(self):
        route = asyncio.run(route_command("please make the bedroom warmer", account=self.account, command_mode=False))

        self.assertEqual(route["route"], "needs_normalize")
        self.assertEqual(route["reason"], "english_heavy")
        self.assertGreaterEqual(route["signals"]["english"], 2)

    def test_route_command_marks_standard_device_query(self):
        route = asyncio.run(route_command("空调几度啊", account=self.account, command_mode=False))

        self.assertEqual(route["route"], "standard")
        self.assertEqual(route["reason"], "device_query_signal")

    def test_route_command_skips_non_device_chat(self):
        route = asyncio.run(route_command("今天天气怎么样", account=self.account, command_mode=False))

        self.assertEqual(route["route"], "skip_device")
        self.assertEqual(route["reason"], "no_device_signal")

    def test_route_command_sends_multi_intent_to_full_ai(self):
        route = asyncio.run(route_command("开灯然后开空调", account=self.account, command_mode=False))

        self.assertEqual(route["route"], "needs_full_ai")
        self.assertEqual(route["reason"], "multi_intent")

    def test_route_command_uses_account_learned_alias_for_device_signal(self):
        LearnedKeyword.objects.create(
            account=self.account,
            keyword="aircon",
            normalized_keyword="aircon",
            canonical="空调",
            canonical_payload={"device": "空调"},
            category=LearnedKeyword.CategoryChoices.DEVICE,
            source=LearnedKeyword.SourceChoices.USER,
        )

        route = asyncio.run(route_command("check aircon status", account=self.account, command_mode=False))

        self.assertNotEqual(route["route"], "skip_device")
        self.assertTrue(route["signals"]["has_device_signal"])

    def test_analyze_device_intent_uses_normalizer_when_enabled(self):
        with patch.dict("os.environ", {"ENABLE_COMMAND_NORMALIZER": "true"}, clear=False), patch(
            "comms.normalizer.CommandNormalizer.normalize",
            new=AsyncMock(return_value="降低卧室温度"),
        ), patch(
            "comms.device_intent._build_device_prompt_context",
            new=AsyncMock(return_value=("无设备", "无控制能力")),
        ):
            result = asyncio.run(
                analyze_device_intent(
                    "it feels too hot in the bedroom",
                    self.account,
                    command_mode=False,
                    allow_normalize=True,
                )
            )

        self.assertEqual(result["type"], "DEVICE_CONTROL")
        self.assertEqual(result["room"], "卧室")
        self.assertEqual(result["control_key"], "temperature")

