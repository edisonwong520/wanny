from __future__ import annotations

from typing import Any

from care.models import CareSuggestion, ExternalDataSource
from care.services.aggregator import SuggestionAggregator
from care.services.learner import FeedbackLearner
from devices.models import DeviceControl, DeviceSnapshot


class CareEventProcessor:
    default_temperature_drop_threshold = 8.0

    @classmethod
    def process_weather_source(cls, source: ExternalDataSource) -> CareSuggestion | None:
        data = source.last_data if isinstance(source.last_data, dict) else {}
        current = cls._to_float(data.get("temperature"))
        previous = cls._to_float(data.get("previous_temperature"))
        if current is None or previous is None:
            return None
        drop = previous - current
        threshold = cls._to_float((source.config or {}).get("drop_threshold")) or cls.default_temperature_drop_threshold
        if drop < threshold:
            return None

        action_spec, device, control = cls._build_climate_action(source.account, current)
        dedupe_key = f"weather-drop:{source.account_id}:{source.id}"
        title = f"外部温度下降了 {drop:.1f}°C"
        body = (
            f"当前温度约 {current:.1f}°C，较上次记录下降 {drop:.1f}°C。"
            + (" 已为你匹配到一个可调整的空调温度目标。" if action_spec else " 当前未找到可直接执行的空调目标。")
        )
        suggestion, _ = SuggestionAggregator.upsert(
            account=source.account,
            dedupe_key=dedupe_key,
            cooldown_hours=12,
            aggregation_marker=source.id,
            defaults={
                "account": source.account,
                "suggestion_type": CareSuggestion.SuggestionTypeChoices.CARE,
                "device": device,
                "control_target": control,
                "title": title,
                "body": body,
                "action_spec": action_spec,
                "priority": round(
                    (6.5 + min(drop / 10.0, 2.0))
                    * FeedbackLearner.feedback_adjust_factor(
                        account=source.account,
                        topic_key="care:event:weather_temperature_drop",
                    ),
                    2,
                ),
                "dedupe_key": dedupe_key,
                "source_event": {
                    "source_id": source.id,
                    "event": "weather_temperature_drop",
                    "current_temperature": current,
                    "previous_temperature": previous,
                    "drop": drop,
                },
            },
        )
        return suggestion

    @classmethod
    def _build_climate_action(cls, account, current_temperature: float):
        controls = (
            DeviceControl.objects.select_related("device")
            .filter(account=account, writable=True)
            .order_by("device__sort_order", "sort_order", "id")
        )
        target = next(
            (
                control
                for control in controls
                if "target_temperature" in control.key.lower() or "目标温度" in control.label
            ),
            None,
        )
        if target is None:
            return {}, None, None
        current_target = cls._to_float(target.value)
        next_value = current_target + 1 if current_target is not None else max(current_temperature + 2, 22)
        action_spec = {
            "device_id": target.device.external_id,
            "control_id": target.external_id,
            "control_key": target.key,
            "value": round(next_value),
        }
        return action_spec, target.device, target

    @classmethod
    def _to_float(cls, value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
