import asyncio
from unittest.mock import patch

from django.test import TransactionTestCase

from accounts.models import Account
from comms.device_command_service import DeviceCommandService
from comms.device_intent import _heuristic_parse_device_intent
from devices.executor import DeviceExecutor
from devices.models import DeviceControl, DeviceRoom, DeviceSnapshot
from devices.services import DeviceDashboardService


class DeviceCommandServiceTest(TransactionTestCase):
    def setUp(self):
        self.account = Account.objects.create(
            email="device-command@example.com",
            name="Device Command",
            password="pwd",
        )
        self.room = DeviceRoom.objects.create(
            account=self.account,
            slug="living-room",
            name="客厅",
            climate="26°C",
            summary="测试房间",
            sort_order=10,
        )
        self.device = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="ha:ac-1",
            room=self.room,
            name="空调",
            category="空调",
            status=DeviceSnapshot.StatusChoices.ONLINE,
            telemetry="制冷",
            capabilities=["temperature"],
            sort_order=10,
        )
        self.control = DeviceControl.objects.create(
            account=self.account,
            device=self.device,
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

    def test_relative_temperature_value_is_resolved_from_current_value(self):
        action, value = DeviceCommandService._build_execution_payload(
            self.control,
            "set_property",
            {"value": "+1"},
        )
        self.assertEqual(action, "set_property")
        self.assertEqual(value, 27)

    def test_resolve_device_target_matches_chinese_temperature_alias(self):
        resolved = asyncio.run(
            DeviceCommandService.resolve_device_target(
                self.account,
                {
                    "type": "DEVICE_CONTROL",
                    "room": "客厅",
                    "device": "空调",
                    "control_key": "温度",
                    "value": 24,
                },
            )
        )
        self.assertEqual(resolved["matched_control"].external_id, self.control.external_id)
        self.assertFalse(resolved["ambiguous"])

    def test_resolve_device_target_uses_payload_hints_when_top_level_missing(self):
        resolved = asyncio.run(
            DeviceCommandService.resolve_device_target(
                self.account,
                {
                    "type": "DEVICE_CONTROL",
                    "room": "客厅",
                    "device": "空调",
                    "control_key": "",
                    "action": "",
                    "value": None,
                    "payload_hints": {
                        "control_key": "temperature",
                        "action": "set_property",
                        "value": "+1",
                    },
                },
            )
        )

        self.assertEqual(resolved["matched_control"].external_id, self.control.external_id)
        self.assertFalse(resolved["ambiguous"])

    def test_execute_device_query_prefers_single_device_refresh(self):
        with patch.object(
            DeviceDashboardService,
            "refresh_device",
            return_value={"snapshot": {"devices": []}},
        ) as mocked_refresh:
            result = asyncio.run(
                DeviceCommandService.execute_device_query(
                    {"matched_device": self.control.device, "matched_control": self.control},
                    account=self.account,
                )
            )
        mocked_refresh.assert_called_once_with(
            self.account,
            device_external_id=self.control.device.external_id,
            trigger="query",
        )
        self.assertIn("当前为 26 °C", result["message"])

    def test_build_execution_payload_accepts_action_inside_operation_value_dict(self):
        action, value = DeviceCommandService._build_execution_payload(
            self.control,
            "",
            {"action": "set_property", "value": "+1"},
        )
        self.assertEqual(action, "set_property")
        self.assertEqual(value, 27)

    def test_execute_device_query_formats_toggle_values_as_chinese_state(self):
        toggle_device = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="ha:light-1",
            room=self.control.device.room,
            name="床头灯",
            category="灯",
            status=DeviceSnapshot.StatusChoices.ONLINE,
            telemetry="开启",
            capabilities=["power"],
            sort_order=20,
        )
        toggle_control = DeviceControl.objects.create(
            account=self.account,
            device=toggle_device,
            external_id="ha:light-1:power",
            parent_external_id="ha:light-1:power",
            source_type=DeviceControl.SourceTypeChoices.HA_ENTITY,
            kind=DeviceControl.KindChoices.TOGGLE,
            key="light.bedroom:power",
            label="电源",
            writable=True,
            value="off",
            sort_order=20,
        )
        with patch.object(DeviceDashboardService, "refresh_device", side_effect=RuntimeError("skip refresh")):
            result = asyncio.run(
                DeviceCommandService.execute_device_query(
                    {"matched_device": toggle_device, "matched_control": toggle_control},
                    account=self.account,
                )
            )
        self.assertEqual(result["message"], "床头灯 的 电源 当前为 关闭")

    def test_heuristic_device_intent_detects_mercedes_fuel_query(self):
        result = _heuristic_parse_device_intent("我的奔驰油量是多少", command_mode=False)

        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "DEVICE_QUERY")
        self.assertEqual(result["device"], "奔驰")
        self.assertEqual(result["control_key"], "tanklevelpercent")

    def test_heuristic_device_intent_detects_car_fuel_query(self):
        result = _heuristic_parse_device_intent("我的车油量是多少", command_mode=False)

        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "DEVICE_QUERY")
        self.assertEqual(result["device"], "车")
        self.assertEqual(result["control_key"], "tanklevelpercent")

    def test_resolve_device_target_matches_mercedes_vehicle_fuel_query(self):
        vehicle = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="mbapi2020:VIN123456",
            room=self.room,
            name="E 300 L 豪华型轿车",
            category="vehicle",
            status=DeviceSnapshot.StatusChoices.ONLINE,
            telemetry="车牌 川GPT032",
            note="VIN: VIN123456",
            capabilities=["tanklevelpercent"],
            source_payload={"license_plate": "川GPT032", "vin": "VIN123456"},
            sort_order=30,
        )
        fuel_control = DeviceControl.objects.create(
            account=self.account,
            device=vehicle,
            external_id="mbapi2020:VIN123456:status:tanklevelpercent",
            parent_external_id="mbapi2020:VIN123456",
            source_type=DeviceControl.SourceTypeChoices.MBAPI2020_PROPERTY,
            kind=DeviceControl.KindChoices.SENSOR,
            key="tanklevelpercent",
            label="油量",
            writable=False,
            value=68,
            unit="%",
            sort_order=30,
        )

        resolved = asyncio.run(
            DeviceCommandService.resolve_device_target(
                self.account,
                {
                    "type": "DEVICE_QUERY",
                    "room": "",
                    "device": "奔驰",
                    "control_key": "tanklevelpercent",
                },
            )
        )

        self.assertEqual(resolved["matched_device"].external_id, vehicle.external_id)
        self.assertEqual(resolved["matched_control"].external_id, fuel_control.external_id)
        self.assertFalse(resolved["ambiguous"])

    def test_execute_device_operation_returns_offline_error_with_alternative(self):
        self.device.status = DeviceSnapshot.StatusChoices.OFFLINE
        self.device.telemetry = "离线"
        self.device.save(update_fields=["status", "telemetry", "updated_at"])
        spare = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="ha:ac-2",
            room=self.room,
            name="备用空调",
            category="空调",
            status=DeviceSnapshot.StatusChoices.ONLINE,
            telemetry="制冷",
            capabilities=["temperature"],
            sort_order=20,
        )
        DeviceControl.objects.create(
            account=self.account,
            device=spare,
            external_id="ha:ac-2:temperature",
            parent_external_id="ha:ac-2:temperature",
            source_type=DeviceControl.SourceTypeChoices.HA_ENTITY,
            kind=DeviceControl.KindChoices.RANGE,
            key="climate.spare_ac:target_temperature",
            label="空调 目标温度",
            writable=True,
            value=25,
            unit="°C",
            range_spec={"min": 16, "max": 30, "step": 1},
            sort_order=20,
        )

        result = asyncio.run(
            DeviceCommandService.execute_device_operation(
                self.account,
                control_id=self.control.external_id,
                operation_action="set_property",
                operation_value={"value": 24},
            )
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "DEVICE_OFFLINE")
        self.assertIn("备用空调", result["suggestion"])

    def test_device_executor_normalizes_auth_expired_errors(self):
        with patch.object(
            DeviceDashboardService,
            "execute_control",
            side_effect=ValueError("No active Home Assistant authorization found"),
        ):
            result = DeviceExecutor.execute(
                self.account,
                control=self.control,
                action="set_property",
                value=24,
            )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "AUTH_EXPIRED")
        self.assertIn("重新登录", result["message"])

