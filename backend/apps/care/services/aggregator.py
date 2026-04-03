from __future__ import annotations

from datetime import datetime, timedelta

from care.models import CareSuggestion


class SuggestionAggregator:
    active_statuses = [
        CareSuggestion.StatusChoices.PENDING,
        CareSuggestion.StatusChoices.APPROVED,
        CareSuggestion.StatusChoices.IGNORED,
        CareSuggestion.StatusChoices.EXECUTED,
    ]

    @classmethod
    def _find_recent(cls, *, account, dedupe_key: str, cooldown_hours: int) -> CareSuggestion | None:
        if not dedupe_key:
            return None
        threshold = datetime.now() - timedelta(hours=max(int(cooldown_hours or 0), 0))
        return (
            CareSuggestion.objects.filter(
                account=account,
                dedupe_key=dedupe_key,
                created_at__gte=threshold,
                status__in=cls.active_statuses,
            )
            .order_by("-created_at", "-id")
            .first()
        )

    @classmethod
    def should_create(cls, *, account, dedupe_key: str, cooldown_hours: int) -> bool:
        return cls._find_recent(account=account, dedupe_key=dedupe_key, cooldown_hours=cooldown_hours) is None

    @classmethod
    def upsert(
        cls,
        *,
        account,
        dedupe_key: str,
        cooldown_hours: int,
        defaults: dict,
        aggregation_marker: int | str | None = None,
    ) -> tuple[CareSuggestion, bool]:
        existing = cls._find_recent(account=account, dedupe_key=dedupe_key, cooldown_hours=cooldown_hours)
        if existing is None:
            markers = []
            if aggregation_marker not in (None, ""):
                markers = [aggregation_marker]
            return CareSuggestion.objects.create(
                aggregated_count=max(int(defaults.get("aggregated_count") or 1), 1),
                aggregated_from=markers,
                **defaults,
            ), True

        existing.priority = max(float(existing.priority or 0), float(defaults.get("priority") or 0))
        existing.aggregated_count = max(int(existing.aggregated_count or 1) + 1, 2)
        existing.aggregated_from = cls._merge_markers(existing.aggregated_from, aggregation_marker)
        existing.source_event = cls._merge_source_event(existing.source_event, defaults.get("source_event"))
        if existing.status == CareSuggestion.StatusChoices.IGNORED:
            existing.status = CareSuggestion.StatusChoices.PENDING
        existing.updated_at = datetime.now()
        existing.save(update_fields=["priority", "aggregated_count", "aggregated_from", "source_event", "status", "updated_at"])
        return existing, False

    @classmethod
    def _merge_markers(cls, current: list | None, marker: int | str | None) -> list:
        merged = list(current) if isinstance(current, list) else []
        if marker not in (None, "") and marker not in merged:
            merged.append(marker)
        return merged

    @classmethod
    def _merge_source_event(cls, current: dict | None, incoming: dict | None) -> dict:
        current_payload = dict(current) if isinstance(current, dict) else {}
        events = list(current_payload.get("events") or [])
        if not events and current_payload:
            base = {key: value for key, value in current_payload.items() if key != "events"}
            if base:
                events.append(base)
        if isinstance(incoming, dict) and incoming:
            events.append(incoming)
        if not events:
            return current_payload
        latest = dict(events[-1])
        latest["events"] = events
        return latest
