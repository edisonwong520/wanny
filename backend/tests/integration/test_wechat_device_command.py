import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from django.test import TransactionTestCase

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


class FakeMessage(SimpleNamespace):
    def __init__(self, text="", user_id="wx-user-1", voices=None):
        super().__init__(text=text, user_id=user_id, voices=voices or [])


class WeChatDeviceCommandIntegrationTest(TransactionTestCase):
    def setUp(self):
        self.account = Account.objects.create(
            email="integration-wechat-device@example.com",
            name="Integration WeChat Device",
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
            summary="测试房间",
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

    def test_command_mode_device_control_uses_suggested_reply(self):
        message = FakeMessage(text="jarvis, 把客厅主灯关了", user_id="wx-user-1")
        with patch("comms.services.WeChatService.get_account_by_wechat_id", new=AsyncMock(return_value=self.account)), patch(
            "comms.services.MemoryService.record_conversation", new=AsyncMock()
        ), patch(
            "comms.services.MemoryService.get_context_for_chat", new=AsyncMock(return_value="")
        ), patch(
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
        ), patch(
            "comms.services.DeviceCommandService.resolve_device_target",
            new=AsyncMock(
                return_value={
                    "matched_device": self.device,
                    "matched_control": self.control,
                    "confidence": 1.0,
                    "ambiguous": False,
                    "resolved_from_context": False,
                    "alternatives": [],
                }
            ),
        ), patch(
            "comms.services.DeviceCommandService.check_authorization",
            new=AsyncMock(return_value={"allowed": True, "need_confirm": False, "policy": "DIRECT", "reason": "command_mode"}),
        ), patch(
            "comms.services.DeviceCommandService.execute_device_operation",
            new=AsyncMock(return_value={"success": True, "message": "已执行 主灯 / 电源"}),
        ), patch(
            "comms.services.DeviceContextManager.record_operation",
            return_value=None,
        ):
            asyncio.run(WeChatService.process_incoming_message(message, self.bot))

        assert self.bot.replies[-1] == "好的，正在关闭客厅主灯"
        assert Mission.objects.count() == 0

    def test_voice_command_needing_confirm_echoes_transcript_before_confirm_prompt(self):
        message = FakeMessage(text="", user_id="wx-user-1", voices=[SimpleNamespace(text="jarvis，把客厅主灯关了")])
        resolved_payload = {
            "matched_device": self.device,
            "matched_control": self.control,
            "confidence": 1.0,
            "ambiguous": False,
            "resolved_from_context": False,
            "alternatives": [],
        }
        with patch("comms.services.WeChatService.get_account_by_wechat_id", new=AsyncMock(return_value=self.account)), patch(
            "comms.services.MemoryService.record_conversation", new=AsyncMock()
        ), patch(
            "comms.services.MemoryService.get_context_for_chat", new=AsyncMock(return_value="")
        ), patch(
            "comms.services.analyze_device_intent",
            new=AsyncMock(
                return_value={
                    "type": "DEVICE_CONTROL",
                    "action": "set_property",
                    "room": "客厅",
                    "device": "主灯",
                    "control_key": "power",
                    "value": False,
                }
            ),
        ), patch(
            "comms.services.DeviceCommandService.resolve_device_target",
            new=AsyncMock(return_value=resolved_payload),
        ), patch(
            "comms.services.DeviceCommandService.check_authorization",
            new=AsyncMock(return_value={"allowed": True, "need_confirm": True, "policy": "ASK", "reason": "command_mode"}),
        ):
            asyncio.run(WeChatService.process_incoming_message(message, self.bot))

        assert "我听到的是：\"jarvis，把客厅主灯关了\"" in self.bot.replies[-1]
        assert "请确认是否执行" in self.bot.replies[-1]
