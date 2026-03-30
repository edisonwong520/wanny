"""
定时复盘引擎 (Daily Review)
每 24 小时汇总对话和设备操作日志，送给 AI 做反思，生成画像更新建议。
"""
import os
import asyncio
from datetime import datetime
from asgiref.sync import sync_to_async
from utils.logger import logger
from memory.services import MemoryService
from comms.ai import AIAgent


class ReviewEngine:
    """
    定时复盘引擎，与 MonitorService 共存于同一个 asyncio 事件循环中。
    """

    @classmethod
    async def loop_start(cls, bot):
        """
        24 小时周期的复盘协程。
        首次启动延迟 60 秒（等待系统稳定），之后每 24 小时执行一次。
        """
        review_hour = int(os.getenv("REVIEW_HOUR", 3))  # 默认凌晨 3 点
        logger.info(f"[ReviewEngine] 已启动定时复盘引擎，目标执行时间: 每日 {review_hour}:00")

        # 首次等待 60 秒让系统启动稳定
        await asyncio.sleep(60)

        while True:
            try:
                now = datetime.now()
                if now.hour == review_hour:
                    logger.info("[ReviewEngine] 🧠 触发每日复盘任务...")
                    await cls._run_review(bot)
                    # 执行完毕后等 1 小时，防止同一小时内重复触发
                    await asyncio.sleep(3600)
                else:
                    # 每 10 分钟检查一次是否到了复盘时间
                    await asyncio.sleep(600)
            except Exception as e:
                logger.error(f"[ReviewEngine] 复盘循环异常: {e}")
                await asyncio.sleep(600)

    @classmethod
    async def _run_review(cls, bot):
        """
        执行一次复盘：
        1. 收集最近 24h 的所有记忆
        2. 交给 AI 做反思分析
        3. 将画像建议写入 UserProfile
        4. 通过微信推送汇总报告
        """
        # 收集所有活跃用户的记忆（这里用一个通用 user_id 做聚合）
        # 实际上我们可以遍历 ChromaDB 的 collections，但简单起见用已知的用户
        from memory.models import UserProfile, ProactiveLog

        # 获取最近有记忆的用户 — 从 UserProfile 中取去重的 user_id
        user_ids = await sync_to_async(list)(
            UserProfile.objects.values_list('user_id', flat=True).distinct()
        )
        
        # 如果没有任何画像记录，尝试从 bot 的 context_tokens 中获取活跃用户
        if not user_ids and bot and getattr(bot, '_context_tokens', None):
            user_ids = list(bot._context_tokens.keys())

        if not user_ids:
            logger.info("[ReviewEngine] 没有找到活跃用户，跳过本次复盘。")
            return

        for user_id in user_ids:
            try:
                recent_text = await MemoryService.get_recent_memories_text(user_id, hours=24)
                if not recent_text or len(recent_text) < 50:
                    logger.debug(f"[ReviewEngine] 用户 {user_id} 近 24h 记忆不足，跳过。")
                    continue

                # 让 AI 做反思
                review_prompt = f"""请分析以下用户在过去 24 小时的互动记录，提取出值得记录的用户偏好或习惯。

互动记录：
{recent_text[:3000]}

请严格返回 JSON 数组格式，每条包含：
- "category": 类别 (Environment/Entertainment/Habit/Device/Other)
- "key": 偏好键 (英文，如 preferred_temp)
- "value": 偏好值
- "confidence": 置信度 (0.0-1.0)
- "summary": 中文描述（限 30 字）

如果没有可提取的偏好，返回空数组 []。"""

                agent = AIAgent()
                result = await agent.generate_json(
                    "你是一个用户行为分析引擎，只返回纯 JSON 数组。",
                    review_prompt
                )

                # 结果可能是 dict（包裹在 {"type": ...} 里）或 list
                insights = result if isinstance(result, list) else result.get("insights", [])

                updated_count = 0
                for insight in insights:
                    if not isinstance(insight, dict) or "key" not in insight:
                        continue
                    await sync_to_async(UserProfile.objects.update_or_create)(
                        user_id=user_id,
                        key=insight["key"],
                        defaults={
                            "category": insight.get("category", "Other"),
                            "value": str(insight.get("value", "")),
                            "confidence": float(insight.get("confidence", 0.5)),
                        }
                    )
                    updated_count += 1

                if updated_count > 0:
                    logger.info(f"[ReviewEngine] ✅ 用户 {user_id} 画像更新了 {updated_count} 条偏好。")
                    
                    # 推送简要汇总给用户
                    summary_lines = [f"  • {i.get('summary', i.get('key'))}" for i in insights if isinstance(i, dict)]
                    if summary_lines and bot and getattr(bot, '_context_tokens', None):
                        report = f"🧠 Sir, 每日复盘完成。我从今天的互动中学到了以下内容：\n" + "\n".join(summary_lines[:5])
                        
                        # 记录推送日志
                        await sync_to_async(ProactiveLog.objects.create)(
                            user_id=user_id,
                            message=report,
                            score=0.8,
                            source="daily_review"
                        )
                        
                        if user_id in bot._context_tokens:
                            try:
                                await bot.send(user_id, report)
                            except Exception as e:
                                logger.error(f"[ReviewEngine] 推送复盘报告失败: {e}")

            except Exception as e:
                logger.error(f"[ReviewEngine] 用户 {user_id} 复盘失败: {e}")
