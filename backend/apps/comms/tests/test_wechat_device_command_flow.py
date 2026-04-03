import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from django.test import TransactionTestCase
from django.utils import timezone

from accounts.models import Account
from comms.models import Mission
from comms.services import WeChatService
from devices.models import DeviceControl, DeviceRoom, DeviceSnapshot
from providers.models import PlatformAuth

from comms.tests.helpers import FakeBot, FakeMessage


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

