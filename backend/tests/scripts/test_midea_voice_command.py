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
from tests.scripts.test_wechat_device_command import ensure_required_schema, reset_fixture


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
        email="script-midea-voice@example.com",
        defaults={"name": "Script Midea Voice", "password": "pwd"},
    )
    PlatformAuth.objects.update_or_create(
        account=account,
        platform_name="wechat",
        defaults={"auth_payload": {"user_id": "wx-user-1"}, "is_active": True},
    )
    reset_fixture(account)

    room = DeviceRoom.objects.create(
        account=account,
        slug="bedroom",
        name="卧室",
        climate="25°C",
        summary="测试房间",
        sort_order=10,
    )
    device = DeviceSnapshot.objects.create(
        account=account,
        external_id="midea:ac-1",
        room=room,
        name="空调",
        category="空调",
        status=DeviceSnapshot.StatusChoices.ONLINE,
        telemetry="制冷",
        capabilities=["temperature"],
        sort_order=10,
    )
    control = DeviceControl.objects.create(
        account=account,
        device=device,
        external_id="midea:ac-1:temperature",
        parent_external_id="midea:ac-1:temperature",
        source_type=DeviceControl.SourceTypeChoices.MIDEA_CLOUD_PROPERTY,
        kind=DeviceControl.KindChoices.RANGE,
        key="temperature",
        label="目标温度",
        writable=True,
        value=26,
        unit="°C",
        range_spec={"min": 16, "max": 30, "step": 1},
        sort_order=10,
    )
    return account, device, control


async def main(account, device, control):
    bot = FakeBot()
    message = FakeMessage(text="", user_id="wx-user-1", voices=[SimpleNamespace(text="jarvis，把卧室空调调到24度")])

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
                "room": "卧室",
                "device": "空调",
                "control_key": "temperature",
                "value": 24,
                "unit": "°C",
                "suggested_reply": "好的，正在把卧室空调调到 24 度",
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
        new=AsyncMock(return_value={"success": True, "message": "已执行 空调 / 目标温度"}),
    ), patch(
        "comms.services.DeviceContextManager.record_operation",
        return_value=None,
    ):
        await WeChatService.process_incoming_message(message, bot)

    if not bot.replies or "24 度" not in bot.replies[-1]:
        raise AssertionError(f"Unexpected Midea voice reply: {bot.replies[-1] if bot.replies else 'no reply'}")
    print("✅ Midea voice command smoke test passed")
    print(f"Reply: {bot.replies[-1]}")


if __name__ == "__main__":
    try:
        ensure_required_schema()
        fixture = build_fixture()
        asyncio.run(main(*fixture))
    except RuntimeError as error:
        print(f"❌ {error}")
        raise SystemExit(1) from error
