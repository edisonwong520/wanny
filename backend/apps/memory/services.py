"""
记忆服务层 — 统一入口
对外暴露简洁的 API，内部协调 VectorStore 和 UserProfile 的读写。
"""
import asyncio
from asgiref.sync import sync_to_async
from utils.logger import logger
from memory.vector_store import VectorStore


class MemoryService:
    """
    记忆服务统一入口，提供对话记录、上下文检索、设备事件记录等功能。
    """

    @classmethod
    def _store(cls) -> VectorStore:
        return VectorStore.get_instance()

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
                UserProfile.objects.filter(user_id=user_id, confidence__gte=0.5).order_by('-confidence')[:10]
            )
            if not profiles:
                return ""
            return "\n".join([f"  - [{p.category}] {p.key} = {p.value} (置信度: {p.confidence})" for p in profiles])
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
