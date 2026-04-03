import asyncio
import os
from io import StringIO
from unittest.mock import AsyncMock, patch

from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase

from accounts.models import Account
from comms.device_context_manager import DeviceContextManager
from comms.keyword_learner import KeywordLearner
from comms.keyword_loader import KeywordLoader
from comms.models import ChatMessage, DeviceOperationContext, LearnedKeyword
from devices.models import DeviceRoom, DeviceSnapshot


class LearnedKeywordAndLoaderTest(TestCase):
    def setUp(self):
        self.env_patcher = patch.dict(
            os.environ,
            {
                "ENABLE_DYNAMIC_KEYWORDS": "true",
                "ENABLE_HISTORY_KEYWORD_LEARNING": "false",
            },
            clear=False,
        )
        self.env_patcher.start()
        self.account = Account.objects.create(
            email="keyword@example.com",
            name="Keyword Test",
            password="pwd",
        )

    def tearDown(self):
        self.env_patcher.stop()

    def test_global_duplicate_keyword_is_rejected(self):
        LearnedKeyword.objects.create(
            keyword="light",
            normalized_keyword="light",
            canonical="灯",
            category=LearnedKeyword.CategoryChoices.DEVICE,
            source=LearnedKeyword.SourceChoices.SYSTEM,
        )
        with self.assertRaises(IntegrityError):
            LearnedKeyword.objects.create(
                keyword="light",
                normalized_keyword="light",
                canonical="灯",
                category=LearnedKeyword.CategoryChoices.DEVICE,
                source=LearnedKeyword.SourceChoices.SYSTEM,
            )

    def test_keyword_loader_merges_global_and_account_keywords(self):
        LearnedKeyword.objects.create(
            keyword="light",
            normalized_keyword="light",
            canonical="灯",
            category=LearnedKeyword.CategoryChoices.DEVICE,
            source=LearnedKeyword.SourceChoices.SYSTEM,
        )
        LearnedKeyword.objects.create(
            account=self.account,
            keyword="aircon",
            normalized_keyword="aircon",
            canonical="空调",
            canonical_payload={"device": "空调"},
            category=LearnedKeyword.CategoryChoices.DEVICE,
            source=LearnedKeyword.SourceChoices.USER,
        )
        learned_inactive = LearnedKeyword.objects.create(
            account=self.account,
            keyword="bedside",
            normalized_keyword="bedside",
            canonical="床头灯",
            category=LearnedKeyword.CategoryChoices.DEVICE,
            source=LearnedKeyword.SourceChoices.USER,
            is_active=False,
        )

        cache = KeywordLoader._merge_caches(
            KeywordLoader._merge_caches(KeywordLoader.base_cache(), KeywordLoader._load_global_cache_sync()),
            KeywordLoader._load_account_cache_sync(self.account.id),
        )

        self.assertIn("light", cache["devices"])
        self.assertIn("aircon", cache["devices"])
        self.assertNotIn(learned_inactive.normalized_keyword, cache["devices"])
        self.assertEqual(cache["mapping"]["aircon"], "空调")

    def test_keyword_learner_extracts_device_variants(self):
        room = DeviceRoom.objects.create(
            account=self.account,
            slug="living-room",
            name="客厅",
            climate="26°C",
            summary="测试房间",
            sort_order=10,
        )
        DeviceSnapshot.objects.create(
            account=self.account,
            external_id="ha:light-variant",
            room=room,
            name="主灯",
            category="灯",
            status=DeviceSnapshot.StatusChoices.ONLINE,
            telemetry="开启",
            capabilities=["power"],
            sort_order=10,
        )

        created = KeywordLearner._learn_from_devices_sync(self.account.id)
        cache = KeywordLoader._merge_caches(KeywordLoader.base_cache(), KeywordLoader._load_account_cache_sync(self.account.id))

        self.assertGreaterEqual(created, 1)
        self.assertIn("那个主灯", cache["devices"])
        self.assertEqual(cache["mapping"]["那个主灯"], "主灯")

    def test_seed_system_keywords_command_creates_global_records(self):
        out = StringIO()

        call_command("seedsystemkeywords", stdout=out)

        self.assertIn("created=", out.getvalue())
        self.assertTrue(
            LearnedKeyword.objects.filter(
                account__isnull=True,
                source=LearnedKeyword.SourceChoices.SYSTEM,
                normalized_keyword="turnon",
                category=LearnedKeyword.CategoryChoices.ACTION,
            ).exists()
        )

    def test_seed_system_keywords_command_is_idempotent(self):
        call_command("seedsystemkeywords")
        first_count = LearnedKeyword.objects.filter(
            account__isnull=True,
            source=LearnedKeyword.SourceChoices.SYSTEM,
        ).count()

        call_command("seedsystemkeywords")
        second_count = LearnedKeyword.objects.filter(
            account__isnull=True,
            source=LearnedKeyword.SourceChoices.SYSTEM,
        ).count()

        self.assertEqual(first_count, second_count)

    def test_keyword_learner_can_extract_history_keywords_with_ai(self):
        room = DeviceRoom.objects.create(
            account=self.account,
            slug="bedroom",
            name="卧室",
            climate="25°C",
            summary="测试房间",
            sort_order=20,
        )
        device = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="ha:ac-history",
            room=room,
            name="空调",
            category="空调",
            status=DeviceSnapshot.StatusChoices.ONLINE,
            telemetry="制冷",
            capabilities=["temperature"],
            sort_order=20,
        )
        DeviceOperationContext.objects.create(
            account=self.account,
            device=device,
            control_id="ha:ac-history:temperature",
            control_key="temperature",
            operation_type="set_property",
            value=24,
            raw_user_msg="把卧室弄暖和一点",
            normalized_msg="调高卧室温度",
            intent_json={
                "type": "DEVICE_CONTROL",
                "room": "卧室",
                "device": "空调",
                "control_key": "temperature",
                "value": "+1",
            },
            execution_result={"success": True, "message": "ok"},
        )

        with patch.dict(os.environ, {"ENABLE_HISTORY_KEYWORD_LEARNING": "true"}, clear=False), patch(
            "comms.keyword_learner.AIAgent.generate_json",
            new=AsyncMock(
                return_value={
                    "keywords": [
                        {
                            "keyword": "弄暖和一点",
                            "canonical": "调高温度",
                            "category": "action",
                            "canonical_payload": {
                                "control_key": "temperature",
                                "action": "set_property",
                                "value": "+1",
                            },
                            "confidence": 0.88,
                        }
                    ]
                }
            ),
        ), patch(
            "comms.keyword_learner.KeywordLearner._device_reference_lines_sync",
            return_value='- room="卧室" device="空调" category="空调"',
        ):
            samples = KeywordLearner._collect_confirmed_history_samples_sync(self.account.id)
            candidates = asyncio.run(KeywordLearner._extract_history_candidates_with_ai(self.account.id, samples))

        created = KeywordLearner._upsert_candidate_sync(self.account.id, candidates[0])
        learned = LearnedKeyword.objects.get(account=self.account, normalized_keyword="弄暖和一点")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(created, 1)
        self.assertEqual(learned.category, LearnedKeyword.CategoryChoices.ACTION)
        self.assertEqual(learned.canonical_payload["control_key"], "temperature")

    def test_keyword_learner_ignores_failed_history_samples(self):
        room = DeviceRoom.objects.create(
            account=self.account,
            slug="study",
            name="书房",
            climate="24°C",
            summary="测试房间",
            sort_order=30,
        )
        device = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="ha:light-failed",
            room=room,
            name="台灯",
            category="灯",
            status=DeviceSnapshot.StatusChoices.ONLINE,
            telemetry="关闭",
            capabilities=["power"],
            sort_order=30,
        )
        DeviceOperationContext.objects.create(
            account=self.account,
            device=device,
            control_id="ha:light-failed:power",
            control_key="power",
            operation_type="set_property",
            value=False,
            raw_user_msg="把书房那个灯关掉",
            normalized_msg="关闭书房台灯",
            intent_json={
                "type": "DEVICE_CONTROL",
                "room": "书房",
                "device": "台灯",
                "control_key": "power",
                "value": False,
            },
            execution_result={"success": False, "message": "offline"},
        )

        samples = KeywordLearner._collect_confirmed_history_samples_sync(self.account.id)

        self.assertEqual(samples, [])

    def test_device_context_manager_links_recent_user_chat_message(self):
        room = DeviceRoom.objects.create(
            account=self.account,
            slug="living-room-link",
            name="客厅",
            climate="26°C",
            summary="测试房间",
            sort_order=40,
        )
        device = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="ha:light-link",
            room=room,
            name="主灯",
            category="灯",
            status=DeviceSnapshot.StatusChoices.ONLINE,
            telemetry="开启",
            capabilities=["power"],
            sort_order=40,
        )
        chat = ChatMessage.objects.create(
            account=self.account,
            platform_user_id="wx-link",
            role=ChatMessage.RoleChoices.USER,
            source="wechat",
            content="把客厅主灯关了",
        )

        context = DeviceContextManager.record_operation(
            account=self.account,
            platform_user_id="wx-link",
            device=device,
            control_id="ha:light-link:power",
            control_key="power",
            operation_type="set_property",
            value=False,
            raw_user_msg="把客厅主灯关了",
            normalized_msg="关闭客厅主灯",
            intent_json={"type": "DEVICE_CONTROL", "device": "主灯", "control_key": "power"},
            execution_result={"success": True},
        )

        chat.refresh_from_db()
        self.assertEqual(chat.linked_device_context_id, context.id)

    def test_keyword_learner_prefers_linked_chat_message_content(self):
        room = DeviceRoom.objects.create(
            account=self.account,
            slug="bedroom-link",
            name="卧室",
            climate="25°C",
            summary="测试房间",
            sort_order=50,
        )
        device = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="ha:ac-link",
            room=room,
            name="空调",
            category="空调",
            status=DeviceSnapshot.StatusChoices.ONLINE,
            telemetry="制冷",
            capabilities=["temperature"],
            sort_order=50,
        )
        context = DeviceOperationContext.objects.create(
            account=self.account,
            platform_user_id="wx-link-2",
            device=device,
            control_id="ha:ac-link:temperature",
            control_key="temperature",
            operation_type="set_property",
            value=24,
            raw_user_msg="调高卧室温度",
            normalized_msg="调高卧室温度",
            intent_json={
                "type": "DEVICE_CONTROL",
                "room": "卧室",
                "device": "空调",
                "control_key": "temperature",
                "value": "+1",
            },
            execution_result={"success": True, "message": "ok"},
        )
        ChatMessage.objects.create(
            account=self.account,
            platform_user_id="wx-link-2",
            role=ChatMessage.RoleChoices.USER,
            source="wechat",
            content="把卧室弄暖和一点",
            linked_device_context=context,
        )

        samples = KeywordLearner._collect_confirmed_history_samples_sync(self.account.id)

        self.assertEqual(samples[0]["raw_user_msg"], "把卧室弄暖和一点")
        self.assertIsNotNone(samples[0]["chat_message_id"])

