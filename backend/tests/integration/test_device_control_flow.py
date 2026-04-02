import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from django.test import TransactionTestCase
from django.utils import timezone

from accounts.models import Account
from comms.models import Mission
from comms.services import WeChatService
from devices.models import DeviceControl, DeviceRoom, DeviceSnapshot
from providers.models import PlatformAuth


class FakeBot:
    def __init__(self):
        self.replies = []

    async def reply(self, _message, text):
        self.replies.append(text)


class FakeMessage:
    def __init__(self, text="", user_id="wx-user-1", voices=None):
        self.text = text
        self.user_id = user_id
        self.voices = voices or []


class DeviceControlFlowIntegrationTest(TransactionTestCase):
    def setUp(self):
        self.account = Account.objects.create(
            email="integration-device-flow@example.com",
            name="Integration Device Flow",
            password="pwd",
        )
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="wechat",
            auth_payload={"user_id": "wx-user-1"},
            is_active=True,
        )
        self.room = DeviceRoom.objects.create(
            account=self.account,
            slug="living-room",
            name="客厅",
            climate="26°C",
            summary="客厅",
            sort_order=10,
        )
        self.device = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="mijia:light-1",
            room=self.room,
            name="主灯",
            category="灯",
            status=DeviceSnapshot.StatusChoices.ONLINE,
            telemetry="开启",
            capabilities=["power"],
            source_payload={"did": "123"},
            sort_order=10,
        )
        self.control = DeviceControl.objects.create(
            account=self.account,
            device=self.device,
            external_id="mijia:light-1:power",
            parent_external_id="mijia:light-1:power",
            source_type=DeviceControl.SourceTypeChoices.MIJIA_PROPERTY,
            kind=DeviceControl.KindChoices.TOGGLE,
            key="power",
            label="电源",
            writable=True,
            value="on",
            sort_order=10,
        )
        self.bot = FakeBot()

    def _common_patches(self):
        return [
            patch("comms.services.WeChatService.get_account_by_wechat_id", new=AsyncMock(return_value=self.account)),
            patch("comms.services.MemoryService.record_conversation", new=AsyncMock()),
            patch("comms.services.MemoryService.get_context_for_chat", new=AsyncMock(return_value="")),
        ]

    def test_confirm_required_device_command_creates_and_approves_mission(self):
        first_message = FakeMessage(text="jarvis, 把客厅主灯关了")
        confirm_message = FakeMessage(text="好的")
        resolved_payload = {
            "matched_device": self.device,
            "matched_control": self.control,
            "confidence": 0.7,
            "ambiguous": False,
            "resolved_from_context": False,
            "alternatives": [],
        }

        patches = self._common_patches() + [
            patch(
                "comms.services.analyze_device_intent",
                new=AsyncMock(
                    return_value={
                        "type": "DEVICE_CONTROL",
                        "action": "set_property",
                        "room": "客厅",
                        "device": "主灯",
                        "control_key": "power",
                        "value": False,
                        "suggested_reply": "好的，正在关闭客厅主灯",
                    }
                ),
            ),
            patch(
                "comms.services.DeviceCommandService.resolve_device_target",
                new=AsyncMock(return_value=resolved_payload),
            ),
            patch(
                "comms.services.DeviceCommandService.check_authorization",
                new=AsyncMock(return_value={"allowed": True, "need_confirm": True, "policy": "ASK", "reason": "command_mode"}),
            ),
        ]
        for mocked in patches:
            mocked.start()
        try:
            asyncio.run(WeChatService.process_incoming_message(first_message, self.bot))
        finally:
            for mocked in reversed(patches):
                mocked.stop()

        mission = Mission.objects.get(source_type=Mission.SourceTypeChoices.DEVICE_CONTROL)
        self.assertEqual(mission.status, Mission.StatusChoices.PENDING)
        self.assertEqual(mission.control_id, self.control.external_id)
        self.assertIn("请确认是否执行", self.bot.replies[-1])

        patches = self._common_patches() + [
            patch("comms.services.analyze_intent", new=AsyncMock(return_value={"type": "CONFIRM"})),
            patch("comms.services.WeChatService._find_pending_missions", new=AsyncMock(return_value=[mission])),
            patch(
                "comms.services.DeviceCommandService.execute_device_operation",
                new=AsyncMock(return_value={"success": True, "message": "已执行 主灯 / 电源"}),
            ),
            patch("comms.services.WeChatService._record_device_context_from_mission", return_value=None),
        ]
        for mocked in patches:
            mocked.start()
        try:
            asyncio.run(WeChatService.process_incoming_message(confirm_message, self.bot))
        finally:
            for mocked in reversed(patches):
                mocked.stop()

        mission.refresh_from_db()
        self.assertEqual(mission.status, Mission.StatusChoices.APPROVED)
        self.assertEqual(self.bot.replies[-1], "好的，正在关闭客厅主灯")

    def test_multiple_pending_missions_with_close_timestamps_still_asks_for_clarification(self):
        older = Mission.objects.create(
            account=self.account,
            user_id="wx-user-1",
            original_prompt="jarvis, 把客厅主灯关了",
            source_type=Mission.SourceTypeChoices.DEVICE_CONTROL,
            device_id=self.device.external_id,
            control_id=self.control.external_id,
            control_key="power",
            operation_action="set_property",
            operation_value={"value": False},
            status=Mission.StatusChoices.PENDING,
        )
        newer = Mission.objects.create(
            account=self.account,
            user_id="wx-user-1",
            original_prompt="jarvis, 把客厅主灯打开",
            source_type=Mission.SourceTypeChoices.SHELL,
            status=Mission.StatusChoices.PENDING,
        )
        Mission.objects.filter(id=older.id).update(created_at=timezone.now() - timedelta(seconds=25))
        Mission.objects.filter(id=newer.id).update(created_at=timezone.now())
        message = FakeMessage(text="好的")

        patches = self._common_patches() + [
            patch("comms.services.analyze_intent", new=AsyncMock(return_value={"type": "CONFIRM"})),
            patch("comms.services.WeChatService._find_pending_missions", new=AsyncMock(return_value=[newer, older])),
        ]
        for mocked in patches:
            mocked.start()
        try:
            asyncio.run(WeChatService.process_incoming_message(message, self.bot))
        finally:
            for mocked in reversed(patches):
                mocked.stop()

        self.assertIn("同时有多条待确认任务", self.bot.replies[-1])

    def test_command_mode_unsupported_device_intent_can_continue_to_shell_analysis(self):
        message = FakeMessage(text="jarvis, 帮我查天气")

        patches = self._common_patches() + [
            patch(
                "comms.services.analyze_device_intent",
                new=AsyncMock(
                    return_value={
                        "type": "UNSUPPORTED_COMMAND",
                        "response": "这是命令模式，但我还没理解您希望我执行什么操作。",
                    }
                ),
            ),
            patch(
                "comms.services.analyze_intent",
                new=AsyncMock(return_value={"type": "COMPLEX_SHELL", "response": "我可以帮您查天气，请确认是否执行。"}),
            ),
        ]
        for mocked in patches:
            mocked.start()
        try:
            asyncio.run(WeChatService.process_incoming_message(message, self.bot))
        finally:
            for mocked in reversed(patches):
                mocked.stop()

        self.assertIn("准备进行 Shell 操作，请指示", self.bot.replies[-1])
        self.assertEqual(Mission.objects.filter(source_type=Mission.SourceTypeChoices.SHELL).count(), 1)
