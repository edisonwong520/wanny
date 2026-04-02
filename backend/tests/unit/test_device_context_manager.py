from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import Account
from comms.device_context_manager import DeviceContextManager
from comms.models import DeviceOperationContext
from devices.models import DeviceRoom, DeviceSnapshot


class DeviceContextManagerTest(TestCase):
    def setUp(self):
        self.account = Account.objects.create(
            email="unit-device-context@example.com",
            name="Unit Device Context",
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
            external_id="ha:light-1",
            room=self.room,
            name="主灯",
            category="灯",
            status=DeviceSnapshot.StatusChoices.ONLINE,
            telemetry="开启",
            capabilities=["power"],
            sort_order=10,
        )

    def test_get_recent_context_returns_humanized_operated_at(self):
        record = DeviceContextManager.record_operation(
            account=self.account,
            device=self.device,
            control_key="power",
            operation_type="set_property",
            value=False,
        )
        DeviceOperationContext.objects.filter(id=record.id).update(
            operated_at=timezone.now() - timedelta(minutes=2)
        )

        recent = DeviceContextManager.get_recent_context(self.account, limit=1)

        assert recent[0]["room"] == "客厅"
        assert recent[0]["device"] == "主灯"
        assert recent[0]["operated_at"] == "2分钟前"

    def test_get_last_operated_device_returns_latest_device(self):
        DeviceContextManager.record_operation(
            account=self.account,
            device=self.device,
            control_key="power",
            operation_type="set_property",
            value=False,
        )

        latest_device = DeviceContextManager.get_last_operated_device(self.account)

        assert latest_device == self.device
