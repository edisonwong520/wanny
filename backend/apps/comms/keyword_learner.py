from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone
from asgiref.sync import sync_to_async

from comms.ai import AIAgent
from comms.initial_keywords import normalize_keyword
from comms.models import ChatMessage, DeviceOperationContext, LearnedKeyword, Mission
from devices.models import DeviceSnapshot


def history_learning_enabled() -> bool:
    return os.getenv("ENABLE_HISTORY_KEYWORD_LEARNING", "false").strip().lower() in {"1", "true", "on", "yes"}


@dataclass
class LearnedKeywordCandidate:
    keyword: str
    category: str
    canonical: str
    canonical_payload: dict
    source: str
    confidence: float = 0.6


class KeywordLearner:
    @classmethod
    async def run_learning_cycle(cls, account_id: int) -> int:
        count = await cls._learn_from_devices(account_id)
        if history_learning_enabled():
            count += await cls._learn_from_confirmed_history(account_id)
        return count

    @classmethod
    async def _learn_from_devices(cls, account_id: int) -> int:
        return await sync_to_async(cls._learn_from_devices_sync, thread_sensitive=True)(account_id)

    @classmethod
    def _learn_from_devices_sync(cls, account_id: int) -> int:
        devices = list(DeviceSnapshot.objects.filter(account_id=account_id).select_related("room").order_by("id"))
        created = 0
        for device in devices:
            candidates = cls._device_candidates(device)
            for candidate in candidates:
                created += cls._upsert_candidate_sync(account_id, candidate)
        return created

    @classmethod
    async def _learn_from_confirmed_history(cls, account_id: int) -> int:
        samples = await sync_to_async(cls._collect_confirmed_history_samples_sync, thread_sensitive=True)(account_id)
        if not samples:
            return 0

        ai_candidates = await cls._extract_history_candidates_with_ai(account_id, samples)
        if ai_candidates:
            created = 0
            for candidate in ai_candidates:
                created += await sync_to_async(cls._upsert_candidate_sync, thread_sensitive=True)(account_id, candidate)
            return created

        return await sync_to_async(cls._learn_from_confirmed_history_rules, thread_sensitive=True)(account_id, samples)

    @classmethod
    def _learn_from_confirmed_history_rules(cls, account_id: int, samples: list[dict]) -> int:
        counts: Counter[tuple[str, str, str, str]] = Counter()
        for sample in samples:
            raw_msg = str(sample.get("raw_user_msg") or sample.get("normalized_msg") or "").strip()
            intent = sample.get("intent_json") or {}
            if not raw_msg or intent.get("type") not in {"DEVICE_CONTROL", "DEVICE_QUERY"}:
                continue
            device = str(intent.get("device") or "").strip()
            room = str(intent.get("room") or "").strip()
            if device and device not in raw_msg and len(raw_msg) <= 16:
                counts[(raw_msg, "device", device, str(intent.get("control_key") or ""))] += 1
            elif room and room not in raw_msg and len(raw_msg) <= 12:
                counts[(raw_msg, "room", room, "")] += 1

        created = 0
        for (keyword, category, canonical, control_key), freq in counts.items():
            if freq < 2:
                continue
            payload = {}
            if category == "control" and control_key:
                payload["control_key"] = control_key
            created += cls._upsert_candidate_sync(
                account_id,
                LearnedKeywordCandidate(
                    keyword=keyword,
                    category=category,
                    canonical=canonical,
                    canonical_payload=payload,
                    source=LearnedKeyword.SourceChoices.HISTORY,
                    confidence=min(0.5 + (freq * 0.1), 0.9),
                ),
            )
        return created

    @classmethod
    def _confirmed_samples_queryset(cls, account_id: int):
        recent_at = timezone.now() - timedelta(days=7)
        Mission.objects.filter(
            account_id=account_id,
            source_type=Mission.SourceTypeChoices.DEVICE_CONTROL,
            status=Mission.StatusChoices.APPROVED,
            created_at__gte=recent_at,
        ).exists()
        return DeviceOperationContext.objects.filter(
            account_id=account_id,
            operated_at__gte=recent_at,
        ).exclude(raw_user_msg="")

    @classmethod
    def _collect_confirmed_history_samples_sync(cls, account_id: int) -> list[dict]:
        rows = cls._confirmed_samples_queryset(account_id).order_by("-operated_at")[:50]
        samples: list[dict] = []
        for row in rows:
            execution_result = row.execution_result or {}
            intent = row.intent_json or {}
            if intent.get("type") not in {"DEVICE_CONTROL", "DEVICE_QUERY"}:
                continue
            if row.operation_type and intent.get("type") == "DEVICE_CONTROL" and execution_result.get("success") is False:
                continue
            linked_message = (
                ChatMessage.objects.filter(linked_device_context=row, role=ChatMessage.RoleChoices.USER)
                .order_by("-created_at")
                .first()
            )
            raw_msg = str((linked_message.content if linked_message else row.raw_user_msg) or "").strip()
            if not raw_msg:
                continue
            samples.append(
                {
                    "raw_user_msg": raw_msg,
                    "chat_message_id": linked_message.id if linked_message else None,
                    "normalized_msg": row.normalized_msg,
                    "intent_json": intent,
                    "execution_result": execution_result,
                    "device_name": row.device.name,
                    "room_name": row.device.room.name if row.device.room else "",
                    "control_key": row.control_key,
                }
            )
        return samples

    @classmethod
    async def _extract_history_candidates_with_ai(
        cls,
        account_id: int,
        samples: list[dict],
    ) -> list[LearnedKeywordCandidate]:
        if not history_learning_enabled():
            return []

        device_list = await sync_to_async(cls._device_reference_lines_sync, thread_sensitive=True)(account_id)
        if not device_list:
            return []

        prompt = cls._build_history_learning_prompt(samples=samples, device_list=device_list)
        agent = AIAgent()
        result = await agent.generate_json(
            "你是设备意图关键词学习器。请从已确认成功的设备交互中提取稳定关键词，只返回 JSON。",
            prompt,
        )
        keywords = result.get("keywords")
        if not isinstance(keywords, list):
            return []

        candidates: list[LearnedKeywordCandidate] = []
        for item in keywords:
            if not isinstance(item, dict):
                continue
            keyword = str(item.get("keyword") or "").strip()
            category = str(item.get("category") or "").strip()
            if not keyword or category not in {
                LearnedKeyword.CategoryChoices.DEVICE,
                LearnedKeyword.CategoryChoices.ROOM,
                LearnedKeyword.CategoryChoices.CONTROL,
                LearnedKeyword.CategoryChoices.ACTION,
                LearnedKeyword.CategoryChoices.COLLOQUIAL,
            }:
                continue
            candidates.append(
                LearnedKeywordCandidate(
                    keyword=keyword,
                    category=category,
                    canonical=str(item.get("canonical") or "").strip(),
                    canonical_payload=item.get("canonical_payload") if isinstance(item.get("canonical_payload"), dict) else {},
                    source=LearnedKeyword.SourceChoices.HISTORY,
                    confidence=float(item.get("confidence") or 0.6),
                )
            )
        return candidates

    @classmethod
    def _device_reference_lines_sync(cls, account_id: int) -> str:
        devices = list(
            DeviceSnapshot.objects.filter(account_id=account_id)
            .select_related("room")
            .order_by("id")
        )
        return "\n".join(
            f'- room="{device.room.name if device.room else ""}" device="{device.name}" category="{device.category}"'
            for device in devices
        )

    @classmethod
    def _build_history_learning_prompt(cls, *, samples: list[dict], device_list: str) -> str:
        sample_lines = []
        for item in samples:
            sample_lines.append(
                (
                    f'- raw_user_msg="{item.get("raw_user_msg", "")}" '
                    f'normalized_msg="{item.get("normalized_msg", "")}" '
                    f'intent={item.get("intent_json", {})}'
                )
            )
        return (
            "分析以下已确认成功的设备交互记录，提取用户稳定使用的设备控制表达方式。\n\n"
            "要求：\n"
            "1. 只提取能够稳定复用的表达\n"
            "2. 排除闲聊、情绪描述、一次性措辞\n"
            "3. 输出 JSON 对象，格式为 {\"keywords\": [...]} \n"
            "4. 每个元素包含 keyword, canonical, category, canonical_payload, confidence\n\n"
            f"对话记录：\n{chr(10).join(sample_lines)}\n\n"
            f"设备列表：\n{device_list}"
        )

    @classmethod
    def _device_candidates(cls, device: DeviceSnapshot) -> list[LearnedKeywordCandidate]:
        candidates: list[LearnedKeywordCandidate] = []
        room_name = device.room.name if device.room else ""
        if room_name:
            candidates.append(
                LearnedKeywordCandidate(
                    keyword=room_name,
                    category=LearnedKeyword.CategoryChoices.ROOM,
                    canonical=room_name,
                    canonical_payload={"room": room_name},
                    source=LearnedKeyword.SourceChoices.DEVICE,
                    confidence=0.95,
                )
            )

        candidates.append(
            LearnedKeywordCandidate(
                keyword=device.name,
                category=LearnedKeyword.CategoryChoices.DEVICE,
                canonical=device.name,
                canonical_payload={"device": device.name},
                source=LearnedKeyword.SourceChoices.DEVICE,
                confidence=0.95,
            )
        )

        aliases = cls._generate_name_variants(device.name)
        for alias in aliases:
            candidates.append(
                LearnedKeywordCandidate(
                    keyword=alias,
                    category=LearnedKeyword.CategoryChoices.DEVICE,
                    canonical=device.name,
                    canonical_payload={"device": device.name},
                    source=LearnedKeyword.SourceChoices.DEVICE,
                    confidence=0.7,
                )
            )
        return candidates

    @classmethod
    def _generate_name_variants(cls, device_name: str) -> list[str]:
        base = str(device_name or "").strip()
        if not base:
            return []
        variants = {f"那个{base}", f"这个{base}"}
        if base.endswith("灯"):
            variants.add("大灯")
        if "扫地" in base:
            variants.add("扫地机器人")
        return [item for item in variants if item != base]

    @classmethod
    async def _upsert_candidate(cls, account_id: int, candidate: LearnedKeywordCandidate) -> int:
        return await sync_to_async(cls._upsert_candidate_sync, thread_sensitive=True)(account_id, candidate)

    @classmethod
    def _upsert_candidate_sync(cls, account_id: int, candidate: LearnedKeywordCandidate) -> int:
        normalized = normalize_keyword(candidate.keyword)
        if not normalized:
            return 0

        defaults = {
            "keyword": candidate.keyword,
            "canonical": candidate.canonical,
            "canonical_payload": candidate.canonical_payload,
            "source": candidate.source,
            "confidence": candidate.confidence,
            "last_used_at": timezone.now(),
            "is_active": True,
        }

        obj, created = LearnedKeyword.objects.update_or_create(
            account_id=account_id,
            normalized_keyword=normalized,
            category=candidate.category,
            defaults=defaults,
        )
        if not created:
            obj.usage_count = int(obj.usage_count or 0) + 1
            obj.last_used_at = timezone.now()
            obj.save(update_fields=["usage_count", "last_used_at"])
        return 1 if created else 0
