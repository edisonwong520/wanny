from __future__ import annotations

import re
import time

from asgiref.sync import sync_to_async

from brain.models import HabitPolicy, HomeMode
from comms.device_context_manager import DeviceContextManager
from devices.executor import DeviceExecutor
from devices.models import DeviceControl
from devices.services import DeviceDashboardService
from utils.logger import logger
from utils.telemetry import get_tracer


def _normalize_text(value: str | None) -> str:
    return "".join(str(value or "").strip().lower().split())


class DeviceCommandService:
    inheritable_control_hints = {
        "brightness",
        "temperature",
        "target_temperature",
        "volume",
        "fan",
        "speed",
        "color_temp",
    }

    high_risk_hints = {"lock", "unlock", "open", "door", "garage", "alarm"}
    control_aliases = {
        "power": {"power", "电源", "开关", "总电源"},
        "brightness": {"brightness", "亮度", "灯光亮度"},
        "temperature": {"temperature", "targettemperature", "目标温度", "温度", "多少度"},
        "mode": {"mode", "模式", "hvacmode", "presetmode", "fanmode"},
        "fan_mode": {"fanmode", "风速", "风速模式", "预设模式"},
        "volume": {"volume", "volumelevel", "音量"},
        "color_temp": {"colortemp", "色温"},
        "tanklevelpercent": {"tanklevelpercent", "油量", "剩余油量", "汽油", "油箱", "油位"},
        "rangeelectric": {"rangeelectric", "续航", "续航里程"},
        "doorlockstatusvehicle": {"doorlockstatusvehicle", "车锁", "车门锁", "锁车状态"},
    }
    tracer = get_tracer(__name__)

    @classmethod
    async def resolve_device_target(cls, account, intent: dict) -> dict:
        room_text = _normalize_text(intent.get("room"))
        device_text = _normalize_text(intent.get("device"))
        control_text = _normalize_text(intent.get("control_key"))
        desired_value = intent.get("value")

        controls = await sync_to_async(list)(
            DeviceControl.objects.filter(account=account)
            .select_related("device__room")
            .order_by("device__sort_order", "sort_order", "id")
        )

        candidates = []
        for control in controls:
            device = control.device
            if intent.get("type") == "DEVICE_CONTROL" and not control.writable:
                continue
            score = 0.0
            room_name = _normalize_text(device.room.name if device.room else "")
            device_name = _normalize_text(device.name)
            category_text = _normalize_text(device.category)
            external_id_text = _normalize_text(device.external_id)
            note_text = _normalize_text(device.note)
            telemetry_text = _normalize_text(device.telemetry)
            source_payload = device.source_payload if isinstance(device.source_payload, dict) else {}
            license_plate_text = _normalize_text(
                source_payload.get("license_plate") or source_payload.get("licensePlate") or source_payload.get("raw", {}).get("licensePlate")
            )
            label_text = _normalize_text(control.label)
            key_text = _normalize_text(control.key)
            alias_matches = cls._control_alias_match_score(control_text, key_text=key_text, label_text=label_text)

            if room_text:
                if room_text == room_name:
                    score += 2.0
                elif room_text in room_name or room_name in room_text:
                    score += 1.0
                else:
                    continue
            if device_text:
                vehicle_alias_match = (
                    category_text == "vehicle" and device_text in {"奔驰", "车辆", "汽车", "车"}
                )
                if device_text == device_name:
                    score += 2.0
                elif device_text in device_name or device_name in device_text:
                    score += 1.0
                elif vehicle_alias_match:
                    score += 1.5
                elif device_text in category_text or device_text in external_id_text:
                    score += 1.0
                elif device_text in license_plate_text or device_text in note_text or device_text in telemetry_text:
                    score += 1.0
                else:
                    continue
            if control_text:
                if control_text in {key_text, label_text}:
                    score += 2.0
                elif control_text in key_text or control_text in label_text:
                    score += 1.0
                elif alias_matches:
                    score += alias_matches
                else:
                    continue
            else:
                score += cls._infer_control_score_from_value(control, desired_value)
            if not room_text and not device_text and not control_text:
                continue
            candidates.append((score, control))

        resolved_from_context = False
        if not candidates:
            inherited = await sync_to_async(cls._resolve_from_context)(account, intent)
            if inherited:
                return inherited

        if not candidates:
            return {
                "matched_device": None,
                "matched_control": None,
                "confidence": 0.0,
                "ambiguous": True,
                "resolved_from_context": False,
                "alternatives": [],
            }

        candidates.sort(key=lambda item: (-item[0], item[1].sort_order, item[1].id))
        best_score, best_control = candidates[0]
        same_rank = [item for item in candidates if item[0] == best_score]
        ambiguous = len(same_rank) > 1
        confidence = 1.0 if best_score >= 4.0 and not ambiguous else 0.7 if best_score >= 2.0 else 0.5
        return {
            "matched_device": best_control.device,
            "matched_control": best_control,
            "confidence": confidence,
            "ambiguous": ambiguous,
            "resolved_from_context": resolved_from_context,
            "alternatives": [
                {
                    "room": item.device.room.name if item.device.room else "",
                    "device": item.device.name,
                    "control": item.label,
                    "device_id": item.device.external_id,
                    "control_id": item.external_id,
                }
                for _, item in same_rank[:5]
            ],
        }

    @classmethod
    def _resolve_from_context(cls, account, intent: dict) -> dict | None:
        control_key = _normalize_text(intent.get("control_key"))
        if not cls._is_inheritable_control(control_key):
            return None
        last_operation = DeviceContextManager.get_last_operation(account)
        if not DeviceContextManager.is_recent(last_operation):
            return None
        device = last_operation.device
        control = (
            DeviceControl.objects.filter(account=account, device=device, writable=True)
            .order_by("sort_order", "id")
            .first()
        )
        if control is None:
            return None
        if control_key and control_key not in _normalize_text(control.key) and control_key not in _normalize_text(control.label):
            matching = (
                DeviceControl.objects.filter(account=account, device=device, writable=True)
                .order_by("sort_order", "id")
            )
            control = next(
                (
                    item for item in matching
                    if control_key in _normalize_text(item.key) or control_key in _normalize_text(item.label)
                ),
                None,
            )
            if control is None:
                return None
        return {
            "matched_device": device,
            "matched_control": control,
            "confidence": 0.6,
            "ambiguous": False,
            "resolved_from_context": True,
            "alternatives": [],
        }

    @classmethod
    def _is_inheritable_control(cls, control_key: str) -> bool:
        if not control_key:
            return False
        return any(hint in control_key for hint in cls.inheritable_control_hints)

    @classmethod
    def _control_alias_match_score(cls, control_text: str, *, key_text: str, label_text: str) -> float:
        if not control_text:
            return 0.0
        for _, aliases in cls.control_aliases.items():
            normalized_aliases = {_normalize_text(alias) for alias in aliases}
            if control_text in normalized_aliases and (key_text in normalized_aliases or label_text in normalized_aliases):
                return 1.5
        return 0.0

    @classmethod
    def _infer_control_score_from_value(cls, control: DeviceControl, desired_value) -> float:
        if control.kind == DeviceControl.KindChoices.TOGGLE and isinstance(desired_value, bool):
            return 1.5
        if control.kind == DeviceControl.KindChoices.RANGE and isinstance(desired_value, (int, float)):
            return 1.2
        if control.kind == DeviceControl.KindChoices.ENUM and isinstance(desired_value, str):
            return 0.8
        return 0.0

    @classmethod
    async def check_authorization(cls, account, resolved: dict, *, command_mode: bool = False) -> dict:
        control = resolved.get("matched_control")
        device = resolved.get("matched_device")
        if control is None or device is None:
            return {
                "allowed": False,
                "need_confirm": False,
                "policy": "DENY",
                "reason": "missing_target",
            }

        if command_mode:
            need_confirm = bool(
                resolved.get("ambiguous")
                or resolved.get("resolved_from_context")
                or resolved.get("confidence", 0) < 0.8
                or cls._is_high_risk_control(control)
            )
            return {
                "allowed": True,
                "need_confirm": need_confirm,
                "policy": "ASK" if need_confirm else "DIRECT",
                "reason": "command_mode",
            }

        result = await sync_to_async(cls._check_habit_policy)(device, control)
        return result

    @classmethod
    def _check_habit_policy(cls, device, control) -> dict:
        active_mode = HomeMode.objects.filter(is_active=True).first()
        if active_mode is None:
            return {
                "allowed": True,
                "need_confirm": True,
                "policy": HabitPolicy.PolicyChoices.ASK,
                "reason": "no_active_mode",
            }
        did = str((device.source_payload or {}).get("did") or "").strip()
        if not did:
            return {
                "allowed": True,
                "need_confirm": True,
                "policy": HabitPolicy.PolicyChoices.ASK,
                "reason": "no_device_did",
            }
        policy = HabitPolicy.objects.filter(mode=active_mode, device_did=did, property=control.key).first()
        if policy is None:
            return {
                "allowed": True,
                "need_confirm": True,
                "policy": HabitPolicy.PolicyChoices.ASK,
                "reason": "no_policy",
            }
        if policy.policy == HabitPolicy.PolicyChoices.ALWAYS:
            return {"allowed": True, "need_confirm": False, "policy": policy.policy, "reason": "always"}
        if policy.policy == HabitPolicy.PolicyChoices.NEVER:
            return {"allowed": False, "need_confirm": False, "policy": policy.policy, "reason": "never"}
        return {"allowed": True, "need_confirm": True, "policy": policy.policy, "reason": "ask"}

    @classmethod
    def _is_high_risk_control(cls, control: DeviceControl) -> bool:
        key_text = _normalize_text(control.key)
        label_text = _normalize_text(control.label)
        return any(hint in key_text or hint in label_text for hint in cls.high_risk_hints)

    @classmethod
    async def execute_device_operation(cls, account, *, control_id: str, operation_action: str = "", operation_value=None) -> dict:
        control = await sync_to_async(
            lambda: DeviceControl.objects.select_related("device").filter(account=account, external_id=control_id).first()
        )()
        if control is None:
            return {"success": False, "message": "未找到要执行的设备控制。", "error": "CONTROL_NOT_FOUND", "suggestion": None}

        action, value = cls._build_execution_payload(control, operation_action, operation_value)
        return await sync_to_async(DeviceExecutor.execute)(
            account,
            control=control,
            action=action,
            value=value,
        )

    @classmethod
    def _build_execution_payload(cls, control: DeviceControl, operation_action: str, operation_value):
        action = operation_action or ""
        value = operation_value
        if isinstance(operation_value, dict) and "value" in operation_value and len(operation_value) == 1:
            value = operation_value["value"]
        value = cls._resolve_relative_value(control, value)
        if control.kind == DeviceControl.KindChoices.TOGGLE:
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {"on", "true", "1"}:
                    value = True
                elif lowered in {"off", "false", "0"}:
                    value = False
            if action == "":
                action = "turn_on" if value in (True, 1, "on", "true") else "turn_off"
        return action, value

    @classmethod
    def _resolve_relative_value(cls, control: DeviceControl, value):
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized or normalized[0] not in {"+", "-"}:
            return value
        current = control.value
        if isinstance(current, str):
            try:
                current = float(current)
            except ValueError:
                return value
        if not isinstance(current, (int, float)):
            return value
        if normalized.endswith("%"):
            try:
                delta = float(normalized[:-1])
            except ValueError:
                return value
            return current + delta
        try:
            delta = float(normalized)
        except ValueError:
            return value
        return current + delta

    @classmethod
    async def execute_device_query(cls, resolved: dict, *, account) -> dict:
        with cls.tracer.start_as_current_span("device.execute_query") as span:
            started_at = time.perf_counter()
            control = resolved.get("matched_control")
            device = resolved.get("matched_device")
            if control is None or device is None:
                span.set_attribute("device.query.success", False)
                return {"success": False, "message": "没有找到对应设备。"}
            span.set_attribute("device.name", device.name)
            span.set_attribute("device.control", control.label)
            refreshed_control = await sync_to_async(cls._refresh_query_target)(
                device_external_id=device.external_id,
                control_external_id=control.external_id,
                account=account,
            )
            if refreshed_control is not None:
                control = refreshed_control
                device = refreshed_control.device
            suffix = f" {control.unit}".rstrip() if control.unit else ""
            elapsed = time.perf_counter() - started_at
            span.set_attribute("device.query.success", True)
            span.set_attribute("device.query.elapsed_seconds", elapsed)
            logger.info(
                f"[Device Query] 查询完成: device={device.name}, control={control.label}, elapsed={elapsed:.2f}s"
            )
            return {
                "success": True,
                "message": cls._build_query_reply(device_name=device.name, control=control, suffix=suffix),
            }

    @classmethod
    def _refresh_query_target(cls, *, device_external_id: str, control_external_id: str, account):
        control = DeviceControl.objects.select_related("device").filter(
            account=account,
            external_id=control_external_id,
        ).first()
        if control is None:
            return None
        try:
            DeviceExecutor.refresh_single_device(
                account,
                device=control.device,
            )
        except Exception:
            return control
        return DeviceControl.objects.select_related("device").filter(
            account=account,
            external_id=control_external_id,
        ).first()

    @classmethod
    def _build_query_reply(cls, *, device_name: str, control: DeviceControl, suffix: str) -> str:
        value = control.value
        if control.kind == DeviceControl.KindChoices.TOGGLE:
            normalized = str(value).strip().lower()
            if normalized in {"on", "true", "1"}:
                value = "开启"
                suffix = ""
            elif normalized in {"off", "false", "0"}:
                value = "关闭"
                suffix = ""
        return f"{device_name} 的 {control.label} 当前为 {value}{suffix}"

    @classmethod
    async def resolve_clarification_choice(cls, account, mission, user_msg: str) -> dict | None:
        return await sync_to_async(cls._resolve_clarification_choice_sync)(account, mission, user_msg)

    @classmethod
    def _resolve_clarification_choice_sync(cls, account, mission, user_msg: str) -> dict | None:
        metadata = mission.metadata or {}
        alternatives = metadata.get("alternatives_snapshot") or metadata.get("resolver_result", {}).get("alternatives") or []
        normalized = _normalize_text(user_msg)
        if not alternatives:
            return None

        ordinal_map = {
            "1": 0,
            "第一个": 0,
            "第1个": 0,
            "第一个设备": 0,
            "2": 1,
            "第二个": 1,
            "第2个": 1,
            "3": 2,
            "第三个": 2,
            "第3个": 2,
        }
        for key, index in ordinal_map.items():
            if _normalize_text(key) in normalized and index < len(alternatives):
                return cls._build_resolved_target_from_alternative(account, alternatives[index])

        scored_matches = []
        for alternative in alternatives:
            score = 0
            room_text = _normalize_text(alternative.get("room"))
            device_text = _normalize_text(alternative.get("device"))
            control_text = _normalize_text(alternative.get("control"))
            if room_text and room_text in normalized:
                score += 2
            if device_text and device_text in normalized:
                score += 3
            if control_text and control_text in normalized:
                score += 1
            if score:
                scored_matches.append((score, alternative))

        if not scored_matches:
            return None
        scored_matches.sort(key=lambda item: -item[0])
        if len(scored_matches) > 1 and scored_matches[0][0] == scored_matches[1][0]:
            return None
        return cls._build_resolved_target_from_alternative(account, scored_matches[0][1])

    @classmethod
    def _build_resolved_target_from_alternative(cls, account, alternative: dict) -> dict | None:
        control = DeviceControl.objects.select_related("device__room").filter(
            account=account,
            external_id=alternative.get("control_id", ""),
        ).first()
        if control is None:
            return None
        return {
            "matched_device": control.device,
            "matched_control": control,
            "confidence": 1.0,
            "ambiguous": False,
            "resolved_from_context": False,
            "alternatives": [],
        }
