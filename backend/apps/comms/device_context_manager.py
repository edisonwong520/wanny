from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from comms.models import DeviceOperationContext


class DeviceContextManager:
    keep_limit = 20
    inherit_window = timedelta(minutes=5)

    @classmethod
    def record_operation(
        cls,
        *,
        account,
        device,
        control_id: str = "",
        control_key: str,
        operation_type: str,
        value,
        raw_user_msg: str = "",
        normalized_msg: str = "",
        voice_transcript: str = "",
        intent_json: dict | None = None,
        resolver_result: dict | None = None,
        execution_result: dict | None = None,
    ) -> DeviceOperationContext:
        record = DeviceOperationContext.objects.create(
            account=account,
            device=device,
            control_id=control_id,
            control_key=control_key,
            operation_type=operation_type,
            value=value,
            raw_user_msg=raw_user_msg,
            normalized_msg=normalized_msg,
            voice_transcript=voice_transcript,
            intent_json=intent_json or {},
            resolver_result=resolver_result or {},
            execution_result=execution_result or {},
        )
        stale_ids = list(
            DeviceOperationContext.objects.filter(account=account)
            .order_by("-operated_at")
            .values_list("id", flat=True)[cls.keep_limit:]
        )
        if stale_ids:
            DeviceOperationContext.objects.filter(id__in=stale_ids).delete()
        return record

    @classmethod
    def get_recent_context(cls, account, limit: int = 5) -> list[dict]:
        rows = (
            DeviceOperationContext.objects.filter(account=account)
            .select_related("device__room")
            .order_by("-operated_at")[:limit]
        )
        return [
            {
                "room": row.device.room.name if row.device.room else "",
                "device": row.device.name,
                "control": row.control_key,
                "value": row.value,
                "operated_at": cls._humanize_operated_at(row.operated_at),
            }
            for row in rows
        ]

    @classmethod
    def get_last_operation(cls, account) -> DeviceOperationContext | None:
        return (
            DeviceOperationContext.objects.filter(account=account)
            .select_related("device__room")
            .order_by("-operated_at")
            .first()
        )

    @classmethod
    def get_last_operated_device(cls, account):
        row = cls.get_last_operation(account)
        return row.device if row else None

    @classmethod
    def is_recent(cls, row: DeviceOperationContext | None) -> bool:
        if row is None:
            return False
        return timezone.now() - row.operated_at <= cls.inherit_window

    @classmethod
    def _humanize_operated_at(cls, operated_at) -> str:
        delta = timezone.now() - operated_at
        total_seconds = max(int(delta.total_seconds()), 0)
        if total_seconds < 60:
            return "刚刚"
        if total_seconds < 3600:
            return f"{max(total_seconds // 60, 1)}分钟前"
        if total_seconds < 86400:
            return f"{max(total_seconds // 3600, 1)}小时前"
        return f"{max(total_seconds // 86400, 1)}天前"
