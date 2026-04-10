import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import django


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wanny_server.settings")
django.setup()

from accounts.models import Account
from comms.services import WeChatService
from devices.models import DeviceControl, DeviceRoom, DeviceSnapshot
from providers.models import PlatformAuth
from tests.scripts.wechat_device_command_smoke import ensure_required_schema, reset_fixture


class FakeBot:
    def __init__(self):
        self.replies = []

    async def reply(self, _message, text):
        self.replies.append(text)


class FakeMessage(SimpleNamespace):
    def __init__(self, text="", user_id="wx-user-1", voices=None):
        super().__init__(text=text, user_id=user_id, voices=voices or [])


def build_fixture():
    account, _ = Account.objects.get_or_create(
        email="script-mijia-voice@example.com",
        defaults={"name": "Script Mijia Voice", "password": "pwd"},
    )
    PlatformAuth.objects.update_or_create(
        account=account,
        platform_name="wechat",
        defaults={"auth_payload": {"user_id": "wx-user-1"}, "is_active": True},
    )
    reset_fixture(account)

    room = DeviceRoom.objects.create(
        account=account,
        slug="living-room",
        name="客厅",
        climate="26°C",
        summary="测试房间",
        sort_order=10,
    )
    device = DeviceSnapshot.objects.create(
        account=account,
        external_id="mijia:light-1",
        room=room,
        name="主灯",
        category="灯",
        status=DeviceSnapshot.StatusChoices.ONLINE,
        telemetry="开启",
        capabilities=["power"],
        sort_order=10,
    )
    control = DeviceControl.objects.create(
        account=account,
        device=device,
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
    return account, device, control


async def main(account, device, control):
    bot = FakeBot()
    message = FakeMessage(text="", user_id="wx-user-1", voices=[SimpleNamespace(text="jarvis，把客厅主灯关了")])

    with patch("comms.services.WeChatService.get_account_by_wechat_id", new=AsyncMock(return_value=account)), patch(
        "comms.services.MemoryService.record_conversation",
        new=AsyncMock(),
    ), patch(
        "comms.services.MemoryService.get_context_for_chat",
        new=AsyncMock(return_value=""),
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
                "matched_device": device,
                "matched_control": control,
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
        await WeChatService.process_incoming_message(message, bot)

    if not bot.replies or bot.replies[-1] != "好的，正在关闭客厅主灯":
        raise AssertionError(f"Unexpected MiJia voice reply: {bot.replies[-1] if bot.replies else 'no reply'}")
    print("✅ MiJia voice command smoke test passed")
    print(f"Reply: {bot.replies[-1]}")


if __name__ == "__main__":
    try:
        ensure_required_schema()
        fixture = build_fixture()
        asyncio.run(main(*fixture))
    except RuntimeError as error:
        print(f"❌ {error}")
        raise SystemExit(1) from error
