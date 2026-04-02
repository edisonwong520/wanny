from __future__ import annotations

from typing import Any

import requests

from devices.models import DeviceControl, DeviceSnapshot
from devices.services import DeviceDashboardService


class DeviceExecutor:
    """统一设备执行入口，负责错误归一化与替代方案推荐。"""

    @classmethod
    def execute(cls, account, *, control: DeviceControl, action: str = "", value: Any = None) -> dict:
        device = control.device
        if device.status == DeviceSnapshot.StatusChoices.OFFLINE:
            suggestion = cls._build_alternative_suggestion(account, device)
            return {
                "success": False,
                "message": f"{device.name} 当前离线，暂时无法操作。",
                "new_value": None,
                "error": "DEVICE_OFFLINE",
                "suggestion": suggestion,
            }

        try:
            result = cls._dispatch_execute(
                account,
                device=device,
                control=control,
                action=action,
                value=value,
            )
        except Exception as error:
            error_code, message = cls._normalize_error(error)
            suggestion = cls._build_alternative_suggestion(account, device)
            return {
                "success": False,
                "message": message,
                "new_value": None,
                "error": error_code,
                "suggestion": suggestion,
            }

        return {
            "success": True,
            "message": f"已执行 {device.name} / {control.label}",
            "new_value": result,
            "error": None,
            "suggestion": None,
        }

    @classmethod
    def _dispatch_execute(cls, account, *, device: DeviceSnapshot, control: DeviceControl, action: str, value: Any) -> dict:
        if control.source_type == DeviceControl.SourceTypeChoices.HA_ENTITY:
            return cls._execute_home_assistant(account, device=device, control=control, action=action, value=value)
        if control.source_type in {
            DeviceControl.SourceTypeChoices.MIJIA_PROPERTY,
            DeviceControl.SourceTypeChoices.MIJIA_ACTION,
        }:
            return cls._execute_mijia(account, device=device, control=control, action=action, value=value)
        if control.source_type in {
            DeviceControl.SourceTypeChoices.MIDEA_CLOUD_PROPERTY,
            DeviceControl.SourceTypeChoices.MIDEA_CLOUD_ACTION,
        }:
            return cls._execute_midea_cloud(account, device=device, control=control, action=action, value=value)
        if control.source_type in {
            DeviceControl.SourceTypeChoices.MBAPI2020_PROPERTY,
            DeviceControl.SourceTypeChoices.MBAPI2020_ACTION,
        }:
            return cls._execute_mbapi2020(account, device=device, control=control, action=action, value=value)
        raise ValueError(f"Unsupported control source: {control.source_type}")

    @classmethod
    def _execute_home_assistant(cls, account, *, device: DeviceSnapshot, control: DeviceControl, action: str, value: Any) -> dict:
        return DeviceDashboardService.execute_control(
            account,
            device_external_id=device.external_id,
            control_external_id=control.external_id,
            action=action,
            value=value,
        )

    @classmethod
    def _execute_mijia(cls, account, *, device: DeviceSnapshot, control: DeviceControl, action: str, value: Any) -> dict:
        return DeviceDashboardService.execute_control(
            account,
            device_external_id=device.external_id,
            control_external_id=control.external_id,
            action=action,
            value=value,
        )

    @classmethod
    def _execute_midea_cloud(cls, account, *, device: DeviceSnapshot, control: DeviceControl, action: str, value: Any) -> dict:
        return DeviceDashboardService.execute_control(
            account,
            device_external_id=device.external_id,
            control_external_id=control.external_id,
            action=action,
            value=value,
        )

    @classmethod
    def _execute_mbapi2020(cls, account, *, device: DeviceSnapshot, control: DeviceControl, action: str, value: Any) -> dict:
        return DeviceDashboardService.execute_control(
            account,
            device_external_id=device.external_id,
            control_external_id=control.external_id,
            action=action,
            value=value,
        )

    @classmethod
    def refresh_single_device(cls, account, *, device: DeviceSnapshot) -> dict:
        try:
            snapshot = DeviceDashboardService.refresh_device(
                account,
                device_external_id=device.external_id,
                trigger="query",
            )
        except Exception as error:
            error_code, message = cls._normalize_error(error)
            return {
                "success": False,
                "message": message,
                "snapshot": None,
                "error": error_code,
            }
        return {
            "success": True,
            "message": f"已刷新 {device.name} 当前状态。",
            "snapshot": snapshot,
            "error": None,
        }

    @classmethod
    def _normalize_error(cls, error: Exception) -> tuple[str, str]:
        message = str(error).strip() or "设备操作失败，请稍后重试。"
        lowered = message.lower()

        if isinstance(error, requests.Timeout) or "timeout" in lowered or "超时" in message:
            return "TIMEOUT", "设备响应超时，请稍后再试。"
        if "no active" in lowered or "authorization" in lowered or "auth" in lowered or "登录" in message or "授权" in message:
            return "AUTH_EXPIRED", "平台授权可能已失效，请重新登录后再试。"
        if "unsupported" in lowered or "read only" in lowered or "missing property value" in lowered:
            return "UNSUPPORTED_OPERATION", "该设备当前不支持这项操作。"
        if "offline" in lowered or "离线" in message:
            return "DEVICE_OFFLINE", "设备离线，暂时无法操作。"
        return "OPERATION_FAILED", f"设备操作失败: {message}"

    @classmethod
    def _build_alternative_suggestion(cls, account, device: DeviceSnapshot) -> str | None:
        candidates = DeviceSnapshot.objects.filter(
            account=account,
            category=device.category,
            status=DeviceSnapshot.StatusChoices.ONLINE,
        ).exclude(id=device.id)

        if device.room_id:
            same_room = candidates.filter(room=device.room).order_by("sort_order", "id").first()
            if same_room:
                return f"{device.room.name} 的 {same_room.name} 当前在线，您可以试试操作它。"

        other_room = candidates.order_by("sort_order", "id").first()
        if other_room:
            room_name = other_room.room.name if other_room.room else "其他房间"
            return f"{room_name} 的 {other_room.name} 当前在线，您可以试试操作它。"
        return None
