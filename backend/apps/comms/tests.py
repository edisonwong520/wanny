import json
import os
import tempfile
import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from django.test import TestCase, TransactionTestCase
from django.test.client import RequestFactory
from django.utils import timezone

from accounts.models import Account
from comms.device_command_service import DeviceCommandService
from comms.device_intent import analyze_device_intent
from comms.models import DeviceOperationContext, Mission
from comms.serializers import MissionSerializer
from comms.views import handle_mission_approve
from devices.executor import DeviceExecutor
from devices.services import DeviceDashboardService
from devices.models import DeviceControl, DeviceRoom, DeviceSnapshot
from providers.models import PlatformAuth

from .management.commands.runwechatbot import Command
from .services import WeChatService


class RunWeChatBotCommandTest(TestCase):
    def test_prepare_wechat_credentials_waits_until_platform_auth_has_wechat_payload(self):
        command = Command()
        command.auth_poll_interval_seconds = 0
        command.auth_wait_log_interval_seconds = 999

        with tempfile.TemporaryDirectory() as temp_dir:
            cred_file = os.path.join(temp_dir, "wechat_credentials.json")
            with open(cred_file, "w", encoding="utf-8") as f:
                json.dump({"stale": True}, f)

            sleep_calls = {"count": 0}

            def fake_sleep(_seconds):
                sleep_calls["count"] += 1
                if sleep_calls["count"] == 1:
                    account = Account.objects.create(
                        email="wx-bot@example.com",
                        name="WX Bot",
                        password="pwd",
                    )
                    PlatformAuth.objects.create(
                        account=account,
                        platform_name="wechat",
                        auth_payload={"token": "mock-token-123", "user_id": "wxid_edison"},
                        is_active=True,
                    )

            with patch("comms.management.commands.runwechatbot.time.sleep", side_effect=fake_sleep):
                command._prepare_wechat_credentials(cred_file)

            self.assertEqual(sleep_calls["count"], 1)
            with open(cred_file, "r", encoding="utf-8") as f:
                payload = json.load(f)

            self.assertEqual(payload["token"], "mock-token-123")
            self.assertEqual(payload["user_id"], "wxid_edison")


class WeChatDeviceCommandFlowTest(TransactionTestCase):
    def setUp(self):
        self.account = Account.objects.create(
            email="wx-device@example.com",
            name="WX Device",
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

    def test_command_mode_device_control_executes_without_chat_fallback(self):
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
            "comms.services.analyze_intent",
            new=AsyncMock(return_value={"type": "CHAT", "response": "fallback"}),
        ) as mocked_analyze_intent, patch(
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

        self.assertEqual(self.bot.replies[-1], "好的，正在关闭客厅主灯")
        mocked_analyze_intent.assert_not_awaited()
        self.assertEqual(Mission.objects.count(), 0)

    def test_command_mode_unsupported_command_does_not_fallback_to_chat(self):
        message = FakeMessage(text="jarvis, 今天天气怎么样", user_id="wx-user-1")
        with patch("comms.services.WeChatService.get_account_by_wechat_id", new=AsyncMock(return_value=self.account)), patch(
            "comms.services.MemoryService.record_conversation", new=AsyncMock()
        ), patch(
            "comms.services.MemoryService.get_context_for_chat", new=AsyncMock(return_value="")
        ), patch(
            "comms.services.analyze_device_intent",
            new=AsyncMock(
                return_value={
                    "type": "UNSUPPORTED_COMMAND",
                    "response": "这是命令模式，但我还没理解您希望我执行什么操作。",
                }
            ),
        ), patch(
            "comms.services.analyze_intent",
            new=AsyncMock(return_value={"type": "CHAT", "response": "fallback"}),
        ) as mocked_analyze_intent:
            asyncio.run(WeChatService.process_incoming_message(message, self.bot))

        self.assertEqual(self.bot.replies[-1], "这是命令模式，但我还没理解您希望我执行什么操作。")
        mocked_analyze_intent.assert_awaited()

    def test_confirm_device_mission_executes_frozen_plan(self):
        mission = Mission.objects.create(
            account=self.account,
            user_id="wx-user-1",
            original_prompt="jarvis, 把客厅主灯关了",
            source_type=Mission.SourceTypeChoices.DEVICE_CONTROL,
            device_id=self.device.external_id,
            control_id=self.control.external_id,
            control_key=self.control.key,
            operation_action="set_property",
            operation_value={"value": False},
            status=Mission.StatusChoices.PENDING,
            metadata={"intent_json": {"type": "DEVICE_CONTROL", "suggested_reply": "好的，正在关闭客厅主灯"}},
        )
        message = FakeMessage(text="好的", user_id="wx-user-1")
        with patch("comms.services.WeChatService.get_account_by_wechat_id", new=AsyncMock(return_value=self.account)), patch(
            "comms.services.MemoryService.record_conversation", new=AsyncMock()
        ), patch(
            "comms.services.MemoryService.get_context_for_chat", new=AsyncMock(return_value="")
        ), patch(
            "comms.services.analyze_intent",
            new=AsyncMock(return_value={"type": "CONFIRM"}),
        ), patch(
            "comms.services.WeChatService._find_pending_missions",
            new=AsyncMock(return_value=[mission]),
        ), patch(
            "comms.services.DeviceCommandService.execute_device_operation",
            new=AsyncMock(return_value={"success": True, "message": "已执行 主灯 / 电源"}),
        ), patch(
            "comms.services.WeChatService._record_device_context_from_mission",
            return_value=None,
        ):
            asyncio.run(WeChatService.process_incoming_message(message, self.bot))

        mission = Mission.objects.get()
        self.assertEqual(mission.status, Mission.StatusChoices.APPROVED)
        self.assertEqual(self.bot.replies[-1], "好的，正在关闭客厅主灯")

    def test_device_result_reply_includes_alternative_suggestion(self):
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
            new=AsyncMock(return_value={
                "success": False,
                "message": "主灯 当前离线，暂时无法操作。",
                "error": "DEVICE_OFFLINE",
                "suggestion": "卧室 的 床头灯 当前在线，您可以试试操作它。",
            }),
        ):
            asyncio.run(WeChatService.process_incoming_message(message, self.bot))

        self.assertIn("可选方案：卧室 的 床头灯 当前在线", self.bot.replies[-1])

    def test_ambiguous_device_command_creates_clarification_mission(self):
        bedroom = DeviceRoom.objects.create(
            account=self.account,
            slug="bedroom",
            name="卧室",
            climate="25°C",
            summary="卧室",
            sort_order=20,
        )
        bedroom_device = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="mijia:light-2",
            room=bedroom,
            name="主灯",
            category="灯",
            status=DeviceSnapshot.StatusChoices.ONLINE,
            telemetry="开启",
            capabilities=["power"],
            source_payload={"did": "456"},
            sort_order=20,
        )
        bedroom_control = DeviceControl.objects.create(
            account=self.account,
            device=bedroom_device,
            external_id="mijia:light-2:power",
            parent_external_id="mijia:light-2:power",
            source_type=DeviceControl.SourceTypeChoices.MIJIA_PROPERTY,
            kind=DeviceControl.KindChoices.TOGGLE,
            key="power",
            label="电源",
            writable=True,
            value="on",
            sort_order=20,
        )
        message = FakeMessage(text="jarvis, 把主灯关了", user_id="wx-user-1")
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
                            "device_id": self.device.external_id,
                            "control_id": self.control.external_id,
                        },
                        {
                            "room": "卧室",
                            "device": "主灯",
                            "control": "电源",
                            "device_id": bedroom_device.external_id,
                            "control_id": bedroom_control.external_id,
                        },
                    ],
                }
            ),
        ):
            asyncio.run(WeChatService.process_incoming_message(message, self.bot))

        mission = Mission.objects.get(source_type=Mission.SourceTypeChoices.DEVICE_CLARIFICATION)
        self.assertEqual(mission.status, Mission.StatusChoices.PENDING)
        self.assertIn("1. 客厅 / 主灯 / 电源", self.bot.replies[-1])
        self.assertIn("2. 卧室 / 主灯 / 电源", self.bot.replies[-1])

    def test_voice_ambiguous_device_command_echoes_transcript_before_clarification(self):
        message = FakeMessage(text="", user_id="wx-user-1", voices=[SimpleNamespace(text="jarvis，把主灯关了")])
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
                            "device_id": self.device.external_id,
                            "control_id": self.control.external_id,
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
            asyncio.run(WeChatService.process_incoming_message(message, self.bot))

        self.assertIn("我听到的是：\"jarvis，把主灯关了\"", self.bot.replies[-1])
        self.assertIn("请直接回复编号或设备名", self.bot.replies[-1])

    def test_repeated_ambiguous_command_reuses_existing_clarification_mission(self):
        message = FakeMessage(text="jarvis, 把主灯关了", user_id="wx-user-1")
        resolved_payload = {
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
                    "device_id": self.device.external_id,
                    "control_id": self.control.external_id,
                }
            ],
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
                    "device": "主灯",
                    "control_key": "power",
                    "value": False,
                }
            ),
        ), patch(
            "comms.services.DeviceCommandService.resolve_device_target",
            new=AsyncMock(return_value=resolved_payload),
        ):
            asyncio.run(WeChatService.process_incoming_message(message, self.bot))
            asyncio.run(WeChatService.process_incoming_message(message, self.bot))

        self.assertEqual(
            Mission.objects.filter(source_type=Mission.SourceTypeChoices.DEVICE_CLARIFICATION).count(),
            1,
        )

    def test_clarification_reply_selects_candidate_and_executes(self):
        clarification = Mission.objects.create(
            account=self.account,
            user_id="wx-user-1",
            original_prompt="jarvis, 把主灯关了",
            source_type=Mission.SourceTypeChoices.DEVICE_CLARIFICATION,
            control_key="power",
            operation_action="set_property",
            operation_value={"value": False},
            status=Mission.StatusChoices.PENDING,
            metadata={
                "intent_json": {"type": "DEVICE_CONTROL", "control_key": "power"},
                "alternatives_snapshot": [
                    {
                        "room": "客厅",
                        "device": "主灯",
                        "control": "电源",
                        "device_id": self.device.external_id,
                        "control_id": self.control.external_id,
                    }
                ],
            },
        )
        message = FakeMessage(text="第一个", user_id="wx-user-1")
        with patch("comms.services.WeChatService.get_account_by_wechat_id", new=AsyncMock(return_value=self.account)), patch(
            "comms.services.MemoryService.record_conversation", new=AsyncMock()
        ), patch(
            "comms.services.MemoryService.get_context_for_chat", new=AsyncMock(return_value="")
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

        clarification.refresh_from_db()
        self.assertEqual(clarification.status, Mission.StatusChoices.APPROVED)
        self.assertEqual(self.bot.replies[-1], "已执行 主灯 / 电源")

    def test_clarification_cancel_reply_rejects_pending_clarification(self):
        clarification = Mission.objects.create(
            account=self.account,
            user_id="wx-user-1",
            original_prompt="jarvis, 把主灯关了",
            source_type=Mission.SourceTypeChoices.DEVICE_CLARIFICATION,
            control_key="power",
            operation_action="set_property",
            operation_value={"value": False},
            status=Mission.StatusChoices.PENDING,
            metadata={
                "alternatives_snapshot": [
                    {
                        "room": "客厅",
                        "device": "主灯",
                        "control": "电源",
                        "device_id": self.device.external_id,
                        "control_id": self.control.external_id,
                    }
                ],
            },
        )
        message = FakeMessage(text="都不是", user_id="wx-user-1")
        with patch("comms.services.WeChatService.get_account_by_wechat_id", new=AsyncMock(return_value=self.account)), patch(
            "comms.services.MemoryService.record_conversation", new=AsyncMock()
        ), patch(
            "comms.services.MemoryService.get_context_for_chat", new=AsyncMock(return_value="")
        ):
            asyncio.run(WeChatService.process_incoming_message(message, self.bot))

        clarification.refresh_from_db()
        self.assertEqual(clarification.status, Mission.StatusChoices.REJECTED)
        self.assertIn("这次设备选择我先取消了", self.bot.replies[-1])

    def test_clarification_unknown_reply_prompts_again(self):
        clarification = Mission.objects.create(
            account=self.account,
            user_id="wx-user-1",
            original_prompt="jarvis, 把主灯关了",
            source_type=Mission.SourceTypeChoices.DEVICE_CLARIFICATION,
            control_key="power",
            operation_action="set_property",
            operation_value={"value": False},
            status=Mission.StatusChoices.PENDING,
            metadata={
                "alternatives_snapshot": [
                    {
                        "room": "客厅",
                        "device": "主灯",
                        "control": "电源",
                        "device_id": self.device.external_id,
                        "control_id": self.control.external_id,
                    },
                    {
                        "room": "卧室",
                        "device": "主灯",
                        "control": "电源",
                        "device_id": "mijia:light-2",
                        "control_id": "mijia:light-2:power",
                    },
                ],
            },
        )
        message = FakeMessage(text="嗯嗯", user_id="wx-user-1")
        with patch("comms.services.WeChatService.get_account_by_wechat_id", new=AsyncMock(return_value=self.account)), patch(
            "comms.services.MemoryService.record_conversation", new=AsyncMock()
        ), patch(
            "comms.services.MemoryService.get_context_for_chat", new=AsyncMock(return_value="")
        ):
            asyncio.run(WeChatService.process_incoming_message(message, self.bot))

        clarification.refresh_from_db()
        self.assertEqual(clarification.status, Mission.StatusChoices.PENDING)
        self.assertIn("回复编号、房间名，或者直接说“取消”", self.bot.replies[-1])

    def test_stale_clarification_is_cancelled_before_handling(self):
        clarification = Mission.objects.create(
            account=self.account,
            user_id="wx-user-1",
            original_prompt="jarvis, 把主灯关了",
            source_type=Mission.SourceTypeChoices.DEVICE_CLARIFICATION,
            control_key="power",
            operation_action="set_property",
            operation_value={"value": False},
            status=Mission.StatusChoices.PENDING,
            metadata={"alternatives_snapshot": []},
        )
        Mission.objects.filter(id=clarification.id).update(
            created_at=timezone.now() - timedelta(minutes=30)
        )
        message = FakeMessage(text="第一个", user_id="wx-user-1")
        with patch("comms.services.WeChatService.get_account_by_wechat_id", new=AsyncMock(return_value=self.account)), patch(
            "comms.services.MemoryService.record_conversation", new=AsyncMock()
        ), patch(
            "comms.services.MemoryService.get_context_for_chat", new=AsyncMock(return_value="")
        ), patch(
            "comms.services.analyze_intent",
            new=AsyncMock(return_value={"type": "CHAT", "response": "目前并没有找到需要您授权操作的任务。"}),
        ):
            asyncio.run(WeChatService.process_incoming_message(message, self.bot))

        clarification.refresh_from_db()
        self.assertEqual(clarification.status, Mission.StatusChoices.CANCELLED)

    def test_repeated_confirm_required_device_command_reuses_existing_pending_mission(self):
        message = FakeMessage(text="jarvis, 把客厅主灯关了", user_id="wx-user-1")
        resolved_payload = {
            "matched_device": self.device,
            "matched_control": self.control,
            "confidence": 0.7,
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
            asyncio.run(WeChatService.process_incoming_message(message, self.bot))

        self.assertEqual(
            Mission.objects.filter(source_type=Mission.SourceTypeChoices.DEVICE_CONTROL).count(),
            1,
        )

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

        self.assertIn("我听到的是：\"jarvis，把客厅主灯关了\"", self.bot.replies[-1])
        self.assertIn("请确认是否执行", self.bot.replies[-1])

    def test_create_shell_mission_reuses_existing_pending_mission(self):
        first = WeChatService.create_shell_mission(
            account=self.account,
            wechat_user_id="wx-user-1",
            raw_content="jarvis, 帮我查明天上海天气",
            shell_command="curl wttr.in/Shanghai",
            metadata={"title": "天气查询"},
        )
        second = WeChatService.create_shell_mission(
            account=self.account,
            wechat_user_id="wx-user-1",
            raw_content="jarvis, 帮我查明天上海天气",
            shell_command="curl wttr.in/Shanghai?format=3",
            metadata={"title": "天气查询2"},
        )
        self.assertEqual(first.id, second.id)
        self.assertEqual(
            Mission.objects.filter(source_type=Mission.SourceTypeChoices.SHELL).count(),
            1,
        )
        second.refresh_from_db()
        self.assertEqual(second.shell_command, "curl wttr.in/Shanghai?format=3")

    def test_mission_metadata_contains_built_summary_fields(self):
        shell = WeChatService.create_shell_mission(
            account=self.account,
            wechat_user_id="wx-user-1",
            raw_content="jarvis, 帮我查明天上海天气",
            shell_command="curl wttr.in/Shanghai",
            metadata=WeChatService._build_shell_mission_metadata(
                raw_content="jarvis, 帮我查明天上海天气",
                shell_command="curl wttr.in/Shanghai",
                incoming_metadata={},
                confirm_text="我需要联网查询天气，是否继续？",
            ),
        )
        device_mission = WeChatService.create_device_mission(
            account=self.account,
            wechat_user_id="wx-user-1",
            raw_content="jarvis, 把客厅主灯关了",
            normalized_content="把客厅主灯关了",
            voice_transcript="",
            intent={
                "type": "DEVICE_CONTROL",
                "action": "set_property",
                "value": False,
            },
            resolved={
                "matched_device": self.device,
                "matched_control": self.control,
                "confidence": 1.0,
                "ambiguous": False,
                "resolved_from_context": False,
                "alternatives": [],
            },
        )

        self.assertEqual(shell.metadata["title"], "Shell 指令待审批")
        self.assertIn("confirm_message", shell.metadata)
        self.assertEqual(device_mission.metadata["title"], "设备控制待确认")
        self.assertIn("主灯 / 电源 -> False", device_mission.metadata["summary"])
        self.assertIn("confirm_message", device_mission.metadata)

    def test_repeated_complex_shell_message_reuses_existing_pending_shell_mission(self):
        message = FakeMessage(text="jarvis, 帮我查明天上海天气", user_id="wx-user-1")
        with patch("comms.services.WeChatService.get_account_by_wechat_id", new=AsyncMock(return_value=self.account)), patch(
            "comms.services.MemoryService.record_conversation", new=AsyncMock()
        ), patch(
            "comms.services.MemoryService.get_context_for_chat", new=AsyncMock(return_value="")
        ), patch(
            "comms.services.analyze_device_intent",
            new=AsyncMock(return_value={"type": "UNSUPPORTED_COMMAND", "response": "不是设备命令"}),
        ), patch(
            "comms.services.analyze_intent",
            new=AsyncMock(
                return_value={
                    "type": "COMPLEX_SHELL",
                    "shell_prompt": "curl wttr.in/Shanghai",
                    "confirm_text": "我需要联网查询天气，是否继续？",
                    "metadata": {"title": "天气查询"},
                }
            ),
        ):
            asyncio.run(WeChatService.process_incoming_message(message, self.bot))
            asyncio.run(WeChatService.process_incoming_message(message, self.bot))

        self.assertEqual(
            Mission.objects.filter(source_type=Mission.SourceTypeChoices.SHELL).count(),
            1,
        )

    def test_multi_pending_prefers_most_recent_mission_when_gap_is_clear(self):
        older = Mission.objects.create(
            account=self.account,
            user_id="wx-user-1",
            original_prompt="jarvis, 帮我查天气",
            source_type=Mission.SourceTypeChoices.SHELL,
            shell_command="curl wttr.in/Shanghai",
            status=Mission.StatusChoices.PENDING,
            metadata={},
        )
        latest = Mission.objects.create(
            account=self.account,
            user_id="wx-user-1",
            original_prompt="jarvis, 把客厅主灯关了",
            source_type=Mission.SourceTypeChoices.DEVICE_CONTROL,
            device_id=self.device.external_id,
            control_id=self.control.external_id,
            control_key=self.control.key,
            operation_action="set_property",
            operation_value={"value": False},
            status=Mission.StatusChoices.PENDING,
            metadata={"intent_json": {"type": "DEVICE_CONTROL"}},
        )
        Mission.objects.filter(id=older.id).update(created_at=timezone.now() - timedelta(minutes=10))
        Mission.objects.filter(id=latest.id).update(created_at=timezone.now())

        message = FakeMessage(text="好的", user_id="wx-user-1")
        with patch("comms.services.WeChatService.get_account_by_wechat_id", new=AsyncMock(return_value=self.account)), patch(
            "comms.services.MemoryService.record_conversation", new=AsyncMock()
        ), patch(
            "comms.services.MemoryService.get_context_for_chat", new=AsyncMock(return_value="")
        ), patch(
            "comms.services.analyze_intent",
            new=AsyncMock(return_value={"type": "CONFIRM"}),
        ), patch(
            "comms.services.DeviceCommandService.execute_device_operation",
            new=AsyncMock(return_value={"success": True, "message": "已执行 主灯 / 电源"}),
        ), patch(
            "comms.services.WeChatService._record_device_context_from_mission",
            return_value=None,
        ):
            asyncio.run(WeChatService.process_incoming_message(message, self.bot))

        latest.refresh_from_db()
        older.refresh_from_db()
        self.assertEqual(latest.status, Mission.StatusChoices.APPROVED)
        self.assertEqual(older.status, Mission.StatusChoices.PENDING)
        self.assertEqual(self.bot.replies[-1], "已执行 主灯 / 电源")

    def test_multi_pending_with_close_timestamps_still_asks_for_clarification(self):
        Mission.objects.create(
            account=self.account,
            user_id="wx-user-1",
            original_prompt="jarvis, 帮我查天气",
            source_type=Mission.SourceTypeChoices.SHELL,
            shell_command="curl wttr.in/Shanghai",
            status=Mission.StatusChoices.PENDING,
            metadata={},
        )
        Mission.objects.create(
            account=self.account,
            user_id="wx-user-1",
            original_prompt="jarvis, 把客厅主灯关了",
            source_type=Mission.SourceTypeChoices.DEVICE_CONTROL,
            device_id=self.device.external_id,
            control_id=self.control.external_id,
            control_key=self.control.key,
            operation_action="set_property",
            operation_value={"value": False},
            status=Mission.StatusChoices.PENDING,
            metadata={"intent_json": {"type": "DEVICE_CONTROL"}},
        )

        message = FakeMessage(text="好的", user_id="wx-user-1")
        with patch("comms.services.WeChatService.get_account_by_wechat_id", new=AsyncMock(return_value=self.account)), patch(
            "comms.services.MemoryService.record_conversation", new=AsyncMock()
        ), patch(
            "comms.services.MemoryService.get_context_for_chat", new=AsyncMock(return_value="")
        ), patch(
            "comms.services.analyze_intent",
            new=AsyncMock(return_value={"type": "CONFIRM"}),
        ):
            asyncio.run(WeChatService.process_incoming_message(message, self.bot))

        self.assertIn("同时有多条待确认任务", self.bot.replies[-1])

    def test_empty_voice_transcript_replies_with_retry_hint(self):
        message = FakeMessage(text="", user_id="wx-user-1", voices=[SimpleNamespace(text="")])
        asyncio.run(WeChatService.process_incoming_message(message, self.bot))
        self.assertEqual(
            self.bot.replies[-1],
            "这条语音我没有识别清楚。您可以再说一次，或者直接发文字命令。",
        )

    def test_low_signal_voice_text_is_blocked_before_command_flow(self):
        message = FakeMessage(text="", user_id="wx-user-1", voices=[SimpleNamespace(text="嗯")])
        with patch("comms.services.WeChatService.get_account_by_wechat_id", new=AsyncMock(return_value=self.account)), patch(
            "comms.services.MemoryService.record_conversation", new=AsyncMock()
        ), patch(
            "comms.services.MemoryService.get_context_for_chat", new=AsyncMock(return_value="")
        ), patch(
            "comms.services.analyze_device_intent",
            new=AsyncMock(),
        ) as mocked_device_intent:
            asyncio.run(WeChatService.process_incoming_message(message, self.bot))

        self.assertIn("识别结果太短了", self.bot.replies[-1])
        mocked_device_intent.assert_not_awaited()


class DeviceIntentHeuristicTest(TransactionTestCase):
    def setUp(self):
        self.account = Account.objects.create(
            email="intent@example.com",
            name="Intent Test",
            password="pwd",
        )
        room = DeviceRoom.objects.create(
            account=self.account,
            slug="living-room",
            name="客厅",
            climate="26°C",
            summary="测试房间",
            sort_order=10,
        )
        device = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="ha:ac-1",
            room=room,
            name="空调",
            category="空调",
            status=DeviceSnapshot.StatusChoices.ONLINE,
            telemetry="制冷",
            capabilities=["temperature"],
            sort_order=10,
        )
        self.control = DeviceControl.objects.create(
            account=self.account,
            device=device,
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

    def test_heuristic_parse_temperature_command(self):
        result = asyncio.run(
            analyze_device_intent("把客厅空调调到24度", self.account, command_mode=True)
        )
        self.assertEqual(result["type"], "DEVICE_CONTROL")


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

    def test_execute_device_query_prefers_single_device_refresh(self):
        with patch.object(
            DeviceDashboardService,
            "refresh_device",
            return_value={"snapshot": {"devices": []}},
        ) as mocked_refresh:
            result = asyncio.run(
                DeviceCommandService.execute_device_query(
                    {"matched_device": self.control.device, "matched_control": self.control}
                )
            )
        mocked_refresh.assert_called_once_with(
            self.account,
            device_external_id=self.control.device.external_id,
            trigger="query",
        )
        self.assertIn("当前为 26 °C", result["message"])

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
                    {"matched_device": toggle_device, "matched_control": toggle_control}
                )
            )
        self.assertEqual(result["message"], "床头灯 的 电源 当前为 关闭")

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


class FakeBot:
    def __init__(self):
        self.replies = []

    async def reply(self, _message, text):
        self.replies.append(text)


class FakeMessage(SimpleNamespace):
    def __init__(self, text="", user_id="wx-user-1", voices=None):
        super().__init__(text=text, user_id=user_id, voices=voices or [])
