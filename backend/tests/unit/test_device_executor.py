from unittest.mock import patch

from django.test import TestCase

from accounts.models import Account
from comms.device_command_service import DeviceCommandService
from devices.executor import DeviceExecutor
from devices.models import DeviceControl, DeviceRoom, DeviceSnapshot
from devices.services import DeviceDashboardService


class DeviceExecutorTest(TestCase):
    def setUp(self):
        self.account = Account.objects.create(
            email="unit-device-executor@example.com",
            name="Unit Device Executor",
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

    def test_execute_returns_offline_error_and_alternative_suggestion(self):
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

        result = DeviceExecutor.execute(
            self.account,
            control=self.control,
            action="set_property",
            value=24,
        )

        assert result["success"] is False
        assert result["error"] == "DEVICE_OFFLINE"
        assert "备用空调" in result["suggestion"]

    def test_execute_normalizes_auth_expired_error(self):
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

        assert result["success"] is False
        assert result["error"] == "AUTH_EXPIRED"
        assert "重新登录" in result["message"]

    def test_refresh_single_device_returns_success_payload(self):
        with patch.object(
            DeviceDashboardService,
            "refresh_device",
            return_value={"snapshot": {"devices": []}},
        ) as mocked_refresh:
            result = DeviceExecutor.refresh_single_device(
                self.account,
                device=self.device,
            )

        mocked_refresh.assert_called_once_with(
            self.account,
            device_external_id=self.device.external_id,
            trigger="query",
        )
        assert result["success"] is True
        assert result["error"] is None

    def test_execute_dispatches_home_assistant_controls_explicitly(self):
        with patch.object(
            DeviceExecutor,
            "_execute_home_assistant",
            return_value={"snapshot": {"devices": []}},
        ) as mocked_execute:
            result = DeviceExecutor.execute(
                self.account,
                control=self.control,
                action="set_property",
                value=24,
            )

        mocked_execute.assert_called_once()
        assert result["success"] is True
        assert result["error"] is None

    def test_execute_dispatches_mijia_controls_explicitly(self):
        self.control.source_type = DeviceControl.SourceTypeChoices.MIJIA_PROPERTY
        self.control.save(update_fields=["source_type", "updated_at"])

        with patch.object(
            DeviceExecutor,
            "_execute_mijia",
            return_value={"snapshot": {"devices": []}},
        ) as mocked_execute:
            result = DeviceExecutor.execute(
                self.account,
                control=self.control,
                action="set_property",
                value=24,
            )

        mocked_execute.assert_called_once()
        assert result["success"] is True
        assert result["error"] is None

    def test_execute_dispatches_midea_cloud_controls_explicitly(self):
        self.control.source_type = DeviceControl.SourceTypeChoices.MIDEA_CLOUD_PROPERTY
        self.control.save(update_fields=["source_type", "updated_at"])

        with patch.object(
            DeviceExecutor,
            "_execute_midea_cloud",
            return_value={"snapshot": {"devices": []}},
        ) as mocked_execute:
            result = DeviceExecutor.execute(
                self.account,
                control=self.control,
                action="set_property",
                value=24,
            )

        mocked_execute.assert_called_once()
        assert result["success"] is True
        assert result["error"] is None
