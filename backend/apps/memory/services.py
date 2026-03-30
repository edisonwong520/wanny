"""
记忆服务层 — 统一入口
对外暴露简洁的 API，内部协调 VectorStore 和 UserProfile 的读写。
"""
import asyncio
from datetime import datetime

from asgiref.sync import sync_to_async
from django.utils import timezone

from utils.logger import logger
from memory.vector_store import VectorStore

PROFILE_SOURCE_REVIEW = "review"
PROFILE_SOURCE_MANUAL = "manual"


def _clamp_confidence(value: float | int | str | None, default: float = 0.5) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = default
    return max(0.0, min(1.0, numeric))


def build_profile_update(existing_profile, incoming: dict, source: str, now: datetime | None = None) -> dict:
    """
    统一处理画像写入规则：
    - 手动修改永远优先，置信度视为用户确认；
    - 定时复盘在遇到用户手动修改的字段时，不覆盖当前值，而是保留最新建议用于后续融合；
    - 如果复盘结果和用户手动值一致，则提升置信度并清空冲突建议。
    """
    now = now or timezone.now()

    normalized_category = str(incoming.get("category") or getattr(existing_profile, "category", "Other") or "Other")
    normalized_value = str(incoming.get("value", "")).strip()
    normalized_confidence = _clamp_confidence(incoming.get("confidence"), default=0.5)

    if source == PROFILE_SOURCE_MANUAL:
        previous_review_value = getattr(existing_profile, "last_review_value", "") or ""
        previous_review_confidence = getattr(existing_profile, "last_review_confidence", None)
        previous_review_at = getattr(existing_profile, "last_review_at", None)

        if previous_review_value.strip() == normalized_value:
            previous_review_value = ""
            previous_review_confidence = None
            previous_review_at = None

        return {
            "category": normalized_category,
            "value": normalized_value,
            "confidence": 1.0,
            "source": PROFILE_SOURCE_MANUAL,
            "is_user_edited": True,
            "last_confirmed": now,
            "last_review_value": previous_review_value,
            "last_review_confidence": previous_review_confidence,
            "last_review_at": previous_review_at,
        }

    if existing_profile and getattr(existing_profile, "is_user_edited", False):
        current_value = str(getattr(existing_profile, "value", "")).strip()
        same_value = current_value == normalized_value
        current_confidence = _clamp_confidence(getattr(existing_profile, "confidence", 1.0), default=1.0)

        return {
            "category": getattr(existing_profile, "category", normalized_category),
            "value": current_value,
            "confidence": max(current_confidence, normalized_confidence) if same_value else current_confidence,
            "source": PROFILE_SOURCE_MANUAL,
            "is_user_edited": True,
            "last_confirmed": getattr(existing_profile, "last_confirmed", None),
            "last_review_value": "" if same_value else normalized_value,
            "last_review_confidence": normalized_confidence,
            "last_review_at": now,
        }

    return {
        "category": normalized_category,
        "value": normalized_value,
        "confidence": normalized_confidence,
        "source": PROFILE_SOURCE_REVIEW,
        "is_user_edited": False,
        "last_confirmed": getattr(existing_profile, "last_confirmed", None),
        "last_review_value": "",
        "last_review_confidence": None,
        "last_review_at": now,
    }


class MemoryService:
    """
    记忆服务统一入口，提供对话记录、上下文检索、设备事件记录等功能。
    """

    @classmethod
    def _store(cls) -> VectorStore:
        return VectorStore.get_instance()

    @staticmethod
    def _serialize_profile(profile) -> dict:
        return {
            "user_id": profile.user_id,
            "category": profile.category,
            "key": profile.key,
            "value": profile.value,
            "confidence": profile.confidence,
            "source": profile.source,
            "is_user_edited": profile.is_user_edited,
            "last_confirmed": profile.last_confirmed.isoformat() if profile.last_confirmed else None,
            "last_review_value": profile.last_review_value,
            "last_review_confidence": profile.last_review_confidence,
            "last_review_at": profile.last_review_at.isoformat() if profile.last_review_at else None,
            "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        }

    @classmethod
    async def record_conversation(cls, user_id: str, role: str, content: str):
        """
        记录一条对话到向量库。

        Args:
            user_id: 用户唯一标识
            role: 角色 ("user" 或 "assistant")
            content: 对话内容
        """
        try:
            text = f"[{role}] {content}"
            metadata = {"role": role, "source": "wechat_chat"}
            await asyncio.to_thread(cls._store().add_memory, user_id, text, metadata)
        except Exception as e:
            logger.error(f"[MemoryService] 记录对话失败: {e}")

    @classmethod
    async def record_device_event(cls, user_id: str, device_did: str, action: str, result: str):
        """
        记录一条设备操作事件到向量库。

        Args:
            user_id: 关联的用户
            device_did: 设备 ID
            action: 操作动作描述
            result: 执行结果
        """
        try:
            text = f"[device_event] 设备 {device_did}: {action} -> {result}"
            metadata = {"role": "system", "source": "iot_monitor", "device_did": device_did}
            await asyncio.to_thread(cls._store().add_memory, user_id, text, metadata)
        except Exception as e:
            logger.error(f"[MemoryService] 记录设备事件失败: {e}")

    @classmethod
    async def get_context_for_chat(cls, user_id: str, current_msg: str, top_k: int = 5) -> str:
        """
        检索与当前消息语义相关的历史记忆，组装成 system prompt 增补片段。

        Args:
            user_id: 用户唯一标识
            current_msg: 当前用户消息
            top_k: 检索条数

        Returns:
            格式化的记忆上下文字符串，可直接拼接到 system prompt
        """
        try:
            memories = await asyncio.to_thread(cls._store().search_memory, user_id, current_msg, top_k)
            if not memories:
                return ""

            # 获取用户画像作为补充
            profile_context = await cls._get_profile_context(user_id)

            lines = ["以下是与用户之前的互动记忆（按相关性排序），请参考它们来理解上下文："]
            for i, mem in enumerate(memories, 1):
                lines.append(f"  {i}. {mem['text']}")

            if profile_context:
                lines.append("\n用户的已知偏好画像：")
                lines.append(profile_context)

            context = "\n".join(lines)
            logger.debug(f"[MemoryService] 生成上下文: user={user_id}, 记忆数={len(memories)}, 长度={len(context)}")
            return context

        except Exception as e:
            logger.error(f"[MemoryService] 检索上下文失败: {e}")
            return ""

    @classmethod
    async def _get_profile_context(cls, user_id: str) -> str:
        """从 UserProfile 表中读取结构化画像，格式化为文本。"""
        try:
            from memory.models import UserProfile
            profiles = await sync_to_async(list)(
                UserProfile.objects.filter(user_id=user_id, confidence__gte=0.5)
                .order_by('-is_user_edited', '-confidence', '-updated_at')[:10]
            )
            if not profiles:
                return ""
            lines = []
            for profile in profiles:
                if profile.is_user_edited:
                    lines.append(f"  - [{profile.category}] {profile.key} = {profile.value} (用户已确认)")
                else:
                    lines.append(
                        f"  - [{profile.category}] {profile.key} = {profile.value} (置信度: {profile.confidence})"
                    )
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"[MemoryService] 读取画像失败: {e}")
            return ""

    @classmethod
    async def get_recent_memories_text(cls, user_id: str, hours: int = 24) -> str:
        """
        获取指定时间窗口的所有记忆文本（用于 Daily Review）。
        """
        try:
            memories = await asyncio.to_thread(cls._store().get_recent_memories, user_id, hours)
            if not memories:
                return ""
            return "\n".join([m["text"] for m in memories])
        except Exception as e:
            logger.error(f"[MemoryService] 获取近期记忆失败: {e}")
            return ""

    @classmethod
    async def get_active_user_ids(cls, hours: int = 24) -> list[str]:
        """从向量记忆库中扫描最近活跃的用户，用于定时画像更新。"""
        try:
            return await asyncio.to_thread(cls._store().list_recent_user_ids, hours)
        except Exception as e:
            logger.error(f"[MemoryService] 获取活跃用户失败: {e}")
            return []

    @classmethod
    async def list_profiles(cls, user_id: str) -> list[dict]:
        """列出某个用户的所有画像，供前端展示和人工编辑。"""
        try:
            from memory.models import UserProfile

            profiles = await sync_to_async(list)(
                UserProfile.objects.filter(user_id=user_id).order_by("-is_user_edited", "-updated_at", "key")
            )
            return [cls._serialize_profile(profile) for profile in profiles]
        except Exception as e:
            logger.error(f"[MemoryService] 列出画像失败: {e}")
            return []

    @classmethod
    async def upsert_manual_profile(
        cls,
        user_id: str,
        key: str,
        value: str,
        category: str = "Other",
    ) -> dict | None:
        """用户手动新增或修改画像；一旦手动修改，后续定时任务必须以用户值为准。"""
        try:
            from memory.models import UserProfile

            now = timezone.now()
            existing = await sync_to_async(
                lambda: UserProfile.objects.filter(user_id=user_id, key=key).first()
            )()
            defaults = build_profile_update(
                existing,
                {
                    "category": category,
                    "value": value,
                    "confidence": 1.0,
                },
                source=PROFILE_SOURCE_MANUAL,
                now=now,
            )

            profile, _ = await sync_to_async(UserProfile.objects.update_or_create)(
                user_id=user_id,
                key=key,
                defaults=defaults,
            )
            logger.info(f"[MemoryService] 用户手动更新画像: user={user_id}, key={key}")
            return cls._serialize_profile(profile)
        except Exception as e:
            logger.error(f"[MemoryService] 手动更新画像失败: {e}")
            return None

    @classmethod
    async def apply_review_profile_update(cls, user_id: str, insight: dict) -> dict | None:
        """定时复盘写入画像，自动处理与用户手动修改的融合策略。"""
        try:
            from memory.models import UserProfile

            key = str(insight.get("key", "")).strip()
            if not key:
                return None

            existing = await sync_to_async(
                lambda: UserProfile.objects.filter(user_id=user_id, key=key).first()
            )()
            defaults = build_profile_update(
                existing,
                insight,
                source=PROFILE_SOURCE_REVIEW,
                now=timezone.now(),
            )

            profile, _ = await sync_to_async(UserProfile.objects.update_or_create)(
                user_id=user_id,
                key=key,
                defaults=defaults,
            )
            logger.info(
                f"[MemoryService] 复盘更新画像: user={user_id}, key={key}, source={profile.source}, user_edited={profile.is_user_edited}"
            )
            return cls._serialize_profile(profile)
        except Exception as e:
            logger.error(f"[MemoryService] 复盘更新画像失败: {e}")
            return None
