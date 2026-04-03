import asyncio
import os

from django.test import TransactionTestCase

from accounts.models import Account
from comms.device_intent import analyze_device_intent
from comms.models import DeviceOperationContext, Mission
from devices.models import DeviceControl, DeviceRoom, DeviceSnapshot


def _has_real_ai_config() -> bool:
    base_url = str(os.getenv("AI_BASE_URL", "")).strip()
    api_key = str(os.getenv("AI_API_KEY", "")).strip()
    gemini_key = str(os.getenv("GEMINI_API_KEY", "")).strip()
    return bool((base_url and api_key) or gemini_key)


class RealAIDeviceIntentSemanticTest(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not _has_real_ai_config():
            raise cls.skipTest("Real AI configuration is not available for semantic device-intent tests.")

    def setUp(self):
        self.account = Account.objects.create(
            email="real-ai-device-intent@example.com",
            name="Real AI Device Intent",
            password="pwd",
        )

        bedroom = DeviceRoom.objects.create(
            account=self.account,
            slug="bedroom",
            name="卧室",
            climate="25°C",
            summary="卧室",
            sort_order=10,
        )
        living_room = DeviceRoom.objects.create(
            account=self.account,
            slug="living-room",
            name="客厅",
            climate="26°C",
            summary="客厅",
            sort_order=20,
        )

        self.ac = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="ha:ac-real-ai",
            room=bedroom,
            name="空调",
            category="空调",
            status=DeviceSnapshot.StatusChoices.ONLINE,
            telemetry="制冷",
            capabilities=["temperature"],
            sort_order=10,
        )
        self.light = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="ha:light-real-ai",
            room=living_room,
            name="主灯",
            category="灯",
            status=DeviceSnapshot.StatusChoices.ONLINE,
            telemetry="开启",
            capabilities=["power", "brightness"],
            sort_order=20,
        )
        self.vehicle = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="mbapi2020:VIN-REAL-AI",
            room=living_room,
            name="E 300 L",
            category="vehicle",
            status=DeviceSnapshot.StatusChoices.ONLINE,
            telemetry="车牌 沪A12345",
            source_payload={"license_plate": "沪A12345"},
            capabilities=["tanklevelpercent"],
            sort_order=30,
        )

        DeviceControl.objects.create(
            account=self.account,
            device=self.ac,
            external_id="ha:ac-real-ai:temperature",
            parent_external_id="ha:ac-real-ai:temperature",
            source_type=DeviceControl.SourceTypeChoices.HA_ENTITY,
            kind=DeviceControl.KindChoices.RANGE,
            key="climate.bedroom_ac:target_temperature",
            label="空调 目标温度",
            writable=True,
            value=26,
            unit="°C",
            range_spec={"min": 16, "max": 30, "step": 1},
            sort_order=10,
        )
        DeviceControl.objects.create(
            account=self.account,
            device=self.light,
            external_id="ha:light-real-ai:power",
            parent_external_id="ha:light-real-ai:power",
            source_type=DeviceControl.SourceTypeChoices.HA_ENTITY,
            kind=DeviceControl.KindChoices.TOGGLE,
            key="power",
            label="电源",
            writable=True,
            value="on",
            sort_order=20,
        )
        DeviceControl.objects.create(
            account=self.account,
            device=self.vehicle,
            external_id="mbapi2020:VIN-REAL-AI:tanklevelpercent",
            parent_external_id="mbapi2020:VIN-REAL-AI",
            source_type=DeviceControl.SourceTypeChoices.MBAPI2020_PROPERTY,
            kind=DeviceControl.KindChoices.SENSOR,
            key="tanklevelpercent",
            label="油量",
            writable=False,
            value=68,
            unit="%",
            sort_order=30,
        )

    def test_real_ai_semantic_temperature_question_is_query_only(self):
        result = asyncio.run(
            analyze_device_intent(
                "我想知道卧室现在有多热",
                self.account,
                command_mode=False,
            )
        )

        self.assertEqual(result["type"], "DEVICE_QUERY")
        self.assertEqual(result.get("room"), "卧室")
        self.assertIn(result.get("control_key"), {"temperature", "target_temperature"})
        self.assertEqual(Mission.objects.count(), 0)
        self.assertEqual(DeviceOperationContext.objects.count(), 0)

    def test_real_ai_semantic_light_state_question_is_query_only(self):
        result = asyncio.run(
            analyze_device_intent(
                "客厅现在是不是还亮着",
                self.account,
                command_mode=False,
            )
        )

        self.assertEqual(result["type"], "DEVICE_QUERY")
        self.assertEqual(result.get("room"), "客厅")
        self.assertIn(result.get("device"), {"主灯", "灯", ""})
        self.assertIn(result.get("control_key"), {"power", "brightness"})
        self.assertEqual(Mission.objects.count(), 0)
        self.assertEqual(DeviceOperationContext.objects.count(), 0)

    def test_real_ai_semantic_vehicle_fuel_question_is_query_only(self):
        result = asyncio.run(
            analyze_device_intent(
                "车现在是不是快没油了",
                self.account,
                command_mode=False,
            )
        )

        self.assertEqual(result["type"], "DEVICE_QUERY")
        self.assertIn(result.get("device"), {"车", "车辆", "奔驰", "E 300 L", ""})
        self.assertEqual(result.get("control_key"), "tanklevelpercent")
        self.assertEqual(Mission.objects.count(), 0)
        self.assertEqual(DeviceOperationContext.objects.count(), 0)

    def test_real_ai_semantic_fridge_open_question_is_query_only(self):
        fridge = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="ha:fridge-real-ai",
            room=None,
            name="多开门冰箱",
            category="冰箱",
            status=DeviceSnapshot.StatusChoices.ONLINE,
            telemetry="运行中",
            capabilities=["power"],
            sort_order=40,
        )
        DeviceControl.objects.create(
            account=self.account,
            device=fridge,
            external_id="ha:fridge-real-ai:power",
            parent_external_id="ha:fridge-real-ai:power",
            source_type=DeviceControl.SourceTypeChoices.HA_ENTITY,
            kind=DeviceControl.KindChoices.TOGGLE,
            key="power",
            label="电源",
            writable=True,
            value="on",
            sort_order=40,
        )

        result = asyncio.run(
            analyze_device_intent(
                "我想确认一下冰箱现在是不是开着的",
                self.account,
                command_mode=False,
            )
        )

        self.assertEqual(result["type"], "DEVICE_QUERY")
        self.assertIn(result.get("device"), {"冰箱", "多开门冰箱", ""})
        self.assertEqual(result.get("control_key"), "power")
        self.assertEqual(Mission.objects.count(), 0)
        self.assertEqual(DeviceOperationContext.objects.count(), 0)

    def test_real_ai_semantic_vehicle_lock_question_is_query_only(self):
        result = asyncio.run(
            analyze_device_intent(
                "帮我确认一下车门现在是不是锁着的",
                self.account,
                command_mode=False,
            )
        )

        self.assertEqual(result["type"], "DEVICE_QUERY")
        self.assertIn(result.get("device"), {"车", "车辆", "奔驰", "E 300 L", ""})
        self.assertEqual(result.get("control_key"), "doorlockstatusvehicle")
        self.assertEqual(Mission.objects.count(), 0)
        self.assertEqual(DeviceOperationContext.objects.count(), 0)

    def test_real_ai_semantic_light_confirmation_question_is_query_only(self):
        result = asyncio.run(
            analyze_device_intent(
                "我想确认一下客厅主灯现在是不是还亮着",
                self.account,
                command_mode=False,
            )
        )

        self.assertEqual(result["type"], "DEVICE_QUERY")
        self.assertEqual(result.get("room"), "客厅")
        self.assertIn(result.get("device"), {"主灯", "灯", ""})
        self.assertIn(result.get("control_key"), {"power", "brightness"})
        self.assertEqual(Mission.objects.count(), 0)
        self.assertEqual(DeviceOperationContext.objects.count(), 0)

    def test_real_ai_semantic_english_fridge_question_is_query_only(self):
        fridge = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="ha:fridge-real-ai-english",
            room=None,
            name="多开门冰箱",
            category="冰箱",
            status=DeviceSnapshot.StatusChoices.ONLINE,
            telemetry="运行中",
            capabilities=["power"],
            sort_order=50,
        )
        DeviceControl.objects.create(
            account=self.account,
            device=fridge,
            external_id="ha:fridge-real-ai-english:power",
            parent_external_id="ha:fridge-real-ai-english:power",
            source_type=DeviceControl.SourceTypeChoices.HA_ENTITY,
            kind=DeviceControl.KindChoices.TOGGLE,
            key="power",
            label="电源",
            writable=True,
            value="on",
            sort_order=50,
        )

        result = asyncio.run(
            analyze_device_intent(
                "is the fridge still on",
                self.account,
                command_mode=False,
            )
        )

        self.assertEqual(result["type"], "DEVICE_QUERY")
        self.assertIn(result.get("device"), {"冰箱", "多开门冰箱", ""})
        self.assertEqual(result.get("control_key"), "power")
        self.assertEqual(Mission.objects.count(), 0)
        self.assertEqual(DeviceOperationContext.objects.count(), 0)

    def test_real_ai_semantic_english_vehicle_lock_question_is_query_only(self):
        result = asyncio.run(
            analyze_device_intent(
                "is the car locked",
                self.account,
                command_mode=False,
            )
        )

        self.assertEqual(result["type"], "DEVICE_QUERY")
        self.assertIn(result.get("device"), {"车", "车辆", "奔驰", "E 300 L", ""})
        self.assertEqual(result.get("control_key"), "doorlockstatusvehicle")
        self.assertEqual(Mission.objects.count(), 0)
        self.assertEqual(DeviceOperationContext.objects.count(), 0)

    def test_real_ai_semantic_english_temperature_question_is_query_only(self):
        result = asyncio.run(
            analyze_device_intent(
                "what's the bedroom temperature",
                self.account,
                command_mode=False,
            )
        )

        self.assertEqual(result["type"], "DEVICE_QUERY")
        self.assertEqual(result.get("room"), "卧室")
        self.assertIn(result.get("control_key"), {"temperature", "target_temperature"})
        self.assertEqual(Mission.objects.count(), 0)
        self.assertEqual(DeviceOperationContext.objects.count(), 0)
