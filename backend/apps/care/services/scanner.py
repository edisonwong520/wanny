from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from django.db.models import Q

from accounts.models import Account
from care.models import CareSuggestion, InspectionRule
from care.services.aggregator import SuggestionAggregator
from care.services.learner import FeedbackLearner
from devices.models import DeviceControl, DeviceSnapshot


@dataclass
class CandidateSuggestion:
    account: Account
    rule: InspectionRule
    device: DeviceSnapshot
    control: DeviceControl | None
    title: str
    body: str
    action_spec: dict
    priority: float
    dedupe_key: str
    source_event: dict


class InspectionScanner:
    operator_map = {
        "<": lambda left, right: left < right,
        "<=": lambda left, right: left <= right,
        ">": lambda left, right: left > right,
        ">=": lambda left, right: left >= right,
        "==": lambda left, right: left == right,
        "!=": lambda left, right: left != right,
        "contains": lambda left, right: str(right) in str(left),
        "exists": lambda left, right: bool(left) is bool(right),
    }

    @classmethod
    def scan_account(cls, account: Account) -> list[CareSuggestion]:
        rules = [
            *InspectionRule.objects.filter(is_active=True, account=account).order_by("id"),
            *InspectionRule.objects.filter(is_active=True, account__isnull=True).order_by("id"),
        ]
        created: list[CareSuggestion] = []
        for rule in rules:
            for candidate in cls._generate_candidates(account, rule):
                suggestion, created_now = SuggestionAggregator.upsert(
                    account=account,
                    dedupe_key=candidate.dedupe_key,
                    cooldown_hours=rule.cooldown_hours,
                    aggregation_marker=rule.id,
                    defaults={
                        "account": account,
                        "suggestion_type": CareSuggestion.SuggestionTypeChoices.INSPECTION,
                        "source_rule": rule,
                        "device": candidate.device,
                        "control_target": candidate.control,
                        "title": candidate.title,
                        "body": candidate.body,
                        "action_spec": candidate.action_spec,
                        "priority": candidate.priority,
                        "dedupe_key": candidate.dedupe_key,
                        "source_event": candidate.source_event,
                    },
                )
                if created_now:
                    created.append(suggestion)
        return created

    @classmethod
    def scan_all_accounts(cls) -> int:
        total = 0
        for account in Account.objects.all().order_by("id"):
            total += len(cls.scan_account(account))
        return total

    @classmethod
    def _generate_candidates(cls, account: Account, rule: InspectionRule) -> list[CandidateSuggestion]:
        devices = DeviceSnapshot.objects.filter(account=account)
        if rule.device_category:
            devices = devices.filter(category__icontains=rule.device_category)

        candidates: list[CandidateSuggestion] = []
        for device in devices.prefetch_related("controls"):
            resolved = cls._resolve_condition_target(device, rule.condition_spec)
            if resolved is None:
                continue
            current_value, control = resolved
            if not cls._matches_condition(current_value, rule.condition_spec):
                continue
            title = cls._render_template(
                rule.suggestion_template or "{device_name} 需要关注",
                device=device,
                control=control,
                current_value=current_value,
                threshold=rule.condition_spec.get("threshold"),
            )
            body = cls._build_body(rule, device, control, current_value)
            action_spec = cls._build_action_spec(rule, device, control)
            field_key = str(rule.condition_spec.get("field") or "device").strip().lower()
            dedupe_key = f"{device.external_id}:{control.external_id if control else 'device'}:{field_key}"
            candidates.append(
                CandidateSuggestion(
                    account=account,
                    rule=rule,
                    device=device,
                    control=control,
                    title=title,
                    body=body,
                    action_spec=action_spec,
                    priority=cls._compute_priority(account, rule, current_value),
                    dedupe_key=dedupe_key,
                    source_event={"current_value": current_value, "threshold": rule.condition_spec.get("threshold")},
                )
            )
        return candidates

    @classmethod
    def _resolve_condition_target(cls, device: DeviceSnapshot, condition_spec: dict) -> tuple[Any, DeviceControl | None] | None:
        field = str(condition_spec.get("field") or "").strip()
        if not field:
            return None
        if field.startswith("device."):
            return cls._resolve_device_path(device, field.removeprefix("device.")), None
        if field == "device_offline_hours":
            if not device.last_seen:
                return None
            return (datetime.now() - device.last_seen).total_seconds() / 3600.0, None
        control_key = field.removeprefix("control.") if field.startswith("control.") else field
        normalized_key = control_key.lower()
        for control in device.controls.all():
            if control.key.lower() == normalized_key or control.label.lower() == normalized_key:
                return control.value, control
        return None

    @classmethod
    def _resolve_device_path(cls, device: DeviceSnapshot, path: str):
        if hasattr(device, path):
            return getattr(device, path)
        current: Any = device.source_payload if isinstance(device.source_payload, dict) else {}
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    @classmethod
    def _matches_condition(cls, current_value: Any, condition_spec: dict) -> bool:
        operator = str(condition_spec.get("operator") or "").strip().lower()
        threshold = condition_spec.get("threshold")
        if operator not in cls.operator_map:
            return False
        current_value = cls._normalize_value(current_value)
        threshold = cls._normalize_value(threshold)
        if current_value is None and operator != "exists":
            return False
        try:
            return bool(cls.operator_map[operator](current_value, threshold))
        except Exception:
            return False

    @classmethod
    def _normalize_value(cls, value: Any):
        if isinstance(value, dict) and "value" in value and len(value) == 1:
            return cls._normalize_value(value["value"])
        if isinstance(value, bool) or value is None:
            return value
        if isinstance(value, (int, float)):
            return value
        text = str(value).strip()
        if not text:
            return None
        lowered = text.lower()
        if lowered in {"true", "false"}:
            return lowered == "true"
        try:
            return float(text) if "." in text else int(text)
        except ValueError:
            return text

    @classmethod
    def _render_template(cls, template: str, *, device: DeviceSnapshot, control: DeviceControl | None, current_value, threshold) -> str:
        return template.format(
            device_name=device.name,
            device_category=device.category,
            control_label=control.label if control else "设备",
            current_value=current_value,
            threshold=threshold,
        )

    @classmethod
    def _build_body(cls, rule: InspectionRule, device: DeviceSnapshot, control: DeviceControl | None, current_value) -> str:
        parts = [rule.description.strip()] if rule.description else []
        if control is not None:
            parts.append(f"{device.name} 的 {control.label} 当前为 {current_value}。")
        else:
            parts.append(f"{device.name} 当前状态触发了规则「{rule.name}」。")
        return " ".join(part for part in parts if part).strip()

    @classmethod
    def _build_action_spec(cls, rule: InspectionRule, device: DeviceSnapshot, control: DeviceControl | None) -> dict:
        template = dict(rule.action_spec or {})
        if control is not None:
            template.setdefault("device_id", device.external_id)
            template.setdefault("control_id", control.external_id)
            template.setdefault("control_key", control.key)
            template.setdefault("provider", control.source_type)
        return template

    @classmethod
    def _compute_priority(cls, account: Account, rule: InspectionRule, current_value: Any) -> float:
        threshold = cls._normalize_value(rule.condition_spec.get("threshold"))
        value = cls._normalize_value(current_value)
        priority = float(rule.priority or 0)
        if isinstance(value, (int, float)) and isinstance(threshold, (int, float)) and threshold:
            if value < threshold:
                priority += min((threshold - value) / max(abs(threshold), 1), 1.0) * 3
        topic_key = f"care:rule:{rule.system_key}" if rule.system_key else f"care:rule:{rule.id}"
        priority *= FeedbackLearner.feedback_adjust_factor(account=account, topic_key=topic_key)
        return round(priority, 2)
