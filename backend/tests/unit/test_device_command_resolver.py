from django.test import TransactionTestCase
from django.utils import timezone

from accounts.models import Account
from comms.device_context_manager import DeviceContextManager
from comms.device_command_service import DeviceCommandService
from comms.models import DeviceOperationContext
from devices.models import DeviceControl, DeviceRoom, DeviceSnapshot


class DeviceCommandResolverTest(TransactionTestCase):
    def setUp(self):
        self.account = Account.objects.create(
            email="unit-device-resolver@example.com",
            name="Unit Device Resolver",
            password="pwd",
        )
        self.living_room = DeviceRoom.objects.create(
            account=self.account,
            slug="living-room",
            name="客厅",
            climate="26°C",
            summary="客厅",
            sort_order=10,
        )
        self.bedroom = DeviceRoom.objects.create(
            account=self.account,
            slug="bedroom",
            name="卧室",
            climate="25°C",
            summary="卧室",
            sort_order=20,
        )
        self.living_light = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="mijia:light-living",
            room=self.living_room,
            name="主灯",
            category="灯",
            status=DeviceSnapshot.StatusChoices.ONLINE,
            telemetry="开启",
            capabilities=["power", "brightness"],
            sort_order=10,
        )
        self.bedroom_light = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="mijia:light-bedroom",
            room=self.bedroom,
            name="主灯",
            category="灯",
            status=DeviceSnapshot.StatusChoices.ONLINE,
            telemetry="开启",
            capabilities=["power"],
            sort_order=20,
        )
        self.ac = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="ha:ac-bedroom",
            room=self.bedroom,
            name="空调",
            category="空调",
            status=DeviceSnapshot.StatusChoices.ONLINE,
            telemetry="制冷",
            capabilities=["temperature"],
            sort_order=30,
        )
        self.living_light_power = DeviceControl.objects.create(
            account=self.account,
            device=self.living_light,
            external_id="mijia:light-living:power",
            parent_external_id="mijia:light-living:power",
            source_type=DeviceControl.SourceTypeChoices.MIJIA_PROPERTY,
            kind=DeviceControl.KindChoices.TOGGLE,
            key="power",
            label="电源",
            writable=True,
            value="on",
            sort_order=10,
        )
        self.living_light_brightness = DeviceControl.objects.create(
            account=self.account,
            device=self.living_light,
            external_id="mijia:light-living:brightness",
            parent_external_id="mijia:light-living:brightness",
            source_type=DeviceControl.SourceTypeChoices.MIJIA_PROPERTY,
            kind=DeviceControl.KindChoices.RANGE,
            key="brightness",
            label="亮度",
            writable=True,
            value=70,
            range_spec={"min": 1, "max": 100, "step": 1},
            sort_order=20,
        )
        self.bedroom_light_power = DeviceControl.objects.create(
            account=self.account,
            device=self.bedroom_light,
            external_id="mijia:light-bedroom:power",
            parent_external_id="mijia:light-bedroom:power",
            source_type=DeviceControl.SourceTypeChoices.MIJIA_PROPERTY,
            kind=DeviceControl.KindChoices.TOGGLE,
            key="power",
            label="电源",
            writable=True,
            value="on",
            sort_order=10,
        )
        self.ac_temperature = DeviceControl.objects.create(
            account=self.account,
            device=self.ac,
            external_id="ha:ac-bedroom:temperature",
            parent_external_id="ha:ac-bedroom:temperature",
            source_type=DeviceControl.SourceTypeChoices.HA_ENTITY,
            kind=DeviceControl.KindChoices.RANGE,
            key="temperature",
            label="目标温度",
            writable=True,
            value=26,
            unit="°C",
            range_spec={"min": 16, "max": 30, "step": 1},
            sort_order=10,
        )

    def test_resolve_device_target_prefers_exact_room_device_and_control_match(self):
        import asyncio

        resolved = asyncio.run(
            DeviceCommandService.resolve_device_target(
                self.account,
                {
                    "type": "DEVICE_CONTROL",
                    "room": "客厅",
                    "device": "主灯",
                    "control_key": "电源",
                    "value": False,
                },
            )
        )

        self.assertEqual(resolved["matched_device"], self.living_light)
        self.assertEqual(resolved["matched_control"], self.living_light_power)
        self.assertFalse(resolved["ambiguous"])
        self.assertGreaterEqual(resolved["confidence"], 1.0)

    def test_resolve_device_target_marks_ambiguous_when_multiple_candidates_tie(self):
        import asyncio

        resolved = asyncio.run(
            DeviceCommandService.resolve_device_target(
                self.account,
                {
                    "type": "DEVICE_CONTROL",
                    "device": "主灯",
                    "control_key": "power",
                    "value": False,
                },
            )
        )

        self.assertTrue(resolved["ambiguous"])
        self.assertEqual(resolved["matched_device"], self.living_light)
        self.assertEqual(len(resolved["alternatives"]), 2)

    def test_resolve_device_target_returns_empty_result_when_control_not_supported(self):
        import asyncio

        resolved = asyncio.run(
            DeviceCommandService.resolve_device_target(
                self.account,
                {
                    "type": "DEVICE_CONTROL",
                    "room": "卧室",
                    "device": "主灯",
                    "control_key": "temperature",
                    "value": 24,
                },
            )
        )

        self.assertIsNone(resolved["matched_device"])
        self.assertIsNone(resolved["matched_control"])
        self.assertTrue(resolved["ambiguous"])

    def test_resolve_from_context_can_inherit_recent_continuous_control(self):
        DeviceContextManager.record_operation(
            account=self.account,
            device=self.living_light,
            control_id=self.living_light_brightness.external_id,
            control_key="brightness",
            operation_type="set_property",
            value=70,
        )

        resolved = DeviceCommandService._resolve_from_context(
            self.account,
            {
                "type": "DEVICE_CONTROL",
                "control_key": "brightness",
                "value": "-10%",
            },
        )

        self.assertEqual(resolved["matched_device"], self.living_light)
        self.assertEqual(resolved["matched_control"], self.living_light_brightness)
        self.assertTrue(resolved["resolved_from_context"])

    def test_resolve_from_context_does_not_inherit_recent_power_toggle(self):
        row = DeviceContextManager.record_operation(
            account=self.account,
            device=self.ac,
            control_id=self.ac_temperature.external_id,
            control_key="temperature",
            operation_type="set_property",
            value=26,
        )
        DeviceOperationContext.objects.filter(id=row.id).update(operated_at=timezone.now())

        resolved = DeviceCommandService._resolve_from_context(
            self.account,
            {
                "type": "DEVICE_CONTROL",
                "control_key": "power",
                "value": False,
            },
        )

        self.assertIsNone(resolved)
