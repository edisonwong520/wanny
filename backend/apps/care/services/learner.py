from __future__ import annotations

from asgiref.sync import async_to_sync

from care.models import CareSuggestion
from memory.models import ProactiveLog
from memory.services import MemoryService


class FeedbackLearner:
    @classmethod
    def build_topic_key(cls, *, suggestion: CareSuggestion, fallback: str = "care:generic") -> str:
        source_event = suggestion.source_event if isinstance(suggestion.source_event, dict) else {}
        event_name = str(source_event.get("event") or "").strip()
        if event_name:
            return f"care:event:{event_name}"
        rule = suggestion.source_rule
        if rule is not None:
            if rule.system_key:
                return f"care:rule:{rule.system_key}"
            return f"care:rule:{rule.id}"
        return fallback

    @classmethod
    def feedback_adjust_factor(cls, *, account, topic_key: str) -> float:
        history = list(
            ProactiveLog.objects.filter(account=account, source=topic_key).order_by("-created_at")[:3]
        )
        if not history:
            return 1.0
        if all(item.feedback == ProactiveLog.FeedbackChoices.DENIED for item in history):
            return 0.3
        if history[0].feedback == ProactiveLog.FeedbackChoices.DENIED:
            return 0.7
        if history[0].feedback == ProactiveLog.FeedbackChoices.APPROVED:
            return 1.1
        return 1.0

    @classmethod
    def apply_feedback(cls, suggestion: CareSuggestion, *, action: str) -> None:
        topic_key = cls.build_topic_key(suggestion=suggestion)
        insight = cls._build_profile_insight(suggestion=suggestion, action=action, topic_key=topic_key)
        if insight:
            async_to_sync(MemoryService.apply_review_profile_update)(suggestion.account, insight)

    @classmethod
    def _build_profile_insight(cls, *, suggestion: CareSuggestion, action: str, topic_key: str) -> dict | None:
        normalized_action = str(action or "").strip().lower()
        source_event = suggestion.source_event if isinstance(suggestion.source_event, dict) else {}

        if source_event.get("event") == "weather_temperature_drop":
            action_spec = suggestion.action_spec if isinstance(suggestion.action_spec, dict) else {}
            if normalized_action in {"approve", "execute"} and "value" in action_spec:
                return {
                    "category": "Environment",
                    "key": "care_preferred_cold_weather_target_temp",
                    "value": str(action_spec.get("value")),
                    "confidence": 0.82 if normalized_action == "execute" else 0.72,
                }
            return {
                "category": "Environment",
                "key": "care_feedback.weather_temperature_drop",
                "value": normalized_action,
                "confidence": 0.62,
            }

        return {
            "category": "Device",
            "key": topic_key.replace(":", "."),
            "value": normalized_action,
            "confidence": 0.58 if normalized_action in {"reject", "ignore"} else 0.68,
        }
