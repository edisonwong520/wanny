import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import django
from django.db import connection


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wanny_server.settings")
django.setup()

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


def reset_fixture(account):
    Mission.objects.filter(account=account).delete()
    DeviceControl.objects.filter(account=account).delete()
    DeviceSnapshot.objects.filter(account=account).delete()
    DeviceRoom.objects.filter(account=account).delete()


def ensure_required_schema():
    existing_tables = set(connection.introspection.table_names())
    required_tables = {
        "comms_mission",
        "comms_device_context",
        "devices_room",
        "devices_snapshot",
        "devices_control",
        "providers_platform_auth",
        "accounts_account",
    }
    missing_tables = sorted(required_tables - existing_tables)
    if missing_tables:
        missing = ", ".join(missing_tables)
        raise RuntimeError(
            f"缺少必要数据表: {missing}。请先执行 `./.venv/bin/python manage.py migrate` 后再运行本脚本。"
        )


def build_fixture():
    account, _ = Account.objects.get_or_create(
        email="script-wechat-device@example.com",
        defaults={"name": "Script WeChat Device", "password": "pwd"},
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
        source_payload={"did": "123"},
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


async def run_smoke_test(account, device, control):
    bot = FakeBot()
    message = FakeMessage(text="jarvis, 把客厅主灯关了", user_id="wx-user-1")

    with patch("comms.services.WeChatService.get_account_by_wechat_id", new=AsyncMock(return_value=account)), patch(
        "comms.services.MemoryService.record_conversation", new=AsyncMock()
    ), patch(
        "comms.services.MemoryService.get_context_for_chat", new=AsyncMock(return_value="")
    ), patch(
        "comms.services.WeChatService._maybe_handle_device_clarification",
        new=AsyncMock(return_value=False),
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

    if not bot.replies:
        raise AssertionError("Bot did not reply to the device command.")
    if bot.replies[-1] != "好的，正在关闭客厅主灯":
        raise AssertionError(f"Unexpected reply: {bot.replies[-1]}")

    print("✅ WeChat device command smoke test passed")
    print(f"Reply: {bot.replies[-1]}")


async def run_voice_confirm_smoke_test(account, device, control):
    bot = FakeBot()
    message = FakeMessage(
        text="",
        user_id="wx-user-1",
        voices=[SimpleNamespace(text="jarvis，把客厅主灯关了")],
    )

    with patch("comms.services.WeChatService.get_account_by_wechat_id", new=AsyncMock(return_value=account)), patch(
        "comms.services.MemoryService.record_conversation", new=AsyncMock()
    ), patch(
        "comms.services.MemoryService.get_context_for_chat", new=AsyncMock(return_value="")
    ), patch(
        "comms.services.WeChatService._maybe_handle_device_clarification",
        new=AsyncMock(return_value=False),
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
        new=AsyncMock(return_value={"allowed": True, "need_confirm": True, "policy": "ASK", "reason": "command_mode"}),
    ):
        await WeChatService.process_incoming_message(message, bot)

    if not bot.replies:
        raise AssertionError("Bot did not reply to the voice confirm command.")
    if "我听到的是：" not in bot.replies[-1]:
        raise AssertionError(f"Voice transcript echo missing: {bot.replies[-1]}")
    if "请确认是否执行" not in bot.replies[-1]:
        raise AssertionError(f"Confirm prompt missing: {bot.replies[-1]}")

    print("✅ WeChat voice confirm smoke test passed")
    print(f"Reply: {bot.replies[-1]}")


async def run_clarification_smoke_test(account, device, control):
    bot = FakeBot()
    message = FakeMessage(text="jarvis, 把主灯关了", user_id="wx-user-1")

    with patch("comms.services.WeChatService.get_account_by_wechat_id", new=AsyncMock(return_value=account)), patch(
        "comms.services.MemoryService.record_conversation", new=AsyncMock()
    ), patch(
        "comms.services.MemoryService.get_context_for_chat", new=AsyncMock(return_value="")
    ), patch(
        "comms.services.WeChatService._maybe_handle_device_clarification",
        new=AsyncMock(return_value=False),
    ), patch(
        "comms.services.analyze_device_intent",
        new=AsyncMock(
            return_value={
                "type": "DEVICE_CONTROL",
                "action": "set_property",
                "device": "主灯",
                "control_key": "power",
                "value": False,
            }
        ),
    ), patch(
        "comms.services.DeviceCommandService.resolve_device_target",
        new=AsyncMock(
            return_value={
                "matched_device": None,
                "matched_control": None,
                "confidence": 0.5,
                "ambiguous": True,
                "resolved_from_context": False,
                "alternatives": [
                    {
                        "room": "客厅",
                        "device": "主灯",
                        "control": "电源",
                        "device_id": device.external_id,
                        "control_id": control.external_id,
                    },
                    {
                        "room": "卧室",
                        "device": "主灯",
                        "control": "电源",
                        "device_id": "mijia:light-2",
                        "control_id": "mijia:light-2:power",
                    },
                ],
            }
        ),
    ):
        await WeChatService.process_incoming_message(message, bot)

    if not bot.replies:
        raise AssertionError("Bot did not reply to the clarification command.")
    if "请直接回复编号或设备名" not in bot.replies[-1]:
        raise AssertionError(f"Clarification prompt missing: {bot.replies[-1]}")
    if "1. 客厅 / 主灯 / 电源" not in bot.replies[-1]:
        raise AssertionError(f"Clarification candidates missing: {bot.replies[-1]}")

    print("✅ WeChat clarification smoke test passed")
    print(f"Reply: {bot.replies[-1]}")


def main():
    ensure_required_schema()
    account, device, control = build_fixture()
    asyncio.run(run_smoke_test(account, device, control))
    asyncio.run(run_voice_confirm_smoke_test(account, device, control))
    asyncio.run(run_clarification_smoke_test(account, device, control))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"❌ {error}")
        raise SystemExit(2)
