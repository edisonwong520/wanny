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


def parse_review_hours(raw_value: str | None, legacy_hour: str | None = None) -> list[int]:
    """
    解析复盘执行时段，支持：
    - REVIEW_HOURS=0,12
    - 兼容旧配置 REVIEW_HOUR=3
    """
    source = raw_value or legacy_hour or "0,12"
    hours = set()

    for piece in str(source).split(","):
        piece = piece.strip()
        if not piece:
            continue
        try:
            hour = int(piece)
        except ValueError:
            continue
        if 0 <= hour <= 23:
            hours.add(hour)

    return sorted(hours) or [0, 12]


def should_run_review_now(now: datetime, review_hours: list[int], last_run_slot: str | None) -> bool:
    """
    仅在目标小时的前 5 分钟内触发一次，确保复盘稳定落在 00:00 / 12:00 这样的整点窗口。
    """
    current_slot = f"{now:%Y-%m-%d}-{now.hour:02d}"
    return now.hour in review_hours and now.minute < 5 and last_run_slot != current_slot


class ReviewEngine:
    """
    定时复盘引擎，与 MonitorService 共存于同一个 asyncio 事件循环中。
    """
    _last_run_slot = None

    @classmethod
    async def loop_start(cls, bot):
        """
        定时复盘协程。
        默认每天 00:00 和 12:00 触发一次，可通过 REVIEW_HOURS 覆盖。
        """
        review_hours = parse_review_hours(os.getenv("REVIEW_HOURS"), os.getenv("REVIEW_HOUR"))
        logger.info(
            "[ReviewEngine] 已启动定时复盘引擎，目标执行时间: 每日 "
            + ", ".join([f"{hour:02d}:00" for hour in review_hours])
        )

        # 首次等待 60 秒让系统启动稳定
        await asyncio.sleep(60)

        while True:
            try:
                now = datetime.now()
                current_slot = f"{now:%Y-%m-%d}-{now.hour:02d}"
                if should_run_review_now(now, review_hours, cls._last_run_slot):
                    logger.info("[ReviewEngine] 🧠 触发定时画像复盘任务...")
                    await cls._run_review(bot)
                    cls._last_run_slot = current_slot
                    # 执行完毕后等 5 分钟，避免同一时段重复触发
                    await asyncio.sleep(300)
                else:
                    # 每 5 分钟检查一次是否到了复盘时间
                    await asyncio.sleep(300)
            except Exception as e:
                logger.error(f"[ReviewEngine] 复盘循环异常: {e}")
                await asyncio.sleep(300)

    @classmethod
    async def _run_review(cls, bot, lookback_hours: int | None = None):
        """
        执行一次复盘：
        1. 收集最近时间窗口的所有记忆
        2. 交给 AI 做反思分析
        3. 将画像建议写入 UserProfile（用户手动修改优先）
        4. 通过微信推送汇总报告
        """
        from memory.models import UserProfile, ProactiveLog
        lookback_hours = lookback_hours or int(os.getenv("REVIEW_LOOKBACK_HOURS", 12))

        profile_user_ids = await sync_to_async(list)(
            UserProfile.objects.values_list("user_id", flat=True).distinct()
        )
        recent_memory_user_ids = await MemoryService.get_active_user_ids(hours=lookback_hours)
        runtime_user_ids = list(bot._context_tokens.keys()) if bot and getattr(bot, "_context_tokens", None) else []
        user_ids = sorted(set(profile_user_ids) | set(recent_memory_user_ids) | set(runtime_user_ids))

        if not user_ids:
            logger.info("[ReviewEngine] 没有找到活跃用户，跳过本次复盘。")
            return

        for user_id in user_ids:
            try:
                recent_text = await MemoryService.get_recent_memories_text(user_id, hours=lookback_hours)
                if not recent_text or len(recent_text) < 50:
                    logger.debug(f"[ReviewEngine] 用户 {user_id} 近 {lookback_hours}h 记忆不足，跳过。")
                    continue

                profile_context = await MemoryService._get_profile_context(user_id)
                review_prompt = f"""请分析以下用户在最近 {lookback_hours} 小时的互动记录，提取出值得记录的用户偏好或习惯。

已有画像（如果标记为“用户已确认”，请视为最高优先级，不要输出与其直接冲突的值）：
{profile_context or "暂无"}

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
                    profile = await MemoryService.apply_review_profile_update(user_id, insight)
                    if profile:
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
