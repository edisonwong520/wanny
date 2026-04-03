import json
from unittest.mock import AsyncMock, patch

from django.test import TestCase
from django.test.client import RequestFactory

from accounts.models import Account
from comms.models import DeviceOperationContext, Mission
from comms.serializers import MissionSerializer
from comms.views import handle_mission_approve
from devices.models import DeviceControl, DeviceRoom, DeviceSnapshot


class MissionPresentationTest(TestCase):
    def setUp(self):
        self.account = Account.objects.create(
            email="mission-ui@example.com",
            name="Mission UI",
            password="pwd",
        )
        self.room = DeviceRoom.objects.create(
            account=self.account,
            slug="bedroom",
            name="卧室",
            climate="24°C",
            summary="卧室",
            sort_order=10,
        )
        self.device = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="ha:lamp-1",
            room=self.room,
            name="床头灯",
            category="灯",
            status=DeviceSnapshot.StatusChoices.ONLINE,
            telemetry="开启",
            capabilities=["power"],
            source_payload={"did": "lamp-1"},
            sort_order=10,
        )
        self.control = DeviceControl.objects.create(
            account=self.account,
            device=self.device,
            external_id="ha:lamp-1:power",
            parent_external_id="ha:lamp-1:power",
            source_type=DeviceControl.SourceTypeChoices.HA_ENTITY,
            kind=DeviceControl.KindChoices.TOGGLE,
            key="power",
            label="电源",
            writable=True,
            value="on",
            sort_order=10,
        )
        self.factory = RequestFactory()

    def test_mission_serializer_uses_device_metadata_and_preview(self):
        mission = Mission.objects.create(
            account=self.account,
            user_id="wx-user-1",
            original_prompt="jarvis, 把卧室床头灯关了",
            source_type=Mission.SourceTypeChoices.DEVICE_CONTROL,
            device_id=self.device.external_id,
            control_id=self.control.external_id,
            control_key=self.control.key,
            operation_action="set_property",
            operation_value={"value": False},
            metadata={
                "title": "设备控制待确认",
                "summary": "床头灯 / 电源 -> False",
                "intent": "控制设备 床头灯",
                "source_label": "Manual WeChat Device Command",
                "command_preview": "床头灯 / 电源 -> False",
                "plan": ["核对目标设备", "等待人工审批", "执行设备控制"],
                "suggested_reply": "床头灯 的 电源 已处理。",
                "confirm_message": "请确认是否执行：床头灯 / 电源 -> False。回复“好的”即可执行。",
            },
        )

        payload = MissionSerializer.serialize(mission)

        self.assertEqual(payload["source"], "Manual WeChat Device Command")
        self.assertEqual(payload["commandPreview"], "床头灯 / 电源 -> False")
        self.assertEqual(payload["plan"], ["核对目标设备", "等待人工审批", "执行设备控制"])
        self.assertEqual(payload["confirmMessage"], "请确认是否执行：床头灯 / 电源 -> False。回复“好的”即可执行。")
        self.assertTrue(payload["canApprove"])
        self.assertTrue(payload["canReject"])
        self.assertIn("设备控制任务已创建", payload["timeline"][0]["message"])

    def test_web_approve_executes_device_control_mission(self):
        mission = Mission.objects.create(
            account=self.account,
            user_id="wx-user-1",
            original_prompt="jarvis, 把卧室床头灯关了",
            source_type=Mission.SourceTypeChoices.DEVICE_CONTROL,
            device_id=self.device.external_id,
            control_id=self.control.external_id,
            control_key=self.control.key,
            operation_action="set_property",
            operation_value={"value": False},
            status=Mission.StatusChoices.PENDING,
            metadata={},
        )
        request = self.factory.post(f"/api/comms/missions/{mission.id}/approve/")
        request.account = self.account

        with patch(
            "comms.views.DeviceCommandService.execute_device_operation",
            new=AsyncMock(return_value={"success": True, "message": "已执行 床头灯 / 电源"}),
        ):
            response = handle_mission_approve(request, mission.id)

        mission.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["result"], "已执行 床头灯 / 电源")
        self.assertEqual(mission.status, Mission.StatusChoices.APPROVED)
        self.assertEqual(DeviceOperationContext.objects.filter(account=self.account).count(), 1)
        self.assertEqual((mission.metadata or {}).get("execution_result", {}).get("success"), True)

    def test_mission_serializer_uses_execution_result_for_approved_timeline(self):
        mission = Mission.objects.create(
            account=self.account,
            user_id="wx-user-1",
            original_prompt="jarvis, 把卧室床头灯关了",
            source_type=Mission.SourceTypeChoices.DEVICE_CONTROL,
            status=Mission.StatusChoices.APPROVED,
            metadata={
                "execution_result": {
                    "success": True,
                    "message": "已执行 床头灯 / 电源",
                },
            },
        )

        payload = MissionSerializer.serialize(mission)

        self.assertEqual(payload["resultMessage"], "已执行 床头灯 / 电源")
        self.assertEqual(payload["timeline"][0]["message"], "已执行 床头灯 / 电源")
        self.assertFalse(payload["canApprove"])
        self.assertFalse(payload["canReject"])

    def test_web_approve_rejects_device_clarification_mission(self):
        mission = Mission.objects.create(
            account=self.account,
            user_id="wx-user-1",
            original_prompt="jarvis, 关灯",
            source_type=Mission.SourceTypeChoices.DEVICE_CLARIFICATION,
            status=Mission.StatusChoices.PENDING,
            metadata={},
        )
        request = self.factory.post(f"/api/comms/missions/{mission.id}/approve/")
        request.account = self.account

        response = handle_mission_approve(request, mission.id)

        mission.refresh_from_db()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(mission.status, Mission.StatusChoices.PENDING)

