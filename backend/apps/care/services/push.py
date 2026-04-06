from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta

from asgiref.sync import sync_to_async

from care.models import CareSuggestion
from comms.bot_runtime import get_current_bot
from memory.models import ProactiveLog
from providers.models import PlatformAuth
from utils.logger import logger


class CarePushService:
    default_interval_seconds = 300
    default_medium_window = timedelta(hours=1)
    default_repeat_gap = timedelta(hours=24)
    default_ignore_gap = timedelta(hours=48)

    @classmethod
    async def loop_start(cls, bot):
        interval = max(int(os.getenv("CARE_PUSH_INTERVAL", cls.default_interval_seconds)), 60)
        logger.info(f"[Care Push] 已启动主动关怀推送循环，间隔: {interval}秒")
        await asyncio.sleep(30)
        while True:
            try:
                await cls.deliver_due_suggestions(bot=bot)
            except Exception as error:
                logger.error(f"[Care Push] 推送循环异常: {error}")
            await asyncio.sleep(interval)

    @classmethod
    async def deliver_due_suggestions(cls, bot=None) -> int:
        active_bot = bot or get_current_bot()
        if not active_bot:
            logger.debug("[Care Push] 当前没有活跃的微信 Bot 进程，跳过主动关怀推送。")
            return 0

        delivered = 0
        accounts = await sync_to_async(list)(
            PlatformAuth.objects.filter(platform_name="wechat", is_active=True, account__isnull=False)
            .select_related("account")
            .order_by("account_id")
        )

        for auth in accounts:
            account = auth.account
            if account is None:
                continue
            payload = auth.auth_payload if isinstance(auth.auth_payload, dict) else {}
            wechat_user_id = str(payload.get("user_id") or payload.get("userId") or "").strip()
            if not wechat_user_id:
                continue
            suggestions = await sync_to_async(cls._select_due_suggestions)(account)
            if not suggestions:
                continue
            message = cls._build_push_message(suggestions)
            try:
                await active_bot.send(wechat_user_id, message)
            except Exception as error:
                logger.error(f"[Care Push] 推送到账户 {account.email} 失败: {error}")
                continue
            await sync_to_async(cls._mark_pushed)(account, suggestions, message)
            delivered += len(suggestions)
        return delivered

    @classmethod
    def _select_due_suggestions(cls, account) -> list[CareSuggestion]:
        now = datetime.now()
        queryset = list(
            CareSuggestion.objects.filter(account=account, status=CareSuggestion.StatusChoices.PENDING)
            .select_related("device", "control_target", "source_rule")
            .order_by("-priority", "-created_at", "-id")
        )
        due: list[CareSuggestion] = []
        medium_included = False
        medium_blocked = cls._has_recent_medium_push(account=account, now=now)
        for suggestion in queryset:
            if len(due) >= 3:
                break
            level = cls._push_level(suggestion.priority)
            if level == "low":
                continue
            if not cls._should_push_suggestion(suggestion, now=now):
                continue
            if level == "medium":
                if medium_blocked or medium_included:
                    continue
                medium_included = True
            due.append(suggestion)
        return due

    @classmethod
    def _push_level(cls, priority: float) -> str:
        if priority > 7:
            return "high"
        if priority >= 4:
            return "medium"
        return "low"

    @classmethod
    def _should_push_suggestion(cls, suggestion: CareSuggestion, *, now: datetime) -> bool:
        feedback = suggestion.user_feedback if isinstance(suggestion.user_feedback, dict) else {}
        if str(feedback.get("action") or "").strip().lower() == "ignore" and suggestion.feedback_collected_at:
            if now - suggestion.feedback_collected_at < cls.default_ignore_gap:
                return False
        push_state = feedback.get("push") if isinstance(feedback.get("push"), dict) else {}
        last_pushed_at_raw = push_state.get("last_pushed_at")
        if not last_pushed_at_raw:
            return True
        try:
            last_pushed_at = datetime.fromisoformat(str(last_pushed_at_raw))
        except ValueError:
            return True
        return now - last_pushed_at >= cls.default_repeat_gap

    @classmethod
    def _has_recent_medium_push(cls, *, account, now: datetime) -> bool:
        threshold = now - cls.default_medium_window
        return ProactiveLog.objects.filter(
            account=account,
            source="care:push",
            created_at__gte=threshold,
            score__gte=4,
            score__lte=7,
        ).exists()

    @classmethod
    def _build_push_message(cls, suggestions: list[CareSuggestion]) -> str:
        if len(suggestions) == 1:
            item = suggestions[0]
            device_name = item.device.name if item.device else "设备"
            return (
                f"主动关怀提醒：{item.title}\n"
                f"{item.body}\n"
                f"目标：{device_name}\n"
                "如需执行，请打开控制台关怀中心或直接在微信里继续确认。"
            )

        lines = ["主动关怀中心为您整理了以下建议："]
        for index, item in enumerate(suggestions, start=1):
            device_name = item.device.name if item.device else "未关联设备"
            lines.append(f"{index}. {item.title}｜{device_name}")
        lines.append("请打开控制台关怀中心查看详情并选择采纳、忽略或执行。")
        return "\n".join(lines)

    @classmethod
    def _mark_pushed(cls, account, suggestions: list[CareSuggestion], message: str) -> None:
        now = datetime.now()
        for suggestion in suggestions:
            feedback = suggestion.user_feedback if isinstance(suggestion.user_feedback, dict) else {}
            push_state = feedback.get("push") if isinstance(feedback.get("push"), dict) else {}
            push_count = int(push_state.get("count") or 0) + 1
            feedback["push"] = {
                "last_pushed_at": now.isoformat(),
                "count": push_count,
            }
            suggestion.user_feedback = feedback
            suggestion.save(update_fields=["user_feedback", "updated_at"])
            ProactiveLog.objects.create(
                account=account,
                message=message,
                feedback=ProactiveLog.FeedbackChoices.PENDING,
                score=suggestion.priority,
                source="care:push",
            )
