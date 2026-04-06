from __future__ import annotations

import hashlib
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter, defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

import requests
from django.db import transaction
from django.utils import timezone

from providers.models import PlatformAuth
from providers.clients.midea_cloud import get_device_mapping
from utils.logger import logger
from utils.telemetry import get_tracer

from .queue import enqueue_account_refresh, get_queue_backend, redis_queue_enabled
from .models import (
    DeviceAnomaly,
    DeviceAutomationRule,
    DeviceControl,
    DeviceDashboardState,
    DeviceRoom,
    DeviceSnapshot,
)

if TYPE_CHECKING:
    from accounts.models import Account


class DeviceDashboardService:
    tracer = get_tracer(__name__)
    state_key = "default"
    default_sync_interval_seconds = 300
    device_provider_names = ("mijia", "home_assistant", "midea_cloud", "mbapi2020", "hisense_ha")
    supported_ha_domains = {
        "light",
        "switch",
        "fan",
        "climate",
        "sensor",
        "binary_sensor",
        "cover",
        "lock",
        "camera",
        "media_player",
        "humidifier",
        "vacuum",
        "number",
        "input_number",
        "select",
        "button",
        "scene",
        "script",
        "input_boolean",
    }
    ha_service_domains = {"light", "switch", "fan", "humidifier", "cover", "vacuum", "media_player", "script", "scene"}
    # These are protocol/debug fields from Midea payloads that add noise on
    # the device page and should not be shown as user-facing telemetry.
    midea_cloud_extra_status_ignore_keys = {
        "cmd",
        "hex_length",
        "msg_type",
        "sub_msg_type",
        "version",
        "device_version",
        "ota_version",
        "cur_firmware_version",
        "upgrade_firmware_version",
        "firmware_state",
        "firmware_upgrade_progress",
        "app_flag",
        "operator",
    }
    mijia_spec_cache_dir = Path(__file__).resolve().parents[2] / "runtime_cache" / "mijia_specs"
    mbapi2020_command_groups = (
        {
            "key": "door_lock",
            "label": "车门锁",
            "group_label": "车身",
            "commands": (
                {"name": "DOORS_LOCK", "label": "锁车"},
                {"name": "DOORS_UNLOCK", "label": "解锁", "requires_pin": True},
            ),
        },
        {
            "key": "preconditioning",
            "label": "空调预热",
            "group_label": "空调",
            "commands": (
                {"name": "ZEV_PRECONDITIONING_START", "label": "开启"},
                {"name": "ZEV_PRECONDITIONING_STOP", "label": "关闭"},
            ),
        },
        {
            "key": "battery_conditioning",
            "label": "电池预处理",
            "group_label": "电池",
            "commands": (
                {"name": "HVBATTERY_START_CONDITIONING", "label": "开启"},
                {"name": "HVBATTERY_STOP_CONDITIONING", "label": "关闭"},
            ),
        },
        {
            "key": "sigpos",
            "label": "寻车闪灯",
            "group_label": "车身",
            "commands": (
                {"name": "SIGPOS_START", "label": "执行"},
            ),
        },
    )
    mbapi2020_status_value_maps = {
        "doorlockstatusvehicle": {
            "0": "未锁车",
            "1": "车内锁止",
            "2": "已锁车",
            "3": "部分未锁",
            "4": "状态未知",
            "locked": "已锁车",
            "unlocked": "未锁车",
        },
        "doorstatusoverall": {
            "0": "有车门开启",
            "1": "全部关闭",
            "2": "无此状态",
            "3": "状态未知",
        },
        "decklidstatus": {
            "false": "已关闭",
            "true": "已打开",
            "open": "已打开",
            "opened": "已打开",
            "closed": "已关闭",
            "close": "已关闭",
            "locked": "已关闭",
            "unlocked": "已打开",
        },
        "chargingstatusdisplay": {
            "0": "充电中",
            "1": "充电即将结束",
            "2": "充电暂停",
            "3": "未连接",
            "4": "故障",
            "5": "慢充",
            "6": "快充",
            "7": "放电中",
            "8": "未充电",
            "9": "到达目的地后慢充",
            "10": "到达目的地后充电",
            "11": "到达目的地后快充",
            "12": "已连接",
            "13": "交流充电",
            "14": "直流充电",
            "15": "电池校准中",
            "16": "状态未知",
            "charging": "充电中",
            "not_charging": "未充电",
            "not charging": "未充电",
            "disconnected": "未连接",
            "connected": "已连接",
            "complete": "已充满",
            "finished": "已完成",
        },
        "windowstatusfrontleft": {"2": "已关闭", "0": "已打开", "1": "已打开"},
        "windowstatusfrontright": {"2": "已关闭", "0": "已打开", "1": "已打开"},
        "windowstatusrearleft": {"2": "已关闭", "0": "已打开", "1": "已打开"},
        "windowstatusrearright": {"2": "已关闭", "0": "已打开", "1": "已打开"},
        "sunroofstatus": {
            "0": "已关闭",
            "1": "已打开",
            "2": "上掀开启",
            "3": "运行中",
            "4": "静音位置",
            "5": "半开滑动",
            "6": "半开上掀",
            "7": "开启中",
            "8": "关闭中",
            "9": "向静音位上掀",
            "10": "中间位置",
            "11": "开启并上掀",
            "12": "关闭并上掀",
        },
        "chargeflapacstatus": {"0": "已打开", "1": "已关闭", "2": "已按压", "3": "状态未知"},
        "chargeflapdcstatus": {"0": "已打开", "1": "已关闭", "2": "已按压", "3": "状态未知"},
        "starterbatterystate": {"0": "正常", "1": "偏低", "2": "告警"},
        "tirewarningsrdk": {"0": "无告警", "1": "轻微告警", "2": "胎压过低", "3": "漏气"},
        "warningbrakefluid": {"false": "正常", "true": "告警"},
        "parkbrakestatus": {"false": "未启用", "true": "已启用"},
        "trackingstatehu": {"false": "未启用", "true": "已启用"},
        "enginestate": {"false": "已熄火", "true": "运行中"},
        "remotestartactive": {"false": "未启动", "true": "已启动"},
        "doorstatusfrontleft": {"false": "已关闭", "true": "已打开"},
        "doorstatusfrontright": {"false": "已关闭", "true": "已打开"},
        "doorstatusrearleft": {"false": "已关闭", "true": "已打开"},
        "doorstatusrearright": {"false": "已关闭", "true": "已打开"},
        "enginehoodstatus": {"false": "已关闭", "true": "已打开"},
        "doorlockstatusfrontleft": {"false": "已锁止", "true": "已解锁"},
        "doorlockstatusfrontright": {"false": "已锁止", "true": "已解锁"},
        "doorlockstatusrearleft": {"false": "已锁止", "true": "已解锁"},
        "doorlockstatusrearright": {"false": "已锁止", "true": "已解锁"},
        "doorlockstatusdecklid": {"false": "已锁止", "true": "已解锁"},
        "doorlockstatusgas": {"false": "已锁止", "true": "已解锁"},
    }
    mbapi2020_status_label_maps = {
        "doorstatusoverall": "车门总状态",
        "windowstatusfrontleft": "左前窗",
        "windowstatusfrontright": "右前窗",
        "windowstatusrearleft": "左后窗",
        "windowstatusrearright": "右后窗",
        "doorstatusfrontleft": "左前门",
        "doorstatusfrontright": "右前门",
        "doorstatusrearleft": "左后门",
        "doorstatusrearright": "右后门",
        "doorlockstatusfrontleft": "左前门锁",
        "doorlockstatusfrontright": "右前门锁",
        "doorlockstatusrearleft": "左后门锁",
        "doorlockstatusrearright": "右后门锁",
        "doorlockstatusdecklid": "后备箱锁",
        "doorlockstatusgas": "油箱盖锁",
        "enginehoodstatus": "引擎盖",
        "sunroofstatus": "天窗状态",
        "starterbatterystate": "启动电瓶状态",
        "tirewarningsrdk": "胎压告警",
        "warningbrakefluid": "制动液状态",
        "parkbrakestatus": "驻车制动",
        "trackingstatehu": "追踪功能",
        "enginestate": "发动机状态",
        "remotestartactive": "远程启动",
        "chargeflapacstatus": "交流充电口盖",
        "chargeflapdcstatus": "直流充电口盖",
    }

    @classmethod
    def _provider_refresh_tasks(cls) -> tuple[dict[str, Any], ...]:
        from providers.services import (
            HisenseHAAuthService,
            HomeAssistantAuthService,
            MbApi2020AuthService,
            MideaCloudAuthService,
            MijiaAuthService,
        )

        return (
            {
                "platform": "mijia",
                "auth_service": MijiaAuthService,
                "builder": cls._build_mijia_snapshot,
                "label": "Mijia",
            },
            {
                "platform": "home_assistant",
                "auth_service": HomeAssistantAuthService,
                "builder": cls._build_home_assistant_snapshot,
                "label": "HomeAssistant",
            },
            {
                "platform": "midea_cloud",
                "auth_service": MideaCloudAuthService,
                "builder": cls._build_midea_cloud_snapshot,
                "label": "MideaCloud",
            },
            {
                "platform": "mbapi2020",
                "auth_service": MbApi2020AuthService,
                "builder": cls._build_mbapi2020_snapshot,
                "label": "MbApi2020",
            },
            {
                "platform": "hisense_ha",
                "auth_service": HisenseHAAuthService,
                "builder": cls._build_hisense_ha_snapshot,
                "label": "HisenseHA",
            },
        )

    @classmethod
    def _run_provider_refresh_task(cls, account: Account, task: dict[str, Any]) -> dict:
        provider_started_at = time.perf_counter()
        with cls.tracer.start_as_current_span("devices.provider_refresh") as span:
            span.set_attribute("devices.account_id", account.id)
            span.set_attribute("devices.provider", str(task.get("platform") or ""))
            span.set_attribute("devices.trigger", "provider_refresh")
            try:
                payload = task["builder"](account)
            except Exception as error:
                elapsed = time.perf_counter() - provider_started_at
                span.set_attribute("devices.provider.success", False)
                span.set_attribute("devices.provider.elapsed_seconds", elapsed)
                span.set_attribute("devices.provider.error", str(error))
                logger.error(
                    f"[Device Sync] {task['label']} snapshot failed for account_id={account.id}: "
                    f"elapsed={elapsed:.2f}s error={error}"
                )
                raise
            elapsed = time.perf_counter() - provider_started_at
            span.set_attribute("devices.provider.success", True)
            span.set_attribute("devices.provider.elapsed_seconds", elapsed)
            span.set_attribute("devices.provider.device_count", len(payload.get("devices", [])))
            logger.info(
                f"[Device Sync] {task['label']} snapshot built for account_id={account.id}: "
                f"devices={len(payload.get('devices', []))} "
                f"elapsed={elapsed:.2f}s"
            )
            return payload

    @classmethod
    def _get_state(cls, account: Account) -> DeviceDashboardState:
        state, _ = DeviceDashboardState.objects.get_or_create(account=account, key=cls.state_key)
        return state

    @classmethod
    def _has_snapshot(cls, account: Account) -> bool:
        return bool(cls._get_state(account).refreshed_at)

    @classmethod
    def _serialize_control(cls, control: DeviceControl) -> dict:
        return {
            "id": control.external_id,
            "parent_id": control.parent_external_id or None,
            "source_type": control.source_type,
            "kind": control.kind,
            "key": control.key,
            "label": control.label,
            "group_label": control.group_label,
            "writable": control.writable,
            "value": control.value,
            "unit": control.unit,
            "options": control.options,
            "range_spec": control.range_spec,
            "action_params": control.action_params,
            "updated_at": control.updated_at.isoformat(),
        }

    @classmethod
    def _serialize_snapshot(
        cls,
        *,
        state: DeviceDashboardState,
        rooms: list[DeviceRoom],
        devices: list[DeviceSnapshot],
        anomalies: list[DeviceAnomaly],
        rules: list[DeviceAutomationRule],
    ) -> dict:
        device_counts = Counter(device.room_id for device in devices if device.room_id)
        anomaly_counts = Counter(anomaly.room_id for anomaly in anomalies if anomaly.room_id)

        return {
            "refreshed_at": state.refreshed_at.isoformat() if state.refreshed_at else None,
            "source": state.source,
            "last_trigger": state.last_trigger,
            "pending_refresh": bool(state.refresh_requested_at),
            "last_error": state.last_error,
            "has_snapshot": bool(state.refreshed_at),
            "rooms": [
                {
                    "id": room.slug,
                    "name": room.name,
                    "climate": room.climate,
                    "summary": room.summary,
                    "device_count": device_counts.get(room.id, 0),
                    "anomaly_count": anomaly_counts.get(room.id, 0),
                }
                for room in rooms
            ],
            "devices": [
                {
                    "id": device.external_id,
                    "room_id": device.room.slug if device.room else None,
                    "room_name": device.room.name if device.room else "",
                    "name": device.name,
                    "category": device.category,
                    "status": device.status,
                    "telemetry": device.telemetry,
                    "note": device.note,
                    "capabilities": device.capabilities,
                    "last_seen": device.last_seen.isoformat() if device.last_seen else None,
                    "controls": [cls._serialize_control(control) for control in device.controls.all()],
                }
                for device in devices
            ],
            "anomalies": [
                {
                    "id": anomaly.external_id,
                    "room_id": anomaly.room.slug if anomaly.room else None,
                    "device_id": anomaly.device.external_id if anomaly.device else None,
                    "severity": anomaly.severity,
                    "title": anomaly.title,
                    "body": anomaly.body,
                    "recommendation": anomaly.recommendation,
                    "updated_at": anomaly.updated_at.isoformat(),
                }
                for anomaly in anomalies
            ],
            "rules": [
                {
                    "id": rule.external_id,
                    "room_id": rule.room.slug if rule.room else None,
                    "device_id": rule.device.external_id if rule.device else None,
                    "mode_key": rule.mode_key,
                    "mode_label": rule.mode_label,
                    "target": rule.target,
                    "condition": rule.condition,
                    "decision": rule.decision,
                    "rationale": rule.rationale,
                    "updated_at": rule.updated_at.isoformat(),
                }
                for rule in rules
            ],
        }

    @classmethod
    def _queue_refresh(cls, state: DeviceDashboardState, *, trigger: str) -> None:
        logger.info(f"[Device Sync] _queue_refresh called: account_id={state.account_id} trigger={trigger}")
        state.requested_trigger = trigger
        if not state.refresh_requested_at:
            state.refresh_requested_at = timezone.now()
        state.last_error = ""
        state.save(update_fields=["requested_trigger", "refresh_requested_at", "last_error", "updated_at"])
        logger.info(
            f"[Device Sync] Refresh queued for account_id={state.account_id}, backend={get_queue_backend()} "
            "and ready for worker pickup"
        )

    @classmethod
    def get_dashboard(cls, account: Account) -> dict:
        state = cls._get_state(account)
        has_snapshot = cls._has_snapshot(account)

        if not has_snapshot and not state.refresh_requested_at:
            if cls.has_active_device_provider_auth(account):
                logger.info(
                    f"[Device Sync] No snapshot for account_id={account.id}; "
                    "running inline bootstrap refresh."
                )
                return cls.refresh(account, trigger="bootstrap")
            cls._queue_refresh(state, trigger="bootstrap")
            state.refresh_from_db()
            return {
                "status": "success",
                "snapshot": cls._serialize_snapshot(
                    state=state,
                    rooms=[],
                    devices=[],
                    anomalies=[],
                    rules=[],
                ),
            }

        rooms = list(DeviceRoom.objects.filter(account=account))
        devices = list(DeviceSnapshot.objects.filter(account=account).select_related("room").prefetch_related("controls"))
        anomalies = list(DeviceAnomaly.objects.filter(account=account, is_active=True).select_related("room", "device"))
        rules = list(DeviceAutomationRule.objects.filter(account=account, is_active=True).select_related("room", "device"))

        return {
            "status": "success",
            "snapshot": cls._serialize_snapshot(
                state=state,
                rooms=rooms,
                devices=devices,
                anomalies=anomalies,
                rules=rules,
            ),
        }

    @classmethod
    def clear_all_data(cls, account: Account) -> None:
        with transaction.atomic():
            DeviceAnomaly.objects.filter(account=account).delete()
            DeviceAutomationRule.objects.filter(account=account).delete()
            DeviceControl.objects.filter(account=account).delete()
            DeviceSnapshot.objects.filter(account=account).delete()
            DeviceRoom.objects.filter(account=account).delete()

            state = cls._get_state(account)
            state.source = "none"
            state.refreshed_at = None
            state.last_trigger = "clear"
            state.refresh_requested_at = None
            state.last_error = ""
            state.save(update_fields=["source", "refreshed_at", "last_trigger", "refresh_requested_at", "last_error", "updated_at"])

            logger.info(f"[Device Data] 已清理账户 {account.email} 下的所有设备平台业务数据。")

    @classmethod
    def refresh(cls, account: Account, *, trigger: str = "manual") -> dict:
        with cls.tracer.start_as_current_span("devices.refresh") as span:
            span.set_attribute("devices.account_id", account.id)
            span.set_attribute("devices.trigger", trigger)
            span.set_attribute("account.email", account.email)
            logger.info(f"[Device Sync] refresh() started for account_id={account.id} email={account.email} trigger={trigger}")
            refresh_started_at = time.perf_counter()
            provider_payloads: list[dict] = []
            enabled_tasks: list[dict[str, Any]] = []

            for task in cls._provider_refresh_tasks():
                try:
                    auth_record = task["auth_service"].get_auth_record(account=account, active_only=True)
                    logger.debug(
                        f"[Device Sync] {task['label']} auth check for account_id={account.id}: "
                        f"found={auth_record is not None}"
                    )
                    if auth_record:
                        enabled_tasks.append(task)
                except Exception as error:
                    logger.error(
                        f"[Device Sync] Failed to check {task['label']} auth state for user {account.email}: {error}"
                    )

            span.set_attribute("devices.provider_enabled_count", len(enabled_tasks))
            span.set_attribute("devices.providers", ",".join(task["platform"] for task in enabled_tasks))
            logger.info(
                f"[Device Sync] Enabled providers for account_id={account.id}: "
                f"{', '.join(task['label'] for task in enabled_tasks) or 'none'}"
            )

            if enabled_tasks:
                max_workers = min(len(enabled_tasks), 4)
                logger.info(
                    f"[Device Sync] Running {len(enabled_tasks)} provider refresh task(s) in parallel "
                    f"for account_id={account.id} with max_workers={max_workers}"
                )
                with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="device-sync") as executor:
                    future_to_task = {}
                    for task in enabled_tasks:
                        logger.info(f"[Device Sync] Building {task['label']} snapshot for account_id={account.id}")
                        future_to_task[executor.submit(cls._run_provider_refresh_task, account, task)] = task

                    for future in as_completed(future_to_task):
                        task = future_to_task[future]
                        try:
                            provider_payloads.append(future.result())
                        except Exception as error:
                            logger.error(
                                f"[Device Sync] Failed to build {task['label']} snapshot for user {account.email}: {error}"
                            )

            logger.info(f"[Device Sync] Merging {len(provider_payloads)} provider payloads for account_id={account.id}")
            payload = cls._merge_snapshots(provider_payloads) if provider_payloads else cls._build_empty_snapshot()
            span.set_attribute("devices.room_count", len(payload["rooms"]))
            span.set_attribute("devices.device_count", len(payload["devices"]))
            logger.info(
                f"[Device Sync] Final payload for account_id={account.id}: "
                f"rooms={len(payload['rooms'])} devices={len(payload['devices'])}"
            )

            persistence_started_at = time.perf_counter()
            with transaction.atomic():
                state = cls._get_state(account)
                existing_room_sort_orders = {
                    room.slug: room.sort_order
                    for room in DeviceRoom.objects.filter(account=account).only("slug", "sort_order")
                }
                existing_device_sort_orders = {
                    device.external_id: device.sort_order
                    for device in DeviceSnapshot.objects.filter(account=account).only("external_id", "sort_order")
                }
                existing_device_controls: dict[str, list[dict]] = defaultdict(list)
                for control in (
                    DeviceControl.objects.filter(account=account)
                    .select_related("device")
                    .order_by("sort_order", "id")
                ):
                    if control.device_id and control.device:
                        existing_device_controls[control.device.external_id].append(cls._serialize_existing_control(control))

                DeviceAnomaly.objects.filter(account=account).delete()
                DeviceAutomationRule.objects.filter(account=account).delete()
                DeviceControl.objects.filter(account=account).delete()
                DeviceSnapshot.objects.filter(account=account).delete()
                DeviceRoom.objects.filter(account=account).delete()

                room_map: dict[str, DeviceRoom] = {}
                for room_data in payload["rooms"]:
                    room = DeviceRoom.objects.create(
                        account=account,
                        slug=room_data["id"],
                        name=room_data["name"],
                        climate=room_data["climate"],
                        summary=room_data["summary"],
                        sort_order=existing_room_sort_orders.get(room_data["id"], room_data["sort_order"]),
                    )
                    room_map[room.slug] = room

                device_map: dict[str, DeviceSnapshot] = {}
                for device_data in payload["devices"]:
                    cls._apply_mijia_control_fallback(
                        device_data,
                        stale_controls=existing_device_controls.get(device_data["id"], []),
                    )
                    device = DeviceSnapshot.objects.create(
                        account=account,
                        external_id=device_data["id"],
                        room=room_map.get(device_data["room_id"]),
                        name=device_data["name"],
                        category=device_data["category"],
                        status=device_data["status"],
                        telemetry=device_data["telemetry"],
                        note=device_data["note"],
                        capabilities=device_data["capabilities"],
                        last_seen=device_data["last_seen"],
                        sort_order=existing_device_sort_orders.get(device_data["id"], device_data["sort_order"]),
                        source_payload=device_data.get("source_payload", {}),
                    )
                    device_map[device.external_id] = device

                    for control_data in device_data.get("controls", []):
                        DeviceControl.objects.create(
                            account=account,
                            device=device,
                            external_id=control_data["id"],
                            parent_external_id=control_data.get("parent_id", "") or "",
                            source_type=control_data["source_type"],
                            kind=control_data["kind"],
                            key=control_data["key"],
                            label=control_data["label"],
                            group_label=control_data.get("group_label", ""),
                            writable=control_data.get("writable", False),
                            value=control_data.get("value") if control_data.get("value") is not None else {},
                            unit=control_data.get("unit", ""),
                            options=control_data.get("options", []),
                            range_spec=control_data.get("range_spec", {}),
                            action_params=control_data.get("action_params", {}),
                            source_payload=control_data.get("source_payload", {}),
                            sort_order=control_data.get("sort_order", 0),
                        )

                for anomaly_data in payload["anomalies"]:
                    DeviceAnomaly.objects.create(
                        account=account,
                        external_id=anomaly_data["id"],
                        room=room_map.get(anomaly_data["room_id"]),
                        device=device_map.get(anomaly_data.get("device_id")),
                        severity=anomaly_data["severity"],
                        title=anomaly_data["title"],
                        body=anomaly_data["body"],
                        recommendation=anomaly_data["recommendation"],
                        sort_order=anomaly_data["sort_order"],
                    )

                for rule_data in payload["rules"]:
                    DeviceAutomationRule.objects.create(
                        account=account,
                        external_id=rule_data["id"],
                        room=room_map.get(rule_data["room_id"]),
                        device=device_map.get(rule_data.get("device_id")),
                        mode_key=rule_data["mode_key"],
                        mode_label=rule_data["mode_label"],
                        target=rule_data["target"],
                        condition=rule_data["condition"],
                        decision=rule_data["decision"],
                        rationale=rule_data["rationale"],
                        sort_order=rule_data["sort_order"],
                    )

                state.source = payload["source"]
                state.last_trigger = trigger
                state.requested_trigger = ""
                state.refresh_requested_at = None
                state.last_error = ""
                state.refreshed_at = timezone.now()
                state.save()

            persistence_elapsed = time.perf_counter() - persistence_started_at
            total_elapsed = time.perf_counter() - refresh_started_at
            span.set_attribute("devices.persistence_elapsed_seconds", persistence_elapsed)
            span.set_attribute("devices.total_elapsed_seconds", total_elapsed)
            logger.info(
                f"[Device Sync] Refresh persisted for account_id={account.id}: "
                f"elapsed={persistence_elapsed:.2f}s total={total_elapsed:.2f}s"
            )
            logger.info(
                f"[Device Sync] refresh() completed for account_id={account.id}: "
                f"providers={len(provider_payloads)} rooms={len(payload['rooms'])} devices={len(payload['devices'])} total={total_elapsed:.2f}s"
            )
            return cls.get_dashboard(account)

    @classmethod
    def reorder_devices(cls, account: Account, *, ordered_device_ids: list[str]) -> dict:
        normalized_ids = []
        seen_ids = set()
        for device_id in ordered_device_ids:
            normalized_id = str(device_id or "").strip()
            if not normalized_id or normalized_id in seen_ids:
                continue
            normalized_ids.append(normalized_id)
            seen_ids.add(normalized_id)

        if len(normalized_ids) < 2:
            raise ValueError("At least two devices are required to reorder.")

        devices = list(
            DeviceSnapshot.objects.filter(account=account)
            .select_related("room")
            .prefetch_related("controls")
            .order_by("sort_order", "id")
        )
        device_map = {device.external_id: device for device in devices}

        missing_ids = [device_id for device_id in normalized_ids if device_id not in device_map]
        if missing_ids:
            raise ValueError("Some devices were not found.")

        current_subset = [device.external_id for device in devices if device.external_id in seen_ids]
        if len(current_subset) != len(normalized_ids):
            raise ValueError("Some devices were not found.")

        replacement_iter = iter(normalized_ids)
        reordered_ids = [
            next(replacement_iter) if device.external_id in seen_ids else device.external_id
            for device in devices
        ]

        with transaction.atomic():
            for index, device_id in enumerate(reordered_ids, start=1):
                device = device_map[device_id]
                next_sort_order = index * 10
                if device.sort_order == next_sort_order:
                    continue
                DeviceSnapshot.objects.filter(pk=device.pk).update(sort_order=next_sort_order)
                device.sort_order = next_sort_order

        return cls.get_dashboard(account)

    @classmethod
    def request_refresh(cls, account: Account, *, trigger: str = "manual") -> dict:
        logger.info(f"[Device Sync] request_refresh called: account_id={account.id} email={account.email} trigger={trigger}")
        provider_connect_trigger = trigger.startswith("connect_")
        interactive_trigger = trigger == "api" or trigger == "bootstrap"
        if cls.has_active_device_provider_auth(account) and not provider_connect_trigger and (
            interactive_trigger or not redis_queue_enabled()
        ):
            logger.info(
                f"[Device Sync] Inline refresh selected for account_id={account.id}; "
                f"trigger={trigger} backend={get_queue_backend()}"
            )
            return cls.refresh(account, trigger=trigger)

        state = cls._get_state(account)
        cls._queue_refresh(state, trigger=trigger)
        if redis_queue_enabled():
            try:
                enqueue_account_refresh(account.id)
                logger.info(
                    f"[Device Sync] Queued account_id={account.id} to Redis sync queue. "
                    f"backend={get_queue_backend()}"
                )
            except Exception as error:
                logger.error(
                    f"[Device Sync] Failed to enqueue account_id={account.id} to Redis queue: {error}. "
                    "Falling back to DB pending state."
                )
            return cls.get_dashboard(account)
        return cls.get_dashboard(account)

    @classmethod
    def execute_control(
        cls,
        account: Account,
        *,
        device_external_id: str,
        control_external_id: str,
        action: str = "",
        value: Any = None,
    ) -> dict:
        device = DeviceSnapshot.objects.filter(account=account, external_id=device_external_id).first()
        if device is None:
            raise ValueError("Device not found")

        control = DeviceControl.objects.filter(account=account, device=device, external_id=control_external_id).first()
        if control is None:
            raise ValueError("Control not found")
        if not control.writable:
            raise ValueError("Control is read only")

        if control.source_type == DeviceControl.SourceTypeChoices.HA_ENTITY:
            cls._execute_home_assistant_control(account, control=control, action=action, value=value)
        elif control.source_type in {
            DeviceControl.SourceTypeChoices.MIJIA_PROPERTY,
            DeviceControl.SourceTypeChoices.MIJIA_ACTION,
        }:
            cls._execute_mijia_control(account, device=device, control=control, value=value)
        elif control.source_type in {
            DeviceControl.SourceTypeChoices.MIDEA_CLOUD_PROPERTY,
            DeviceControl.SourceTypeChoices.MIDEA_CLOUD_ACTION,
        }:
            cls._execute_midea_cloud_control(account, device=device, control=control, action=action, value=value)
        elif control.source_type in {
            DeviceControl.SourceTypeChoices.MBAPI2020_PROPERTY,
            DeviceControl.SourceTypeChoices.MBAPI2020_ACTION,
        }:
            cls._execute_mbapi2020_control(account, device=device, control=control, action=action, value=value)
        elif control.source_type in {
            DeviceControl.SourceTypeChoices.HISENSE_HA_PROPERTY,
            DeviceControl.SourceTypeChoices.HISENSE_HA_ACTION,
        }:
            cls._execute_hisense_ha_control(account, device=device, control=control, action=action, value=value)
        else:
            raise ValueError(f"Unsupported control source: {control.source_type}")

        cls._apply_optimistic_control_result(control, action=action, value=value)
        try:
            return cls._refresh_device_after_control(
                account,
                device=device,
                control=control,
                trigger="control",
            )
        except Exception as error:
            logger.warning(
                f"[Device Sync] Single-device refresh failed for account_id={account.id} "
                f"device_id={device.external_id}: {error}. Falling back to queued full refresh."
            )
        return cls.request_refresh(account, trigger="control")

    @classmethod
    def refresh_device(
        cls,
        account: Account,
        *,
        device_external_id: str,
        trigger: str = "query",
    ) -> dict:
        device = DeviceSnapshot.objects.filter(account=account, external_id=device_external_id).first()
        if device is None:
            raise ValueError("Device not found")
        control = (
            DeviceControl.objects.filter(account=account, device=device)
            .order_by("sort_order", "id")
            .first()
        )
        if control is None:
            raise ValueError("Control not found")
        return cls._refresh_device_after_control(
            account,
            device=device,
            control=control,
            trigger=trigger,
        )

    @classmethod
    def has_active_device_provider_auth(cls, account: Account) -> bool:
        return PlatformAuth.objects.filter(
            account=account,
            is_active=True,
            platform_name__in=cls.device_provider_names,
        ).exists()

    @classmethod
    def sync_after_provider_change(cls, account: Account, *, trigger: str) -> None:
        if cls.has_active_device_provider_auth(account):
            logger.info(f"[Device Sync] 平台授权有变（触发源: {trigger}），正在申请后台全量同步...")
            cls.request_refresh(account, trigger=trigger)
            return

        logger.info(f"[Device Sync] 所有设备提供商已失效（触发源: {trigger}），正在清理本地业务数据快照...")
        cls.clear_all_data(account)

    @classmethod
    def run_pending_refresh(cls, account: Account, *, sync_interval_seconds: int | None = None) -> bool:
        state = cls._get_state(account)
        interval_seconds = sync_interval_seconds or cls.default_sync_interval_seconds
        now = timezone.now()
        has_snapshot = cls._has_snapshot(account)
        is_stale = (
            not has_snapshot
            or not state.refreshed_at
            or (now - state.refreshed_at).total_seconds() >= interval_seconds
        )

        logger.debug(
            f"[Device Sync] run_pending_refresh check: account_id={account.id} email={account.email} "
            f"has_snapshot={has_snapshot} refresh_requested_at={state.refresh_requested_at} "
            f"is_stale={is_stale} refreshed_at={state.refreshed_at}"
        )

        if not state.refresh_requested_at and not is_stale:
            logger.debug(f"[Device Sync] Skip refresh for account_id={account.id}: no request and not stale")
            return False

        trigger = state.requested_trigger or ("worker_bootstrap" if not has_snapshot else "worker")
        logger.info(f"[Device Sync] Starting refresh for account_id={account.id} email={account.email} trigger={trigger}")
        try:
            cls.refresh(account, trigger=trigger)
            logger.info(f"[Device Sync] Refresh completed for account_id={account.id}")
            return True
        except Exception as error:
            logger.error(f"[Device Sync] Refresh failed for account_id={account.id}: {error}")
            state = cls._get_state(account)
            if not state.refresh_requested_at:
                state.refresh_requested_at = now
            if not state.requested_trigger:
                state.requested_trigger = trigger
            state.last_error = str(error)
            state.save(update_fields=["requested_trigger", "refresh_requested_at", "last_error", "updated_at"])
            raise

    @classmethod
    def _build_mijia_snapshot(cls, account: Account) -> dict:
        from mijiaAPI import get_device_info, mijiaDevice
        from providers.services import MijiaAuthService

        with cls.tracer.start_as_current_span("devices.mijia_snapshot") as span:
            started_at = time.perf_counter()
            span.set_attribute("devices.account_id", account.id)
            logger.info(f"[Device Sync] Mijia snapshot start for account_id={account.id}")
            try:
                logger.info(f"[Device Sync] Mijia auth start for account_id={account.id}")
                api = MijiaAuthService.get_authenticated_api(account=account)
                logger.info(f"[Device Sync] Mijia auth ready for account_id={account.id}")
                devices_list_started_at = time.perf_counter()
                devices = api.get_devices_list()
                logger.info(
                    f"[Device Sync] Mijia devices list fetched for account_id={account.id}: "
                    f"count={len(devices)} elapsed={time.perf_counter() - devices_list_started_at:.2f}s"
                )
                homes_list_started_at = time.perf_counter()
                homes = api.get_homes_list()
                logger.info(
                    f"[Device Sync] Mijia homes list fetched for account_id={account.id}: "
                    f"count={len(homes)} elapsed={time.perf_counter() - homes_list_started_at:.2f}s"
                )
            except Exception as error:
                span.set_attribute("devices.mijia.success", False)
                span.set_attribute("devices.mijia.error", str(error))
                logger.error(f"[Device Sync] Failed to fetch real MiJia data, falling back to empty: {error}")
                return cls._build_empty_snapshot()

            home_map = {str(h.get("id")): h.get("name") or "默认家庭" for h in homes}
            room_index: dict[str, dict] = {}
            devices_data: list[dict] = []
            spec_failed_count = 0
            fallback_reused_count = 0

            for index, dev in enumerate(devices, start=1):
                did = str(dev.get("did", "")).strip()
                if not did:
                    continue

                device_started_at = time.perf_counter()
                home_id = str(dev.get("home_id") or "default")
                home_name = home_map.get(home_id) or "默认家庭"
                room_name = dev.get("room_name") or home_name
                room_key = f"{home_name}:{room_name}"
                room_id = cls._make_room_id("mijia", room_key)
                room_index.setdefault(
                    room_id,
                    {
                        "id": room_id,
                        "name": room_name,
                        "climate": home_name,
                        "summary": f"来自米家家庭: {home_name}",
                        "sort_order": 10 + len(room_index) * 10,
                    },
                )

                model = str(dev.get("model", "")).strip()
                controls = []
                control_capabilities = []
                device_client = None
                spec_failed = False

                logger.info(
                    f"[Device Sync] Mijia device processing account_id={account.id}: "
                    f"did={did} model={model or 'unknown'} room={room_name}"
                )

                try:
                    spec = cls._load_mijia_spec(model, get_device_info=get_device_info)
                except Exception as error:
                    logger.warning(f"[Device Sync] Failed to load MiJia spec for {model}: {error}")
                    spec = {}
                    spec_failed = True
                    spec_failed_count += 1

                if spec:
                    try:
                        device_client = mijiaDevice(api, did=did)
                    except Exception as error:
                        logger.warning(f"[Device Sync] Failed to create MiJia device client for {did}: {error}")

                for control in cls._build_mijia_controls(dev=dev, spec=spec, device_client=device_client):
                    controls.append(control)
                    if control["kind"] != DeviceControl.KindChoices.SENSOR and control["key"] not in control_capabilities:
                        control_capabilities.append(control["key"])

                if spec_failed and not controls:
                    controls = cls._load_existing_device_controls(account, device_external_id=f"mijia:{did}")
                    if controls:
                        fallback_reused_count += 1
                        logger.info(
                            f"[Device Sync] Mijia fallback reused existing controls for did={did}: "
                            f"count={len(controls)}"
                        )
                    control_capabilities = [control["key"] for control in controls if control["kind"] != DeviceControl.KindChoices.SENSOR][:8]

                is_online = bool(dev.get("isOnline", False))
                devices_data.append(
                    {
                        "id": f"mijia:{did}",
                        "room_id": room_id,
                        "name": cls._infer_mijia_device_name(dev=dev, did=did, model=model),
                        "category": cls._map_model_to_category(model),
                        "status": "online" if is_online else "offline",
                        "telemetry": cls._summarize_mijia_telemetry(controls, is_online=is_online),
                        "note": f"DID: {did} | 模型: {model or 'unknown'}",
                        "capabilities": control_capabilities[:8],
                        "controls": controls,
                        "last_seen": timezone.now(),
                        "sort_order": index * 10,
                        "source_payload": dev,
                    }
                )
                logger.info(
                    f"[Device Sync] Mijia device processed account_id={account.id}: "
                    f"did={did} controls={len(controls)} elapsed={time.perf_counter() - device_started_at:.2f}s"
                )

            total_elapsed = time.perf_counter() - started_at
            span.set_attribute("devices.mijia.success", True)
            span.set_attribute("devices.mijia.device_count", len(devices_data))
            span.set_attribute("devices.mijia.spec_failed_count", spec_failed_count)
            span.set_attribute("devices.mijia.fallback_reused_count", fallback_reused_count)
            span.set_attribute("devices.mijia.elapsed_seconds", total_elapsed)
            logger.info(
                f"[Device Sync] Mijia snapshot completed for account_id={account.id}: "
                f"devices={len(devices_data)} spec_failed={spec_failed_count} "
                f"fallback_reused={fallback_reused_count} elapsed={total_elapsed:.2f}s"
            )

            return {
                "source": "mijia",
                "rooms": list(room_index.values()),
                "devices": devices_data,
                "anomalies": [],
                "rules": [],
            }

    @classmethod
    def _build_midea_cloud_snapshot(cls, account: Account) -> dict:
        from providers.services import MideaCloudAuthService

        logger.debug(f"[Device Sync] _build_midea_cloud_snapshot start for account_id={account.id}")
        try:
            client = MideaCloudAuthService.get_client(account=account)
            devices = client.list_devices()
            logger.info(f"[Device Sync] Midea devices fetched for account_id={account.id}: count={len(devices)}")
        except Exception as error:
            logger.error(f"[Device Sync] Failed to fetch Midea data, falling back to empty: {error}")
            return cls._build_empty_snapshot()

        room_index: dict[str, dict] = {}
        devices_data: list[dict] = []
        default_room_id = cls._make_room_id("midea_cloud", "default")

        for index, raw_device in enumerate(devices, start=1):
            if not isinstance(raw_device, dict):
                continue
            room_data, device_data = cls._build_midea_cloud_device_snapshot(raw_device, sort_order=index * 10)
            room_id = room_data["id"] or default_room_id
            room_index.setdefault(room_id, {**room_data, "id": room_id})
            devices_data.append(device_data)

        return {
            "source": "midea_cloud",
            "rooms": list(room_index.values()),
            "devices": devices_data,
            "anomalies": [],
            "rules": [],
        }

    @classmethod
    def _build_midea_cloud_device_snapshot(cls, raw_device: dict, *, sort_order: int) -> tuple[dict, dict]:
        device_id = str(
            raw_device.get("id")
            or raw_device.get("device_id")
            or raw_device.get("sn")
            or raw_device.get("appliance_code")
            or ""
        ).strip()
        room_name = str(raw_device.get("room_name") or raw_device.get("home_name") or "美的设备").strip()
        room_id = cls._make_room_id("midea_cloud", room_name) if room_name else cls._make_room_id("midea_cloud", "default")
        room_data = {
            "id": room_id,
            "name": room_name or "美的设备",
            "climate": str(raw_device.get("home_name") or "Midea").strip(),
            "summary": "来自美的直连接入",
            "sort_order": 10,
        }

        controls = cls._build_midea_cloud_controls(raw_device)
        capabilities = [control["key"] for control in controls if control["kind"] != DeviceControl.KindChoices.SENSOR][:8]
        category = str(raw_device.get("category") or raw_device.get("device_type") or "美的设备").strip()
        device_type_value = raw_device.get("device_type")
        if isinstance(device_type_value, str) and device_type_value.startswith("0x"):
            try:
                device_type_value = int(device_type_value, 16)
            except ValueError:
                device_type_value = None
        if isinstance(device_type_value, int):
            mapping = get_device_mapping(
                device_type_value,
                sn8=str(raw_device.get("sn8") or ""),
                category=str(raw_device.get("category") or ""),
            )
            category = str(mapping.get("category") or category)

        device_data = {
            "id": f"midea_cloud:{device_id}",
            "room_id": room_id,
            "name": str(raw_device.get("name") or raw_device.get("device_name") or f"美的设备 {device_id[-4:]}").strip(),
            "category": category,
            "status": cls._map_midea_cloud_status(raw_device),
            "telemetry": cls._summarize_midea_cloud_device(raw_device, controls),
            "note": f"Midea Device: {device_id}",
            "capabilities": capabilities,
            "controls": controls,
            "last_seen": timezone.now(),
            "sort_order": sort_order,
            "source_payload": raw_device,
        }
        return room_data, device_data

    @classmethod
    def _refresh_midea_cloud_device(cls, account: Account, *, device_external_id: str, trigger: str) -> dict:
        from providers.services import MideaCloudAuthService

        device = DeviceSnapshot.objects.filter(account=account, external_id=device_external_id).first()
        if device is None:
            raise ValueError("Device not found")

        client = MideaCloudAuthService.get_client(account=account)
        raw_device = client.get_device(device.external_id.removeprefix("midea_cloud:"))
        if not isinstance(raw_device, dict):
            raise ValueError("Midea device refresh returned empty payload")

        room_data, device_data = cls._build_midea_cloud_device_snapshot(raw_device, sort_order=device.sort_order or 10)
        with transaction.atomic():
            room, _ = DeviceRoom.objects.update_or_create(
                account=account,
                slug=room_data["id"],
                defaults={
                    "name": room_data["name"],
                    "climate": room_data["climate"],
                    "summary": room_data["summary"],
                    "sort_order": room_data["sort_order"],
                },
            )

            device.room = room
            device.name = device_data["name"]
            device.category = device_data["category"]
            device.status = device_data["status"]
            device.telemetry = device_data["telemetry"]
            device.note = device_data["note"]
            device.capabilities = device_data["capabilities"]
            device.last_seen = device_data["last_seen"]
            device.sort_order = device_data["sort_order"]
            device.source_payload = device_data["source_payload"]
            device.save()

            DeviceControl.objects.filter(account=account, device=device).delete()
            for control_data in device_data.get("controls", []):
                DeviceControl.objects.create(
                    account=account,
                    device=device,
                    external_id=control_data["id"],
                    parent_external_id=control_data.get("parent_id", "") or "",
                    source_type=control_data["source_type"],
                    kind=control_data["kind"],
                    key=control_data["key"],
                    label=control_data["label"],
                    group_label=control_data.get("group_label", ""),
                    writable=control_data.get("writable", False),
                    value=control_data.get("value") if control_data.get("value") is not None else {},
                    unit=control_data.get("unit", ""),
                    options=control_data.get("options", []),
                    range_spec=control_data.get("range_spec", {}),
                    action_params=control_data.get("action_params", {}),
                    source_payload=control_data.get("source_payload", {}),
                    sort_order=control_data.get("sort_order", 0),
                )

            state = cls._get_state(account)
            state.last_trigger = trigger
            state.requested_trigger = ""
            state.refresh_requested_at = None
            state.last_error = ""
            state.refreshed_at = timezone.now()
            state.save(update_fields=["last_trigger", "requested_trigger", "refresh_requested_at", "last_error", "refreshed_at", "updated_at"])

        return cls.get_dashboard(account)

    @classmethod
    def _build_mbapi2020_snapshot(cls, account: Account) -> dict:
        from providers.services import MbApi2020AuthService

        logger.debug(f"[Device Sync] _build_mbapi2020_snapshot start for account_id={account.id}")
        try:
            client = MbApi2020AuthService.get_client(account=account)
            vehicles = client.list_devices()
            logger.info(f"[Device Sync] MbApi2020 vehicles fetched for account_id={account.id}: count={len(vehicles)}")
        except Exception as error:
            logger.error(f"[Device Sync] Failed to fetch MbApi2020 data, falling back to empty: {error}")
            return cls._build_empty_snapshot()

        room_index: dict[str, dict] = {}
        devices_data: list[dict] = []
        for index, raw_vehicle in enumerate(vehicles, start=1):
            if not isinstance(raw_vehicle, dict):
                continue
            room_data, device_data = cls._build_mbapi2020_vehicle_snapshot(raw_vehicle, sort_order=index * 10)
            room_index.setdefault(room_data["id"], room_data)
            devices_data.append(device_data)

        return {
            "source": "mbapi2020",
            "rooms": list(room_index.values()),
            "devices": devices_data,
            "anomalies": [],
            "rules": [],
        }

    @classmethod
    def _build_mbapi2020_vehicle_snapshot(cls, raw_vehicle: dict, *, sort_order: int) -> tuple[dict, dict]:
        vin = str(raw_vehicle.get("vin") or raw_vehicle.get("id") or "").strip()
        region = str(raw_vehicle.get("region") or raw_vehicle.get("raw", {}).get("region") or "China").strip()
        room_id = cls._make_room_id("mbapi2020", region or "default")
        room_data = {
            "id": room_id,
            "name": region or "奔驰",
            "climate": str(raw_vehicle.get("license_plate") or "").strip(),
            "summary": "来自奔驰 mbapi2020 直连接入",
            "sort_order": 10,
        }
        controls = cls._build_mbapi2020_controls(raw_vehicle)
        capabilities = [control["key"] for control in controls if control["kind"] != DeviceControl.KindChoices.SENSOR][:8]
        display_name = cls._resolve_mbapi2020_vehicle_name(raw_vehicle)
        device_data = {
            "id": f"mbapi2020:{vin}",
            "room_id": room_id,
            "name": display_name,
            "category": "vehicle",
            "status": cls._map_mbapi2020_status(raw_vehicle),
            "telemetry": cls._summarize_mbapi2020_vehicle(raw_vehicle, controls),
            "note": f"VIN: {vin}" if vin else "Mercedes-Benz Vehicle",
            "capabilities": capabilities,
            "controls": controls,
            "last_seen": timezone.now(),
            "sort_order": sort_order,
            "source_payload": raw_vehicle,
        }
        return room_data, device_data

    @classmethod
    def _resolve_mbapi2020_vehicle_name(cls, raw_vehicle: dict) -> str:
        vin = str(raw_vehicle.get("vin") or raw_vehicle.get("id") or "").strip()
        sales_related_information = raw_vehicle.get("raw", {}).get("salesRelatedInformation") or raw_vehicle.get("salesRelatedInformation") or {}
        baumuster = sales_related_information.get("baumuster") if isinstance(sales_related_information, dict) else {}
        baumuster_description = ""
        if isinstance(baumuster, dict):
            baumuster_description = str(baumuster.get("baumusterDescription") or "").strip()

        candidates = [
            baumuster_description,
            str(raw_vehicle.get("model") or "").strip(),
            str(raw_vehicle.get("name") or "").strip(),
            str(raw_vehicle.get("license_plate") or raw_vehicle.get("raw", {}).get("licensePlate") or "").strip(),
        ]
        for candidate in candidates:
            if cls._is_meaningful_mbapi2020_name(candidate):
                return candidate
        return f"奔驰 {vin[-6:]}" if vin else "奔驰车辆"

    @staticmethod
    def _is_meaningful_mbapi2020_name(value: str) -> bool:
        normalized = str(value or "").strip()
        if not normalized:
            return False
        if re.fullmatch(r"[0-9]+", normalized):
            return False
        if len(normalized) <= 3 and re.fullmatch(r"[A-Za-z0-9_-]+", normalized):
            return False
        return True

    @classmethod
    def _refresh_mbapi2020_vehicle(cls, account: Account, *, device_external_id: str, trigger: str) -> dict:
        from providers.services import MbApi2020AuthService

        device = DeviceSnapshot.objects.filter(account=account, external_id=device_external_id).first()
        if device is None:
            raise ValueError("Device not found")

        client = MbApi2020AuthService.get_client(account=account)
        raw_vehicle = client.get_device(device.external_id.removeprefix("mbapi2020:"))
        if not isinstance(raw_vehicle, dict):
            raise ValueError("Mercedes vehicle refresh returned empty payload")

        room_data, device_data = cls._build_mbapi2020_vehicle_snapshot(raw_vehicle, sort_order=device.sort_order or 10)
        return cls._persist_single_device_refresh(account, device=device, room_data=room_data, device_data=device_data, trigger=trigger)

    @classmethod
    def _build_hisense_ha_snapshot(cls, account: Account) -> dict:
        from providers.services import HisenseHAAuthService

        logger.debug(f"[Device Sync] _build_hisense_ha_snapshot start for account_id={account.id}")
        try:
            client = HisenseHAAuthService.get_client(account=account)
            devices = client.list_devices()
            logger.info(f"[Device Sync] Hisense devices fetched for account_id={account.id}: count={len(devices)}")
        except Exception as error:
            logger.error(f"[Device Sync] Failed to fetch Hisense data, falling back to empty: {error}")
            return cls._build_empty_snapshot()

        room_index: dict[str, dict] = {}
        devices_data: list[dict] = []
        for index, raw_device in enumerate(devices, start=1):
            if not isinstance(raw_device, dict):
                continue
            room_data, device_data = cls._build_hisense_ha_device_snapshot(raw_device, sort_order=index * 10)
            room_index.setdefault(room_data["id"], room_data)
            devices_data.append(device_data)

        return {
            "source": "hisense_ha",
            "rooms": list(room_index.values()),
            "devices": devices_data,
            "anomalies": [],
            "rules": [],
        }

    @classmethod
    def _build_hisense_ha_device_snapshot(cls, raw_device: dict, *, sort_order: int) -> tuple[dict, dict]:
        device_id = str(raw_device.get("device_id") or raw_device.get("id") or "").strip()
        room_name = str(raw_device.get("room_name") or raw_device.get("home_name") or "海信空调").strip()
        room_id = cls._make_room_id("hisense_ha", room_name or "default")
        room_data = {
            "id": room_id,
            "name": room_name or "海信空调",
            "climate": str(raw_device.get("home_name") or "").strip(),
            "summary": "来自海信云接入",
            "sort_order": 10,
        }
        controls = cls._build_hisense_ha_controls(raw_device)
        capabilities = [control["key"] for control in controls if control["kind"] != DeviceControl.KindChoices.SENSOR][:8]
        status_payload = raw_device.get("status_payload") if isinstance(raw_device.get("status_payload"), dict) else {}
        device_data = {
            "id": f"hisense_ha:{device_id}",
            "room_id": room_id,
            "name": str(raw_device.get("name") or raw_device.get("device_name") or f"海信空调 {device_id[-4:]}").strip(),
            "category": "climate",
            "status": cls._map_hisense_ha_status(status_payload),
            "telemetry": cls._summarize_hisense_ha_device(status_payload, controls),
            "note": f"Hisense Device: {device_id}",
            "capabilities": capabilities,
            "controls": controls,
            "last_seen": timezone.now(),
            "sort_order": sort_order,
            "source_payload": raw_device,
        }
        return room_data, device_data

    @classmethod
    def _refresh_hisense_ha_device(cls, account: Account, *, device_external_id: str, trigger: str) -> dict:
        from providers.services import HisenseHAAuthService

        device = DeviceSnapshot.objects.filter(account=account, external_id=device_external_id).first()
        if device is None:
            raise ValueError("Device not found")

        client = HisenseHAAuthService.get_client(account=account)
        raw_device = client.get_device(device.external_id.removeprefix("hisense_ha:"))
        if not isinstance(raw_device, dict):
            raise ValueError("Hisense device refresh returned empty payload")

        room_data, device_data = cls._build_hisense_ha_device_snapshot(raw_device, sort_order=device.sort_order or 10)
        return cls._persist_single_device_refresh(account, device=device, room_data=room_data, device_data=device_data, trigger=trigger)

    @classmethod
    def _refresh_device_after_control(
        cls,
        account: Account,
        *,
        device: DeviceSnapshot,
        control: DeviceControl,
        trigger: str,
    ) -> dict:
        if control.source_type == DeviceControl.SourceTypeChoices.HA_ENTITY:
            return cls._refresh_home_assistant_device(account, device=device, trigger=trigger)
        if control.source_type in {
            DeviceControl.SourceTypeChoices.MIJIA_PROPERTY,
            DeviceControl.SourceTypeChoices.MIJIA_ACTION,
        }:
            return cls._refresh_mijia_device(account, device=device, trigger=trigger)
        if control.source_type in {
            DeviceControl.SourceTypeChoices.MIDEA_CLOUD_PROPERTY,
            DeviceControl.SourceTypeChoices.MIDEA_CLOUD_ACTION,
        }:
            return cls._refresh_midea_cloud_device(account, device_external_id=device.external_id, trigger=trigger)
        if control.source_type in {
            DeviceControl.SourceTypeChoices.MBAPI2020_PROPERTY,
            DeviceControl.SourceTypeChoices.MBAPI2020_ACTION,
        }:
            return cls._refresh_mbapi2020_vehicle(account, device_external_id=device.external_id, trigger=trigger)
        if control.source_type in {
            DeviceControl.SourceTypeChoices.HISENSE_HA_PROPERTY,
            DeviceControl.SourceTypeChoices.HISENSE_HA_ACTION,
        }:
            return cls._refresh_hisense_ha_device(account, device_external_id=device.external_id, trigger=trigger)
        return cls.request_refresh(account, trigger=trigger)

    @classmethod
    def _refresh_home_assistant_device(cls, account: Account, *, device: DeviceSnapshot, trigger: str) -> dict:
        from providers.services import HomeAssistantAuthService

        raw_payload = device.source_payload or {}
        entity_ids = [str(item) for item in (raw_payload.get("entity_ids") or []) if str(item).strip()]
        if not entity_ids:
            raise ValueError("Home Assistant device entity_ids are missing")

        config, entities = HomeAssistantAuthService.get_entity_states(account=account, entity_ids=entity_ids)
        if not entities:
            raise ValueError("Home Assistant single-device refresh returned no entities")

        primary_entity = cls._pick_home_assistant_primary_entity(entities)
        attributes = primary_entity.get("attributes") or {}
        primary_entity_id = str(primary_entity.get("entity_id") or "")
        domain = primary_entity_id.split(".", 1)[0] if "." in primary_entity_id else primary_entity_id
        controls = cls._build_home_assistant_controls(entities, entity_registry_map={})
        room_data = {
            "id": device.room.slug if device.room else cls._make_room_id("home_assistant", "Home Assistant"),
            "name": device.room.name if device.room else str(config.get("location_name") or "Home Assistant"),
            "climate": str(config.get("time_zone") or ""),
            "summary": device.room.summary if device.room else "来自 Home Assistant 分组",
            "sort_order": device.room.sort_order if device.room else 10,
        }
        device_data = {
            "id": device.external_id,
            "room_id": room_data["id"],
            "name": device.name,
            "category": cls._map_home_assistant_domain_to_category(domain),
            "status": cls._map_home_assistant_status(str(primary_entity.get("state", ""))),
            "telemetry": cls._summarize_home_assistant_device(entities),
            "note": f"{len(entities)} 个 HA 实体已归属到该设备",
            "capabilities": [item["key"] for item in controls if item["kind"] != DeviceControl.KindChoices.SENSOR][:8],
            "controls": controls,
            "last_seen": timezone.now(),
            "sort_order": device.sort_order,
            "source_payload": {
                **raw_payload,
                "entity_ids": [item.get("entity_id") for item in entities],
                "device_name": raw_payload.get("device_name") or attributes.get("friendly_name") or device.name,
            },
        }
        return cls._persist_single_device_refresh(account, device=device, room_data=room_data, device_data=device_data, trigger=trigger)

    @classmethod
    def _refresh_mijia_device(cls, account: Account, *, device: DeviceSnapshot, trigger: str) -> dict:
        from mijiaAPI import get_device_info, mijiaDevice
        from providers.services import MijiaAuthService

        raw_payload = dict(device.source_payload or {})
        did = str(raw_payload.get("did") or "").strip()
        if not did:
            raise ValueError("MiJia device DID is missing")

        model = str(raw_payload.get("model") or "").strip()
        api = MijiaAuthService.get_authenticated_api(account=account)
        device_client = mijiaDevice(api, did=did)
        spec_failed = False
        try:
            spec = cls._load_mijia_spec(model, get_device_info=get_device_info)
        except Exception:
            spec = {}
            spec_failed = True

        controls = cls._build_mijia_controls(dev=raw_payload, spec=spec, device_client=device_client)
        if spec_failed and not controls:
            controls = cls._load_existing_device_controls(account, device_external_id=device.external_id)
        device_data = {
            "id": device.external_id,
            "room_id": device.room.slug if device.room else None,
            "name": cls._infer_mijia_device_name(dev=raw_payload, did=did, model=model),
            "category": cls._map_model_to_category(model),
            "status": device.status,
            "telemetry": cls._summarize_mijia_telemetry(controls, is_online=device.status != "offline"),
            "note": f"DID: {did} | 模型: {model or 'unknown'}",
            "capabilities": [item["key"] for item in controls if item["kind"] != DeviceControl.KindChoices.SENSOR][:8],
            "controls": controls,
            "last_seen": timezone.now(),
            "sort_order": device.sort_order,
            "source_payload": raw_payload,
        }
        room_data = None
        if device.room:
            room_data = {
                "id": device.room.slug,
                "name": device.room.name,
                "climate": device.room.climate,
                "summary": device.room.summary,
                "sort_order": device.room.sort_order,
            }
        return cls._persist_single_device_refresh(account, device=device, room_data=room_data, device_data=device_data, trigger=trigger)

    @classmethod
    def _load_mijia_spec(cls, model: str, *, get_device_info) -> dict:
        normalized_model = str(model or "").strip()
        if not normalized_model:
            return {}
        return get_device_info(normalized_model, cache_path=cls.mijia_spec_cache_dir)

    @classmethod
    def _load_existing_device_controls(cls, account: Account, *, device_external_id: str) -> list[dict]:
        existing_controls = (
            DeviceControl.objects.filter(account=account, device__external_id=device_external_id)
            .order_by("sort_order", "id")
        )
        return [cls._serialize_existing_control(control) for control in existing_controls]

    @staticmethod
    def _serialize_existing_control(control: DeviceControl) -> dict:
        return {
            "id": control.external_id,
            "parent_id": control.parent_external_id,
            "source_type": control.source_type,
            "kind": control.kind,
            "key": control.key,
            "label": control.label,
            "group_label": control.group_label,
            "writable": control.writable,
            "value": control.value if control.value is not None else {},
            "unit": control.unit,
            "options": control.options or [],
            "range_spec": control.range_spec or {},
            "action_params": control.action_params or {},
            "source_payload": control.source_payload or {},
            "sort_order": control.sort_order,
        }

    @classmethod
    def _apply_mijia_control_fallback(cls, device_data: dict, *, stale_controls: list[dict]) -> None:
        if not str(device_data.get("id") or "").startswith("mijia:"):
            return
        if device_data.get("controls"):
            return
        if not stale_controls:
            return
        device_data["controls"] = [dict(control) for control in stale_controls]
        device_data["capabilities"] = [
            control["key"]
            for control in device_data["controls"]
            if control["kind"] != DeviceControl.KindChoices.SENSOR
        ][:8]
        device_data["telemetry"] = cls._summarize_mijia_telemetry(
            device_data["controls"],
            is_online=device_data.get("status") != DeviceSnapshot.StatusChoices.OFFLINE,
        )

    @classmethod
    def _persist_single_device_refresh(
        cls,
        account: Account,
        *,
        device: DeviceSnapshot,
        room_data: dict | None,
        device_data: dict,
        trigger: str,
    ) -> dict:
        with transaction.atomic():
            room = device.room
            if room_data:
                room, _ = DeviceRoom.objects.update_or_create(
                    account=account,
                    slug=room_data["id"],
                    defaults={
                        "name": room_data["name"],
                        "climate": room_data["climate"],
                        "summary": room_data["summary"],
                        "sort_order": room_data["sort_order"],
                    },
                )

            device.room = room
            device.name = device_data["name"]
            device.category = device_data["category"]
            device.status = device_data["status"]
            device.telemetry = device_data["telemetry"]
            device.note = device_data["note"]
            device.capabilities = device_data["capabilities"]
            device.last_seen = device_data["last_seen"]
            device.sort_order = device_data["sort_order"]
            device.source_payload = device_data["source_payload"]
            device.save()

            DeviceControl.objects.filter(account=account, device=device).delete()
            for control_data in device_data.get("controls", []):
                DeviceControl.objects.create(
                    account=account,
                    device=device,
                    external_id=control_data["id"],
                    parent_external_id=control_data.get("parent_id", "") or "",
                    source_type=control_data["source_type"],
                    kind=control_data["kind"],
                    key=control_data["key"],
                    label=control_data["label"],
                    group_label=control_data.get("group_label", ""),
                    writable=control_data.get("writable", False),
                    value=control_data.get("value") if control_data.get("value") is not None else {},
                    unit=control_data.get("unit", ""),
                    options=control_data.get("options", []),
                    range_spec=control_data.get("range_spec", {}),
                    action_params=control_data.get("action_params", {}),
                    source_payload=control_data.get("source_payload", {}),
                    sort_order=control_data.get("sort_order", 0),
                )

            state = cls._get_state(account)
            state.last_trigger = trigger
            state.requested_trigger = ""
            state.refresh_requested_at = None
            state.last_error = ""
            state.refreshed_at = timezone.now()
            state.save(update_fields=["last_trigger", "requested_trigger", "refresh_requested_at", "last_error", "refreshed_at", "updated_at"])

        return cls.get_dashboard(account)

    @classmethod
    def _build_midea_cloud_controls(cls, raw_device: dict) -> list[dict]:
        controls: list[dict] = []
        raw_controls = raw_device.get("controls") or []
        device_id = str(
            raw_device.get("id")
            or raw_device.get("device_id")
            or raw_device.get("sn")
            or raw_device.get("appliance_code")
            or ""
        ).strip()
        sort_order = 10

        device_type_value = raw_device.get("device_type")
        if isinstance(device_type_value, str) and device_type_value.startswith("0x"):
            try:
                device_type_value = int(device_type_value, 16)
            except ValueError:
                device_type_value = None
        mapping = (
            get_device_mapping(
                device_type_value,
                sn8=str(raw_device.get("sn8") or ""),
                subtype=raw_device.get("model_number"),
                category=str(raw_device.get("category") or ""),
            )
            if isinstance(device_type_value, int)
            else {}
        )
        status_payload = raw_device.get("status_payload") or {}

        # Prefer the curated upstream mapping first so we preserve vendor intent
        # for writable controls, labels, grouping, and value transforms.
        mapping_controls = mapping.get("controls") or []
        for mapping_control in mapping_controls:
            if not isinstance(mapping_control, dict):
                continue
            label = str(mapping_control.get("label") or mapping_control.get("key") or "")
            name_attribute = str(mapping_control.get("name_attribute") or "").strip()
            if name_attribute:
                dynamic_label = status_payload.get(name_attribute)
                if dynamic_label not in (None, ""):
                    label = str(dynamic_label)
            action_params = {
                "device_id": device_id,
                "control_key": mapping_control.get("control_key") or mapping_control.get("key"),
            }
            if isinstance(mapping_control.get("control_template"), dict):
                action_params["control_template"] = dict(mapping_control["control_template"])
            if isinstance(mapping_control.get("value_transform"), dict):
                action_params["value_transform"] = dict(mapping_control["value_transform"])
            if isinstance(mapping_control.get("actions"), dict):
                # toggle / action controls use named actions
                actions = []
                for action_id, action_payload in mapping_control["actions"].items():
                    actions.append({"id": action_id, "label": cls._titleize_slug(action_id)})
                action_params["actions"] = actions
            options = []
            for option in mapping_control.get("options") or []:
                if not isinstance(option, dict):
                    continue
                option_record = {"label": option.get("label"), "value": option.get("value")}
                if isinstance(option.get("control"), dict):
                    option_record["control"] = option["control"]
                options.append(option_record)
            value = status_payload.get(mapping_control.get("value_key"))
            controls.append(
                {
                    "id": f"midea_cloud:{device_id}:{mapping_control['key']}",
                    "parent_id": f"midea_cloud:{device_id}",
                    "source_type": (
                        DeviceControl.SourceTypeChoices.MIDEA_CLOUD_ACTION
                        if mapping_control["kind"] == DeviceControl.KindChoices.ACTION
                        else DeviceControl.SourceTypeChoices.MIDEA_CLOUD_PROPERTY
                    ),
                    "kind": mapping_control["kind"],
                    "key": mapping_control["key"],
                    "label": label,
                    "group_label": mapping_control.get("group_label", ""),
                    "writable": bool(mapping_control.get("writable", False)),
                    "value": value if value is not None else {},
                    "unit": mapping_control.get("unit", ""),
                    "options": options,
                    "range_spec": dict(mapping_control.get("range_spec") or {}),
                    "action_params": action_params,
                    "source_payload": {
                        "mapping": mapping_control,
                        "status_value": value,
                    },
                    "sort_order": sort_order,
                }
            )
            sort_order += 10

        if controls:
            # After the curated controls are built, append only meaningful scalar
            # leftovers as read-only telemetry so useful state is still visible.
            mapped_value_keys = {
                str(mapping_control.get("value_key"))
                for mapping_control in mapping_controls
                if mapping_control.get("value_key")
            }
            mapped_auxiliary_keys = {
                str(mapping_control.get("name_attribute"))
                for mapping_control in mapping_controls
                if mapping_control.get("name_attribute")
            }
            for status_key, status_value in (status_payload or {}).items():
                if status_key in mapped_value_keys:
                    continue
                if status_key in mapped_auxiliary_keys:
                    continue
                if status_key in cls.midea_cloud_extra_status_ignore_keys:
                    continue
                if str(status_key).startswith("_"):
                    continue
                if isinstance(status_value, (dict, list)) or status_value in (None, ""):
                    continue
                controls.append(
                    {
                        "id": f"midea_cloud:{device_id}:status:{status_key}",
                        "parent_id": f"midea_cloud:{device_id}",
                        "source_type": DeviceControl.SourceTypeChoices.MIDEA_CLOUD_PROPERTY,
                        "kind": DeviceControl.KindChoices.SENSOR,
                        "key": status_key,
                        "label": cls._titleize_slug(status_key),
                        "group_label": "运行状态",
                        "writable": False,
                        "value": status_value,
                        "unit": "",
                        "options": [],
                        "range_spec": {},
                        "action_params": {},
                        "source_payload": {"key": status_key, "value": status_value},
                        "sort_order": sort_order,
                    }
                )
                sort_order += 10
            return controls

        if isinstance(raw_controls, list):
            for raw_control in raw_controls:
                if not isinstance(raw_control, dict):
                    continue

                control_key = str(raw_control.get("key") or raw_control.get("name") or "").strip()
                if not control_key:
                    continue

                control_type = str(raw_control.get("kind") or raw_control.get("type") or "").strip().lower()
                source_type = (
                    DeviceControl.SourceTypeChoices.MIDEA_CLOUD_ACTION
                    if control_type == "action"
                    else DeviceControl.SourceTypeChoices.MIDEA_CLOUD_PROPERTY
                )
                kind = cls._infer_midea_cloud_control_kind(raw_control)
                action_params = dict(raw_control.get("action_params") or {})
                action_params.setdefault("device_id", device_id)
                action_params.setdefault("control_key", control_key)

                controls.append(
                    {
                        "id": f"midea_cloud:{device_id}:{control_key}",
                        "parent_id": f"midea_cloud:{device_id}",
                        "source_type": source_type,
                        "kind": kind,
                        "key": control_key,
                        "label": str(raw_control.get("label") or raw_control.get("name") or control_key),
                        "group_label": str(raw_control.get("group_label") or ""),
                        "writable": bool(raw_control.get("writable", kind != DeviceControl.KindChoices.SENSOR)),
                        "value": raw_control.get("value") if raw_control.get("value") is not None else {},
                        "unit": str(raw_control.get("unit") or ""),
                        "options": list(raw_control.get("options") or []),
                        "range_spec": dict(raw_control.get("range_spec") or {}),
                        "action_params": action_params,
                        "source_payload": raw_control,
                        "sort_order": sort_order,
                    }
                )
                sort_order += 10

        if controls:
            return controls

        if not isinstance(status_payload, dict):
            return controls

        ignored_keys = {"error", "msg", "message", "ts", "timestamp"}
        for status_key, status_value in status_payload.items():
            if status_key in ignored_keys:
                continue
            if isinstance(status_value, (dict, list)) or status_value in (None, ""):
                continue

            controls.append(
                {
                    "id": f"midea_cloud:{device_id}:status:{status_key}",
                    "parent_id": f"midea_cloud:{device_id}",
                    "source_type": DeviceControl.SourceTypeChoices.MIDEA_CLOUD_PROPERTY,
                    "kind": DeviceControl.KindChoices.SENSOR,
                    "key": status_key,
                    "label": cls._titleize_slug(status_key),
                    "group_label": "运行状态",
                    "writable": False,
                    "value": status_value,
                    "unit": "",
                    "options": [],
                    "range_spec": {},
                    "action_params": {},
                    "source_payload": {"key": status_key, "value": status_value},
                    "sort_order": sort_order,
                }
            )
            sort_order += 10

        return controls

    @classmethod
    def _build_hisense_ha_controls(cls, raw_device: dict) -> list[dict]:
        device_id = str(raw_device.get("device_id") or raw_device.get("id") or "").strip()
        status_payload = raw_device.get("status_payload") if isinstance(raw_device.get("status_payload"), dict) else {}
        controls: list[dict] = []
        definitions = raw_device.get("controls") if isinstance(raw_device.get("controls"), list) else []
        sort_order = 10

        for definition in definitions:
            if not isinstance(definition, dict):
                continue
            key = str(definition.get("key") or "").strip()
            if not key:
                continue
            kind = str(definition.get("kind") or DeviceControl.KindChoices.SENSOR)
            control = {
                "id": f"hisense_ha:{device_id}:{key}",
                "parent_id": f"hisense_ha:{device_id}",
                "source_type": (
                    DeviceControl.SourceTypeChoices.HISENSE_HA_ACTION
                    if kind == DeviceControl.KindChoices.ACTION
                    else DeviceControl.SourceTypeChoices.HISENSE_HA_PROPERTY
                ),
                "kind": kind,
                "key": key,
                "label": str(definition.get("label") or key).strip(),
                "group_label": "空调",
                "writable": bool(definition.get("writable")),
                "value": None if kind == DeviceControl.KindChoices.ACTION else status_payload.get(key),
                "unit": str(definition.get("unit") or "").strip(),
                "options": definition.get("options") or [],
                "range_spec": definition.get("range") or {},
                "action_params": {
                    "device_id": device_id,
                    "wifi_id": raw_device.get("wifi_id"),
                    "control_key": key,
                    "command_id": definition.get("command_id"),
                    "action": definition.get("action"),
                },
                "source_payload": definition,
                "sort_order": sort_order,
            }
            controls.append(control)
            sort_order += 10

        for key, label, unit in (
            ("indoor_temperature", "室温", "°C"),
            ("nature_wind", "自然风", ""),
        ):
            if key not in status_payload:
                continue
            controls.append(
                {
                    "id": f"hisense_ha:{device_id}:status:{key}",
                    "parent_id": f"hisense_ha:{device_id}",
                    "source_type": DeviceControl.SourceTypeChoices.HISENSE_HA_PROPERTY,
                    "kind": DeviceControl.KindChoices.SENSOR,
                    "key": key,
                    "label": label,
                    "group_label": "状态",
                    "writable": False,
                    "value": status_payload.get(key),
                    "unit": unit,
                    "options": [],
                    "range_spec": {},
                    "action_params": {},
                    "source_payload": {"key": key, "value": status_payload.get(key)},
                    "sort_order": sort_order,
                }
            )
            sort_order += 10

        return controls

    @classmethod
    def _build_mijia_controls(
        cls,
        *,
        dev: dict,
        spec: dict,
        device_client: Any = None,
    ) -> list[dict]:
        did = str(dev.get("did"))
        controls: list[dict] = []
        sort_order = 10

        for prop in spec.get("properties", []) or []:
            name = str(prop.get("name") or "").strip()
            if not name:
                continue

            rw = str(prop.get("rw") or "")
            value = None
            if "r" in rw and device_client is not None:
                try:
                    value = device_client.get(name)
                except Exception:
                    value = None

            kind = cls._infer_mijia_control_kind(prop)
            range_spec = {}
            if prop.get("range"):
                range_values = prop.get("range") or []
                if len(range_values) >= 2:
                    range_spec = {
                        "min": range_values[0],
                        "max": range_values[1],
                        "step": range_values[2] if len(range_values) >= 3 else 1,
                    }

            controls.append(
                {
                    "id": f"mijia:{did}:property:{name}",
                    "source_type": DeviceControl.SourceTypeChoices.MIJIA_PROPERTY,
                    "kind": kind,
                    "key": name,
                    "label": cls._pick_mijia_label(prop, fallback=name),
                    "group_label": cls._extract_mijia_group_label(name),
                    "writable": "w" in rw,
                    "value": value if value is not None else {},
                    "unit": prop.get("unit") or "",
                    "options": cls._normalize_mijia_options(prop.get("value-list")),
                    "range_spec": range_spec,
                    "action_params": {
                        "kind": "property",
                        "did": did,
                        "property": name,
                    },
                    "source_payload": prop,
                    "sort_order": sort_order,
                }
            )
            sort_order += 10

        for action in spec.get("actions", []) or []:
            name = str(action.get("name") or "").strip()
            if not name:
                continue

            controls.append(
                {
                    "id": f"mijia:{did}:action:{name}",
                    "source_type": DeviceControl.SourceTypeChoices.MIJIA_ACTION,
                    "kind": DeviceControl.KindChoices.ACTION,
                    "key": name,
                    "label": cls._pick_mijia_label(action, fallback=name),
                    "group_label": cls._extract_mijia_group_label(name),
                    "writable": True,
                    "value": {},
                    "unit": "",
                    "options": [],
                    "range_spec": {},
                    "action_params": {
                        "kind": "action",
                        "did": did,
                        "action": name,
                    },
                    "source_payload": action,
                    "sort_order": sort_order,
                }
            )
            sort_order += 10

        return controls

    @classmethod
    def _build_home_assistant_snapshot(cls, account: Account) -> dict:
        from providers.services import HomeAssistantAuthService

        config, states, registry = HomeAssistantAuthService.get_graph(account=account)
        default_room_name = config.get("location_name") or "Home Assistant"
        room_map: dict[str, dict] = {}
        grouped_entities: dict[tuple[str, str], list[dict]] = defaultdict(list)
        area_map = {str(area.get("area_id")): area for area in (registry.get("areas") or [])}
        device_registry_map = {str(device.get("id")): device for device in (registry.get("devices") or [])}
        entity_registry_map = {
            str(entity.get("entity_id")): entity
            for entity in (registry.get("entities") or [])
            if entity.get("entity_id")
        }

        for entity in states:
            entity_id = str(entity.get("entity_id", "")).strip()
            if not entity_id:
                continue

            domain = entity_id.split(".", 1)[0]
            if domain not in cls.supported_ha_domains:
                continue

            attributes = entity.get("attributes") or {}
            friendly_name = str(attributes.get("friendly_name") or entity_id)
            # 过滤天文实体（sun.sun, moon.moon 等是位置计算，非物理设备，可能没有 device_id）
            if entity_id.split(".", 1)[0] in {"sun", "moon"}:
                continue
            entity_registry = entity_registry_map.get(entity_id, {})
            if entity_registry.get("hidden_by") or entity_registry.get("disabled_by"):
                continue

            registry_device = device_registry_map.get(str(entity_registry.get("device_id") or ""), {})
            # 过滤虚拟设备（entry_type="service" 表示非物理设备，如 Sun, Backup, HACS 等）
            if registry_device.get("entry_type") == "service":
                continue
            registry_area = area_map.get(
                str(entity_registry.get("area_id") or registry_device.get("area_id") or "")
            )

            room_name = str(
                (registry_area or {}).get("name")
                or attributes.get("room")
                or attributes.get("area_name")
                or attributes.get("floor_name")
                or default_room_name
            )
            room_id = cls._make_room_id("home_assistant", room_name)
            room_map.setdefault(
                room_id,
                {
                    "id": room_id,
                    "name": room_name,
                    "climate": config.get("time_zone", ""),
                    "summary": f"来自 Home Assistant 分组: {room_name}",
                    "sort_order": 10 + len(room_map) * 10,
                },
            )

            device_key = cls._infer_home_assistant_device_key(
                entity_id=entity_id,
                friendly_name=friendly_name,
                attributes=attributes,
                registry_entity=entity_registry,
                registry_device=registry_device,
            )
            grouped_entities[(room_id, device_key)].append(entity)

        devices_data: list[dict] = []
        for index, ((room_id, device_key), entities) in enumerate(grouped_entities.items(), start=1):
            primary_entity = cls._pick_home_assistant_primary_entity(entities)
            attributes = primary_entity.get("attributes") or {}
            friendly_name = str(attributes.get("friendly_name") or primary_entity.get("entity_id"))
            entity_id = str(primary_entity.get("entity_id"))
            domain = entity_id.split(".", 1)[0]
            entity_registry = entity_registry_map.get(entity_id, {})
            registry_device = device_registry_map.get(str(entity_registry.get("device_id") or ""), {})
            controls = cls._build_home_assistant_controls(
                entities,
                entity_registry_map=entity_registry_map,
            )
            devices_data.append(
                {
                    "id": f"home_assistant:{device_key}",
                    "room_id": room_id,
                    "name": cls._infer_home_assistant_device_name(
                        device_key=device_key,
                        friendly_name=friendly_name,
                        registry_device=registry_device,
                    ),
                    "category": cls._map_home_assistant_domain_to_category(domain),
                    "status": cls._map_home_assistant_status(str(primary_entity.get("state", ""))),
                    "telemetry": cls._summarize_home_assistant_device(entities),
                    "note": f"{len(entities)} 个 HA 实体已归属到该设备",
                    "capabilities": [control["key"] for control in controls if control["kind"] != DeviceControl.KindChoices.SENSOR][:8],
                    "controls": controls,
                    "last_seen": timezone.now(),
                    "sort_order": index * 10,
                    "source_payload": {
                        "entity_ids": [item.get("entity_id") for item in entities],
                        "device_id": registry_device.get("id"),
                        "device_name": registry_device.get("name_by_user") or registry_device.get("name"),
                        "area_id": entity_registry.get("area_id") or registry_device.get("area_id"),
                    },
                }
            )

        return {
            "source": "home_assistant",
            "rooms": list(room_map.values()),
            "devices": devices_data,
            "anomalies": [],
            "rules": [],
        }

    @classmethod
    def _build_home_assistant_controls(
        cls,
        entities: list[dict],
        *,
        entity_registry_map: dict[str, dict] | None = None,
    ) -> list[dict]:
        entity_registry_map = entity_registry_map or {}
        controls: list[dict] = []
        sort_order = 10
        for entity in entities:
            entity_id = str(entity.get("entity_id", ""))
            domain = entity_id.split(".", 1)[0]
            attributes = entity.get("attributes") or {}
            registry_entity = entity_registry_map.get(entity_id, {})
            friendly_name = str(
                registry_entity.get("name")
                or registry_entity.get("original_name")
                or attributes.get("friendly_name")
                or entity_id
            )
            group_label = cls._extract_home_assistant_group_label(
                friendly_name,
                entity_id=entity_id,
                attributes=attributes,
                registry_entity=registry_entity,
            )
            state = entity.get("state")

            if domain in {"sensor", "binary_sensor", "camera"}:
                controls.append(
                    cls._build_ha_control_record(
                        entity_id=entity_id,
                        key=entity_id,
                        label=friendly_name,
                        kind=DeviceControl.KindChoices.SENSOR,
                        writable=False,
                        value=state,
                        unit=attributes.get("unit_of_measurement") or "",
                        group_label=group_label,
                        source_payload=entity,
                        sort_order=sort_order,
                    )
                )
                sort_order += 10
                continue

            if domain in {"switch", "input_boolean", "light", "fan", "humidifier", "lock"}:
                controls.append(
                    cls._build_ha_control_record(
                        entity_id=entity_id,
                        key=entity_id,
                        label=friendly_name,
                        kind=DeviceControl.KindChoices.TOGGLE,
                        writable=True,
                        value=state,
                        group_label=group_label,
                        action_params={
                            "service_domain": "lock" if domain == "lock" else domain,
                            "entity_id": entity_id,
                            "actions": cls._build_ha_toggle_actions(domain),
                        },
                        source_payload=entity,
                        sort_order=sort_order,
                    )
                )
                sort_order += 10

                if domain == "light" and attributes.get("brightness") is not None:
                    controls.append(
                        cls._build_ha_control_record(
                            entity_id=entity_id,
                            key=f"{entity_id}:brightness",
                            label=f"{friendly_name} 亮度",
                            kind=DeviceControl.KindChoices.RANGE,
                            writable=True,
                            value=attributes.get("brightness"),
                            range_spec={"min": 0, "max": 255, "step": 1},
                            group_label=group_label,
                            action_params={
                                "service_domain": "light",
                                "entity_id": entity_id,
                                "service": "turn_on",
                                "value_field": "brightness",
                            },
                            source_payload=entity,
                            sort_order=sort_order,
                        )
                    )
                    sort_order += 10

                if domain == "light" and attributes.get("color_temp_kelvin") is not None:
                    controls.append(
                        cls._build_ha_control_record(
                            entity_id=entity_id,
                            key=f"{entity_id}:color_temp_kelvin",
                            label=f"{friendly_name} 色温",
                            kind=DeviceControl.KindChoices.RANGE,
                            writable=True,
                            value=attributes.get("color_temp_kelvin"),
                            range_spec={
                                "min": attributes.get("min_color_temp_kelvin", 2000),
                                "max": attributes.get("max_color_temp_kelvin", 6500),
                                "step": 100,
                            },
                            unit="K",
                            group_label=group_label,
                            action_params={
                                "service_domain": "light",
                                "entity_id": entity_id,
                                "service": "turn_on",
                                "value_field": "color_temp_kelvin",
                            },
                            source_payload=entity,
                            sort_order=sort_order,
                        )
                    )
                    sort_order += 10

                if domain == "fan" and attributes.get("percentage") is not None:
                    controls.append(
                        cls._build_ha_control_record(
                            entity_id=entity_id,
                            key=f"{entity_id}:percentage",
                            label=f"{friendly_name} 风速",
                            kind=DeviceControl.KindChoices.RANGE,
                            writable=True,
                            value=attributes.get("percentage"),
                            range_spec={"min": 0, "max": 100, "step": 1},
                            group_label=group_label,
                            action_params={
                                "service_domain": "fan",
                                "entity_id": entity_id,
                                "service": "set_percentage",
                                "value_field": "percentage",
                            },
                            source_payload=entity,
                            sort_order=sort_order,
                        )
                    )
                    sort_order += 10

                if domain == "fan" and attributes.get("preset_modes"):
                    controls.append(
                        cls._build_ha_control_record(
                            entity_id=entity_id,
                            key=f"{entity_id}:preset_mode",
                            label=f"{friendly_name} 预设模式",
                            kind=DeviceControl.KindChoices.ENUM,
                            writable=True,
                            value=attributes.get("preset_mode") or state,
                            options=cls._build_enum_options(attributes.get("preset_modes")),
                            group_label=group_label,
                            action_params={
                                "service_domain": "fan",
                                "entity_id": entity_id,
                                "service": "set_preset_mode",
                                "value_field": "preset_mode",
                            },
                            source_payload=entity,
                            sort_order=sort_order,
                        )
                    )
                    sort_order += 10

                if domain == "humidifier" and attributes.get("available_modes"):
                    controls.append(
                        cls._build_ha_control_record(
                            entity_id=entity_id,
                            key=f"{entity_id}:mode",
                            label=f"{friendly_name} 模式",
                            kind=DeviceControl.KindChoices.ENUM,
                            writable=True,
                            value=attributes.get("mode") or state,
                            options=cls._build_enum_options(attributes.get("available_modes")),
                            group_label=group_label,
                            action_params={
                                "service_domain": "humidifier",
                                "entity_id": entity_id,
                                "service": "set_mode",
                                "value_field": "mode",
                            },
                            source_payload=entity,
                            sort_order=sort_order,
                        )
                    )
                    sort_order += 10
                continue

            if domain in {"number", "input_number"}:
                controls.append(
                    cls._build_ha_control_record(
                        entity_id=entity_id,
                        key=entity_id,
                        label=friendly_name,
                        kind=DeviceControl.KindChoices.RANGE,
                        writable=True,
                        value=cls._parse_numeric_value(state),
                        range_spec={
                            "min": attributes.get("min", 0),
                            "max": attributes.get("max", 100),
                            "step": attributes.get("step", 1),
                        },
                        unit=attributes.get("unit_of_measurement") or "",
                        group_label=group_label,
                        action_params={
                            "service_domain": domain,
                            "entity_id": entity_id,
                            "service": "set_value",
                            "value_field": "value",
                        },
                        source_payload=entity,
                        sort_order=sort_order,
                    )
                )
                sort_order += 10
                continue

            if domain == "select":
                controls.append(
                    cls._build_ha_control_record(
                        entity_id=entity_id,
                        key=entity_id,
                        label=friendly_name,
                        kind=DeviceControl.KindChoices.ENUM,
                        writable=True,
                        value=state,
                        options=[{"label": str(item), "value": item} for item in (attributes.get("options") or [])],
                        group_label=group_label,
                        action_params={
                            "service_domain": "select",
                            "entity_id": entity_id,
                            "service": "select_option",
                            "value_field": "option",
                        },
                        source_payload=entity,
                        sort_order=sort_order,
                    )
                )
                sort_order += 10
                continue

            if domain in {"button", "scene", "script"}:
                controls.append(
                    cls._build_ha_control_record(
                        entity_id=entity_id,
                        key=entity_id,
                        label=friendly_name,
                        kind=DeviceControl.KindChoices.ACTION,
                        writable=True,
                        value=None,
                        group_label=group_label,
                        action_params={
                            "service_domain": domain,
                            "entity_id": entity_id,
                            "service": "press" if domain == "button" else "turn_on",
                        },
                        source_payload=entity,
                        sort_order=sort_order,
                    )
                )
                sort_order += 10
                continue

            if domain == "climate":
                controls.append(
                    cls._build_ha_control_record(
                        entity_id=entity_id,
                        key=f"{entity_id}:hvac_mode",
                        label=f"{friendly_name} 模式",
                        kind=DeviceControl.KindChoices.ENUM,
                        writable=True,
                        value=state,
                        options=[{"label": str(item), "value": item} for item in (attributes.get("hvac_modes") or [])],
                        group_label=group_label,
                        action_params={
                            "service_domain": "climate",
                            "entity_id": entity_id,
                            "service": "set_hvac_mode",
                            "value_field": "hvac_mode",
                        },
                        source_payload=entity,
                        sort_order=sort_order,
                    )
                )
                sort_order += 10
                if attributes.get("temperature") is not None:
                    controls.append(
                        cls._build_ha_control_record(
                            entity_id=entity_id,
                            key=f"{entity_id}:target_temperature",
                            label=f"{friendly_name} 目标温度",
                            kind=DeviceControl.KindChoices.RANGE,
                            writable=True,
                            value=attributes.get("temperature"),
                            range_spec={
                                "min": attributes.get("min_temp", 16),
                                "max": attributes.get("max_temp", 30),
                                "step": attributes.get("target_temp_step", 1),
                            },
                            unit=attributes.get("temperature_unit") or "°C",
                            group_label=group_label,
                            action_params={
                                "service_domain": "climate",
                                "entity_id": entity_id,
                                "service": "set_temperature",
                                "value_field": "temperature",
                            },
                            source_payload=entity,
                            sort_order=sort_order,
                        )
                    )
                    sort_order += 10
                if attributes.get("current_temperature") is not None:
                    controls.append(
                        cls._build_ha_control_record(
                            entity_id=entity_id,
                            key=f"{entity_id}:current_temperature",
                            label=f"{friendly_name} 当前温度",
                            kind=DeviceControl.KindChoices.SENSOR,
                            writable=False,
                            value=attributes.get("current_temperature"),
                            unit=attributes.get("temperature_unit") or "°C",
                            group_label=group_label,
                            source_payload=entity,
                            sort_order=sort_order,
                        )
                    )
                    sort_order += 10
                for extra_key, label_text, service_name, value_field in (
                    ("preset_modes", "预设模式", "set_preset_mode", "preset_mode"),
                    ("fan_modes", "风速模式", "set_fan_mode", "fan_mode"),
                    ("swing_modes", "扫风模式", "set_swing_mode", "swing_mode"),
                ):
                    if attributes.get(extra_key):
                        controls.append(
                            cls._build_ha_control_record(
                                entity_id=entity_id,
                                key=f"{entity_id}:{value_field}",
                                label=f"{friendly_name} {label_text}",
                                kind=DeviceControl.KindChoices.ENUM,
                                writable=True,
                                value=attributes.get(value_field) or state,
                                options=cls._build_enum_options(attributes.get(extra_key)),
                                group_label=group_label,
                                action_params={
                                    "service_domain": "climate",
                                    "entity_id": entity_id,
                                    "service": service_name,
                                    "value_field": value_field,
                                },
                                source_payload=entity,
                                sort_order=sort_order,
                            )
                        )
                        sort_order += 10
                continue

            if domain == "cover":
                controls.append(
                    cls._build_ha_control_record(
                        entity_id=entity_id,
                        key=entity_id,
                        label=friendly_name,
                        kind=DeviceControl.KindChoices.ACTION,
                        writable=True,
                        value=state,
                        group_label=group_label,
                        action_params={
                            "service_domain": "cover",
                            "entity_id": entity_id,
                            "actions": [
                                {"id": "open_cover", "label": "打开"},
                                {"id": "close_cover", "label": "关闭"},
                                {"id": "stop_cover", "label": "停止"},
                            ],
                        },
                        source_payload=entity,
                        sort_order=sort_order,
                    )
                )
                sort_order += 10
                if attributes.get("current_position") is not None:
                    controls.append(
                        cls._build_ha_control_record(
                            entity_id=entity_id,
                            key=f"{entity_id}:position",
                            label=f"{friendly_name} 开合度",
                            kind=DeviceControl.KindChoices.RANGE,
                            writable=True,
                            value=attributes.get("current_position"),
                            range_spec={"min": 0, "max": 100, "step": 1},
                            group_label=group_label,
                            action_params={
                                "service_domain": "cover",
                                "entity_id": entity_id,
                                "service": "set_cover_position",
                                "value_field": "position",
                            },
                            source_payload=entity,
                            sort_order=sort_order,
                        )
                    )
                    sort_order += 10
                continue

            if domain == "media_player":
                controls.append(
                    cls._build_ha_control_record(
                        entity_id=entity_id,
                        key=entity_id,
                        label=friendly_name,
                        kind=DeviceControl.KindChoices.ACTION,
                        writable=True,
                        value=state,
                        group_label=group_label,
                        action_params={
                            "service_domain": "media_player",
                            "entity_id": entity_id,
                            "actions": [
                                {"id": "turn_on", "label": "开启"},
                                {"id": "turn_off", "label": "关闭"},
                                {"id": "media_play_pause", "label": "播放/暂停"},
                            ],
                        },
                        source_payload=entity,
                        sort_order=sort_order,
                    )
                )
                sort_order += 10
                if attributes.get("volume_level") is not None:
                    controls.append(
                        cls._build_ha_control_record(
                            entity_id=entity_id,
                            key=f"{entity_id}:volume_level",
                            label=f"{friendly_name} 音量",
                            kind=DeviceControl.KindChoices.RANGE,
                            writable=True,
                            value=attributes.get("volume_level"),
                            range_spec={"min": 0, "max": 1, "step": 0.05},
                            group_label=group_label,
                            action_params={
                                "service_domain": "media_player",
                                "entity_id": entity_id,
                                "service": "volume_set",
                                "value_field": "volume_level",
                            },
                            source_payload=entity,
                            sort_order=sort_order,
                        )
                    )
                    sort_order += 10
                if attributes.get("source_list"):
                    controls.append(
                        cls._build_ha_control_record(
                            entity_id=entity_id,
                            key=f"{entity_id}:source",
                            label=f"{friendly_name} 输入源",
                            kind=DeviceControl.KindChoices.ENUM,
                            writable=True,
                            value=attributes.get("source") or state,
                            options=cls._build_enum_options(attributes.get("source_list")),
                            group_label=group_label,
                            action_params={
                                "service_domain": "media_player",
                                "entity_id": entity_id,
                                "service": "select_source",
                                "value_field": "source",
                            },
                            source_payload=entity,
                            sort_order=sort_order,
                        )
                    )
                    sort_order += 10
                continue

            if domain == "vacuum":
                controls.append(
                    cls._build_ha_control_record(
                        entity_id=entity_id,
                        key=entity_id,
                        label=friendly_name,
                        kind=DeviceControl.KindChoices.ACTION,
                        writable=True,
                        value=state,
                        group_label=group_label,
                        action_params={
                            "service_domain": "vacuum",
                            "entity_id": entity_id,
                            "actions": [
                                {"id": "start", "label": "开始"},
                                {"id": "pause", "label": "暂停"},
                                {"id": "return_to_base", "label": "回充"},
                            ],
                        },
                        source_payload=entity,
                        sort_order=sort_order,
                    )
                )
                sort_order += 10
                if attributes.get("fan_speed_list"):
                    controls.append(
                        cls._build_ha_control_record(
                            entity_id=entity_id,
                            key=f"{entity_id}:fan_speed",
                            label=f"{friendly_name} 吸力模式",
                            kind=DeviceControl.KindChoices.ENUM,
                            writable=True,
                            value=attributes.get("fan_speed") or state,
                            options=cls._build_enum_options(attributes.get("fan_speed_list")),
                            group_label=group_label,
                            action_params={
                                "service_domain": "vacuum",
                                "entity_id": entity_id,
                                "service": "set_fan_speed",
                                "value_field": "fan_speed",
                            },
                            source_payload=entity,
                            sort_order=sort_order,
                        )
                    )
                    sort_order += 10
                continue

            controls.append(
                cls._build_ha_control_record(
                    entity_id=entity_id,
                    key=entity_id,
                    label=friendly_name,
                    kind=DeviceControl.KindChoices.SENSOR,
                    writable=False,
                    value=state,
                    group_label=group_label,
                    source_payload=entity,
                    sort_order=sort_order,
                )
            )
            sort_order += 10

        return controls

    @staticmethod
    def _build_enum_options(values: Any) -> list[dict]:
        if not isinstance(values, list):
            return []
        return [{"label": str(item), "value": item} for item in values]

    @staticmethod
    def _build_ha_control_record(
        *,
        entity_id: str,
        key: str,
        label: str,
        kind: str,
        writable: bool,
        value: Any,
        group_label: str,
        source_payload: dict,
        sort_order: int,
        unit: str = "",
        options: list[dict] | None = None,
        range_spec: dict | None = None,
        action_params: dict | None = None,
    ) -> dict:
        return {
            "id": f"home_assistant:{key}",
            "parent_id": f"home_assistant:{entity_id}",
            "source_type": DeviceControl.SourceTypeChoices.HA_ENTITY,
            "kind": kind,
            "key": key,
            "label": label,
            "group_label": group_label,
            "writable": writable,
            "value": value if value is not None else {},
            "unit": unit,
            "options": options or [],
            "range_spec": range_spec or {},
            "action_params": action_params or {},
            "source_payload": source_payload,
            "sort_order": sort_order,
        }

    @classmethod
    def _execute_home_assistant_control(cls, account: Account, *, control: DeviceControl, action: str, value: Any) -> None:
        from providers.services import HomeAssistantAuthService

        auth_obj = HomeAssistantAuthService.get_auth_record(account=account, active_only=True)
        payload = HomeAssistantAuthService._extract_payload(auth_obj)
        if not payload:
            raise ValueError("No active Home Assistant authorization found")

        base_url = HomeAssistantAuthService._normalize_base_url(payload.get("base_url", ""))
        headers = HomeAssistantAuthService._build_headers(payload.get("access_token", ""))
        params = control.action_params or {}
        service_domain = params.get("service_domain")
        entity_id = params.get("entity_id")
        if not service_domain or not entity_id:
            raise ValueError("Home Assistant control metadata is incomplete")

        if control.kind == DeviceControl.KindChoices.TOGGLE:
            service = action or "toggle"
            if service not in {"turn_on", "turn_off", "toggle", "lock", "unlock"}:
                raise ValueError("Unsupported toggle action")
            body = {"entity_id": entity_id}
        elif control.kind == DeviceControl.KindChoices.ACTION:
            service = action or params.get("service")
            if not service:
                raise ValueError("Missing action name")
            body = {"entity_id": entity_id}
        else:
            service = params.get("service")
            value_field = params.get("value_field")
            if not service or not value_field:
                raise ValueError("Home Assistant control metadata is incomplete")
            if value is None:
                raise ValueError("Missing control value")
            body = {
                "entity_id": entity_id,
                value_field: value,
            }

        response = requests.post(
            f"{base_url}/api/services/{service_domain}/{service}",
            headers=headers,
            json=body,
            timeout=15,
        )
        response.raise_for_status()

    @classmethod
    def _execute_mijia_control(cls, account: Account, *, device: DeviceSnapshot, control: DeviceControl, value: Any) -> None:
        from mijiaAPI import mijiaDevice
        from providers.services import MijiaAuthService

        params = control.action_params or {}
        did = params.get("did")
        if not did:
            raw_payload = device.source_payload or {}
            did = raw_payload.get("did")
        if not did:
            raise ValueError("MiJia device identifier is missing")

        api = MijiaAuthService.get_authenticated_api(account=account)
        client = mijiaDevice(api, did=str(did))

        if control.source_type == DeviceControl.SourceTypeChoices.MIJIA_PROPERTY:
            if value is None:
                raise ValueError("Missing property value")
            client.set(control.key, value)
            return

        action_value = value
        if action_value == "":
            action_value = None
        client.run_action(control.key, value=action_value)

    @classmethod
    def _execute_midea_cloud_control(
        cls,
        account: Account,
        *,
        device: DeviceSnapshot,
        control: DeviceControl,
        action: str,
        value: Any,
    ) -> None:
        from providers.services import MideaCloudAuthService

        client = MideaCloudAuthService.get_client(account=account)
        params = control.action_params or {}
        device_id = params.get("device_id") or (device.source_payload or {}).get("device_id")
        if not device_id:
            device_id = device.external_id.removeprefix("midea_cloud:")
        if not device_id:
            raise ValueError("Midea device identifier is missing")

        merged_action_params = dict(params)
        actions = merged_action_params.get("actions") or []
        if control.kind == DeviceControl.KindChoices.TOGGLE:
            action_id = action or ("turn_on" if value in (True, 1, "on", "true") else "turn_off")
            for action_item in actions:
                if action_item.get("id") == action_id:
                    merged_action_params["control"] = cls._find_midea_cloud_action_payload(control, action_id)
                    break
        elif control.kind == DeviceControl.KindChoices.ENUM:
            selected_payload = cls._find_midea_cloud_option_payload(control, value)
            if selected_payload:
                merged_action_params["control"] = selected_payload
        elif control.kind == DeviceControl.KindChoices.ACTION:
            selected_payload = cls._find_midea_cloud_action_payload(control, value)
            if not selected_payload:
                selected_payload = cls._find_midea_cloud_option_payload(control, action or value or "press")
            if selected_payload:
                merged_action_params["control"] = selected_payload

        payload = {
            "key": control.key,
            "kind": control.kind,
            "source_type": control.source_type,
            "action_params": merged_action_params,
        }
        client.execute_control(device_id=device_id, control=payload, value=value)

    @classmethod
    def _execute_mbapi2020_control(
        cls,
        account: Account,
        *,
        device: DeviceSnapshot,
        control: DeviceControl,
        action: str,
        value: Any,
    ) -> None:
        from providers.services import MbApi2020AuthService

        client = MbApi2020AuthService.get_client(account=account)
        params = control.action_params or {}
        vehicle_id = params.get("vehicle_id") or (device.source_payload or {}).get("vin")
        if not vehicle_id:
            vehicle_id = device.external_id.removeprefix("mbapi2020:")
        if not vehicle_id:
            raise ValueError("Mercedes vehicle identifier is missing")

        command_name = action or params.get("command_name") or value
        if not command_name:
            raise ValueError("Mercedes command metadata is incomplete")

        payload = {
            "key": control.key,
            "kind": control.kind,
            "source_type": control.source_type,
            "action_params": {
                **params,
                "command_name": command_name,
            },
        }
        client.execute_control(vehicle_id=str(vehicle_id), control=payload, value=value)

    @classmethod
    def _execute_hisense_ha_control(
        cls,
        account: Account,
        *,
        device: DeviceSnapshot,
        control: DeviceControl,
        action: str,
        value: Any,
    ) -> None:
        from providers.services import HisenseHAAuthService

        client = HisenseHAAuthService.get_client(account=account)
        params = control.action_params or {}
        device_id = params.get("device_id") or (device.source_payload or {}).get("device_id")
        if not device_id:
            device_id = device.external_id.removeprefix("hisense_ha:")
        if not device_id:
            raise ValueError("Hisense device identifier is missing")

        effective_value = value
        if control.kind == DeviceControl.KindChoices.TOGGLE and value is None:
            effective_value = action in {"turn_on", "on", "true", "1"}
        elif control.kind == DeviceControl.KindChoices.ACTION and value in (None, ""):
            effective_value = action or "refresh"

        client.execute_control(
            device_id=str(device_id),
            control_key=control.key,
            action=action,
            value=effective_value,
        )

    @classmethod
    def _apply_optimistic_control_result(cls, control: DeviceControl, *, action: str, value: Any) -> None:
        next_value = value
        if control.kind == DeviceControl.KindChoices.TOGGLE:
            normalized_action = str(action or "").strip().lower()
            if normalized_action in {"turn_on", "on", "open", "start", "lock"}:
                next_value = "on"
            elif normalized_action in {"turn_off", "off", "close", "stop", "unlock"}:
                next_value = "off"
            elif value in (True, 1, "1", "on", "true"):
                next_value = "on"
            elif value in (False, 0, "0", "off", "false"):
                next_value = "off"

        if control.kind not in {
            DeviceControl.KindChoices.TOGGLE,
            DeviceControl.KindChoices.RANGE,
            DeviceControl.KindChoices.ENUM,
            DeviceControl.KindChoices.TEXT,
        }:
            return
        if next_value is None:
            return

        control.value = next_value
        control.save(update_fields=["value", "updated_at"])

    @classmethod
    def _merge_snapshots(cls, payloads: list[dict]) -> dict:
        merged = cls._build_empty_snapshot()
        source_names = []
        for payload in payloads:
            source = payload.get("source")
            if source:
                source_names.append(source)
            merged["rooms"].extend(payload.get("rooms", []))
            merged["devices"].extend(payload.get("devices", []))
            merged["anomalies"].extend(payload.get("anomalies", []))
            merged["rules"].extend(payload.get("rules", []))

        merged["source"] = "+".join(source_names) if source_names else "none"
        return merged

    @staticmethod
    def _map_model_to_category(model: str) -> str:
        normalized = (model or "").lower()
        if "light" in normalized:
            return "灯光"
        if "sensor" in normalized:
            return "传感器"
        if "airpurifier" in normalized or "purifier" in normalized:
            return "空气护理"
        if "acpartner" in normalized or "aircondition" in normalized or "climate" in normalized:
            return "空调"
        if "fountain" in normalized or "feeder" in normalized:
            return "宠物照护"
        if "switch" in normalized or "plug" in normalized:
            return "开关"
        if "curtain" in normalized:
            return "窗帘"
        if "camera" in normalized:
            return "监控"
        if "fridge" in normalized or "refrigerator" in normalized:
            return "冰箱"
        return "其他设备"

    @staticmethod
    def _make_room_id(provider: str, raw_value: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(raw_value or "").strip()).strip("-").lower()
        if normalized:
            return f"{provider}:{normalized}"

        digest = hashlib.md5(str(raw_value or provider).encode("utf-8")).hexdigest()[:8]
        return f"{provider}:{digest}"

    @staticmethod
    def _map_home_assistant_domain_to_category(domain: str) -> str:
        mapping = {
            "light": "灯光",
            "switch": "开关",
            "fan": "风扇",
            "climate": "空调",
            "sensor": "传感器",
            "binary_sensor": "传感器",
            "cover": "窗帘",
            "lock": "门锁",
            "camera": "监控",
            "media_player": "媒体设备",
            "humidifier": "空气护理",
            "vacuum": "清洁设备",
            "number": "数值控制",
            "select": "模式控制",
        }
        return mapping.get(domain, "其他设备")

    @staticmethod
    def _map_home_assistant_status(state: str) -> str:
        normalized = (state or "").lower()
        if normalized in {"unavailable", "unknown", "offline"}:
            return "offline"
        if normalized in {"on", "open", "unlocking", "locking", "jammed", "problem", "triggered"}:
            return "attention"
        return "online"

    @classmethod
    def _summarize_home_assistant_device(cls, entities: list[dict]) -> str:
        parts: list[str] = []
        for entity in entities[:4]:
            attributes = entity.get("attributes") or {}
            friendly_name = str(attributes.get("friendly_name") or entity.get("entity_id"))
            state = str(entity.get("state", ""))
            unit = attributes.get("unit_of_measurement") or ""
            short_name = friendly_name[:14]
            parts.append(f"{short_name}: {state}{unit}")
        return " | ".join(parts)

    @staticmethod
    def _parse_numeric_value(value: Any) -> Any:
        try:
            parsed = float(value)
            return int(parsed) if parsed.is_integer() else parsed
        except (TypeError, ValueError):
            return value

    @staticmethod
    def _pick_home_assistant_primary_entity(entities: list[dict]) -> dict:
        for preferred_domain in ("switch", "light", "climate", "fan", "humidifier", "select", "number"):
            for entity in entities:
                entity_id = str(entity.get("entity_id", ""))
                if entity_id.startswith(f"{preferred_domain}."):
                    return entity
        return entities[0]

    @classmethod
    def _infer_home_assistant_device_key(
        cls,
        *,
        entity_id: str,
        friendly_name: str,
        attributes: dict,
        registry_entity: dict | None = None,
        registry_device: dict | None = None,
    ) -> str:
        registry_entity = registry_entity or {}
        registry_device = registry_device or {}
        registry_device_id = registry_entity.get("device_id") or registry_device.get("id")
        if registry_device_id:
            return f"device_{cls._slugify(str(registry_device_id))}"

        explicit = attributes.get("device_id") or attributes.get("device_name")
        if explicit:
            return cls._slugify(str(explicit))

        object_id = entity_id.split(".", 1)[1] if "." in entity_id else entity_id
        tokens = [token for token in object_id.split("_") if token]
        if len(tokens) >= 3:
            return "_".join(tokens[: max(2, len(tokens) - 1)])
        if len(tokens) >= 2:
            return "_".join(tokens[:-1])

        normalized_name = cls._slugify(friendly_name)
        return normalized_name or cls._slugify(object_id)

    @classmethod
    def _infer_home_assistant_device_name(
        cls,
        *,
        device_key: str,
        friendly_name: str,
        registry_device: dict | None = None,
    ) -> str:
        registry_device = registry_device or {}
        registry_name = registry_device.get("name_by_user") or registry_device.get("name")
        if registry_name and not cls._looks_like_device_identifier(registry_name):
            return str(registry_name)
        if not cls._looks_like_device_identifier(friendly_name):
            if " " in friendly_name:
                return friendly_name.split(" ", 1)[0]
            if "·" in friendly_name:
                return friendly_name.split("·", 1)[0]
            return friendly_name
        return cls._titleize_slug(device_key)

    @classmethod
    def _infer_mijia_device_name(cls, *, dev: dict, did: str, model: str) -> str:
        raw_name = str(dev.get("name") or "").strip()
        if raw_name and not cls._looks_like_device_identifier(raw_name):
            return raw_name

        model_name = str(model or "").strip()
        if model_name:
            category = cls._map_model_to_category(model_name)
            if category and category != "其他设备":
                return category
            return cls._titleize_slug(model_name)

        return f"米家设备 {did[-4:]}" if did else "米家设备"

    @classmethod
    def _extract_home_assistant_group_label(
        cls,
        friendly_name: str,
        *,
        entity_id: str = "",
        attributes: dict | None = None,
        registry_entity: dict | None = None,
    ) -> str:
        attributes = attributes or {}
        registry_entity = registry_entity or {}
        haystacks = [
            friendly_name.lower(),
            entity_id.lower(),
            str(registry_entity.get("original_name") or "").lower(),
            str(registry_entity.get("name") or "").lower(),
            str(attributes.get("device_class") or "").lower(),
        ]

        keyword_groups = [
            ("整机", ("power", "main", "master", "total", "overall", "整机", "总电源", "运行状态", "status")),
            ("冷藏区", ("冷藏", "refrigerator", "fridge", "cool")),
            ("冷冻区", ("冷冻", "freezer", "freeze")),
            ("变温区", ("变温", "variable", "middle", "flex")),
            ("门体", ("door", "门")),
            ("照明", ("light", "lamp", "led", "照明", "灯")),
            ("模式", ("mode", "preset", "program", "模式")),
            ("系统", ("diagnostic", "config", "battery", "signal", "system", "firmware")),
        ]
        for label, keywords in keyword_groups:
            if any(any(keyword in haystack for keyword in keywords) for haystack in haystacks):
                return label

        entity_category = str(registry_entity.get("entity_category") or "").lower()
        if entity_category == "diagnostic":
            return "系统"
        if entity_category == "config":
            return "设置"

        object_id = entity_id.split(".", 1)[1] if "." in entity_id else entity_id
        tokens = [token for token in re.split(r"[_\-\s]+", object_id) if token]
        stop_words = {"sensor", "switch", "binary", "number", "select", "button", "input", "temperature", "humidity"}
        candidates = [token for token in tokens if token not in stop_words]
        if candidates:
            first = candidates[0]
            if first in {"fridge", "refrigerator", "freezer", "cool"}:
                return "冷藏区" if first != "freezer" else "冷冻区"
            return cls._titleize_slug(first)

        for separator in (" ", "·", "-", "_"):
            if separator in friendly_name:
                return friendly_name.split(separator, 1)[1].strip()
        return "通用"

    @staticmethod
    def _build_ha_toggle_actions(domain: str) -> list[dict]:
        if domain == "lock":
            return [
                {"id": "lock", "label": "上锁"},
                {"id": "unlock", "label": "解锁"},
            ]
        return [
            {"id": "turn_on", "label": "开启"},
            {"id": "turn_off", "label": "关闭"},
            {"id": "toggle", "label": "切换"},
        ]

    @staticmethod
    def _infer_mijia_control_kind(prop: dict) -> str:
        rw = str(prop.get("rw") or "")
        if "w" not in rw:
            return DeviceControl.KindChoices.SENSOR
        value_list = prop.get("value-list") or []
        if value_list:
            return DeviceControl.KindChoices.ENUM
        value_type = prop.get("type")
        if value_type == "bool":
            return DeviceControl.KindChoices.TOGGLE
        if value_type in {"int", "uint", "float"}:
            return DeviceControl.KindChoices.RANGE
        if value_type == "string":
            return DeviceControl.KindChoices.TEXT
        return DeviceControl.KindChoices.SENSOR

    @staticmethod
    def _normalize_mijia_options(value_list: list[dict] | None) -> list[dict]:
        if not value_list:
            return []
        options = []
        for item in value_list:
            label = item.get("description") or item.get("desc_zh_cn") or item.get("name") or str(item.get("value"))
            options.append({"label": str(label), "value": item.get("value")})
        return options

    @staticmethod
    def _pick_mijia_label(payload: dict, *, fallback: str) -> str:
        raw = str(payload.get("description") or payload.get("desc_zh_cn") or payload.get("name") or fallback)
        if " / " in raw:
            zh, _, en = raw.partition(" / ")
            return zh.strip() or en.strip() or fallback
        return raw

    @staticmethod
    def _extract_mijia_group_label(name: str) -> str:
        if "-" in name:
            return name.split("-", 1)[0].replace("_", " ").strip()
        return ""

    @staticmethod
    def _summarize_mijia_telemetry(controls: list[dict], *, is_online: bool) -> str:
        if not is_online:
            return "离线"
        interesting = []
        for control in controls:
            if control["kind"] == DeviceControl.KindChoices.ACTION:
                continue
            value = control.get("value")
            if value in (None, "", [], {}):
                continue
            suffix = control.get("unit", "")
            interesting.append(f"{control['label']}: {value}{suffix}")
            if len(interesting) >= 3:
                break
        return " | ".join(interesting) if interesting else "已连接"

    @staticmethod
    def _infer_midea_cloud_control_kind(control: dict) -> str:
        kind = str(control.get("kind") or control.get("type") or "").strip().lower()
        if kind in {"toggle", "switch", "bool"}:
            return DeviceControl.KindChoices.TOGGLE
        if kind in {"range", "number", "slider"}:
            return DeviceControl.KindChoices.RANGE
        if kind in {"enum", "select", "mode"}:
            return DeviceControl.KindChoices.ENUM
        if kind in {"action", "button"}:
            return DeviceControl.KindChoices.ACTION
        if kind in {"text", "string"}:
            return DeviceControl.KindChoices.TEXT
        return DeviceControl.KindChoices.SENSOR

    @classmethod
    def _build_mbapi2020_controls(cls, raw_vehicle: dict) -> list[dict]:
        controls: list[dict] = []
        vin = str(raw_vehicle.get("vin") or raw_vehicle.get("id") or "").strip()
        status_payload = raw_vehicle.get("status_payload") or {}
        command_capabilities = raw_vehicle.get("command_capabilities") or []
        pin_available = bool(raw_vehicle.get("pin_available"))
        available_commands = {
            str(item.get("commandName") or "").strip().upper(): item
            for item in command_capabilities
            if isinstance(item, dict) and item.get("isAvailable")
        }
        sort_order = 10

        for group in cls.mbapi2020_command_groups:
            actions = []
            for command in group["commands"]:
                command_name = str(command["name"]).upper()
                if command_name not in available_commands:
                    continue
                if command.get("requires_pin") and not pin_available:
                    continue
                actions.append({"id": command_name, "label": command["label"]})

            if not actions:
                continue

            controls.append(
                {
                    "id": f"mbapi2020:{vin}:{group['key']}",
                    "parent_id": f"mbapi2020:{vin}",
                    "source_type": DeviceControl.SourceTypeChoices.MBAPI2020_ACTION,
                    "kind": DeviceControl.KindChoices.ACTION,
                    "key": group["key"],
                    "label": group["label"],
                    "group_label": group["group_label"],
                    "writable": True,
                    "value": (
                        cls._format_mbapi2020_status_value("doorlockstatusvehicle", status_payload.get("doorlockstatusvehicle"))
                        if group["key"] == "door_lock"
                        else ""
                    ),
                    "unit": "",
                    "options": [],
                    "range_spec": {},
                    "action_params": {
                        "vehicle_id": vin,
                        "actions": actions,
                    },
                    "source_payload": available_commands,
                    "sort_order": sort_order,
                }
            )
            sort_order += 10

        preferred_sensors = [
            ("doorlockstatusvehicle", "车门锁状态", ""),
            ("decklidstatus", "后备箱状态", ""),
            ("chargingstatusdisplay", "充电状态", ""),
            ("electricrange", "续航里程", ""),
            ("rangeelectric", "续航里程", ""),
            ("odometer", "总里程", ""),
            ("tanklevelpercent", "油量", "%"),
            ("engineHoodStatus", "引擎盖", ""),
            ("doorlockstatusdecklid", "后备箱锁", ""),
            ("doorStatusOverall", "车门总状态", ""),
            ("sunroofstatus", "天窗状态", ""),
            ("parkbrakestatus", "驻车制动", ""),
            ("warningbrakefluid", "制动液状态", ""),
        ]
        used_keys: set[str] = set()
        for key, label, unit in preferred_sensors:
            value = cls._format_mbapi2020_status_value(key, status_payload.get(key))
            if value in (None, "", {}, []):
                continue
            controls.append(
                {
                    "id": f"mbapi2020:{vin}:status:{key}",
                    "parent_id": f"mbapi2020:{vin}",
                    "source_type": DeviceControl.SourceTypeChoices.MBAPI2020_PROPERTY,
                    "kind": DeviceControl.KindChoices.SENSOR,
                    "key": key,
                    "label": label,
                    "group_label": "状态",
                    "writable": False,
                    "value": value,
                    "unit": unit,
                    "options": [],
                    "range_spec": {},
                    "action_params": {},
                    "source_payload": {"key": key, "value": value},
                    "sort_order": sort_order,
                }
            )
            sort_order += 10
            used_keys.add(key)

        for key, value in status_payload.items():
            value = cls._format_mbapi2020_status_value(key, value)
            if key in used_keys or value in (None, "", {}, []) or isinstance(value, (list, dict)):
                continue
            controls.append(
                {
                    "id": f"mbapi2020:{vin}:status:{key}",
                    "parent_id": f"mbapi2020:{vin}",
                    "source_type": DeviceControl.SourceTypeChoices.MBAPI2020_PROPERTY,
                    "kind": DeviceControl.KindChoices.SENSOR,
                    "key": key,
                    "label": cls._format_mbapi2020_status_label(key),
                    "group_label": "状态",
                    "writable": False,
                    "value": value,
                    "unit": "",
                    "options": [],
                    "range_spec": {},
                    "action_params": {},
                    "source_payload": {"key": key, "value": value},
                    "sort_order": sort_order,
                }
            )
            sort_order += 10
            if sort_order > 120:
                break

        return controls

    @classmethod
    def _format_mbapi2020_status_value(cls, key: str, value: Any) -> Any:
        if value in (None, "", {}, []):
            return value
        normalized_key = str(key or "").strip().lower()
        mapped_values = cls.mbapi2020_status_value_maps.get(normalized_key)
        if not mapped_values:
            return value
        normalized_value = str(value).strip().lower()
        return mapped_values.get(normalized_value, value)

    @classmethod
    def _format_mbapi2020_status_label(cls, key: str) -> str:
        normalized_key = str(key or "").strip().lower()
        return cls.mbapi2020_status_label_maps.get(normalized_key, key)

    @staticmethod
    def _map_mbapi2020_status(raw_vehicle: dict) -> str:
        status_payload = raw_vehicle.get("status_payload") or {}
        lock_status = str(status_payload.get("doorlockstatusvehicle") or "").lower()
        if "invalid" in lock_status or "error" in lock_status:
            return DeviceSnapshot.StatusChoices.ATTENTION
        if raw_vehicle.get("vin"):
            return DeviceSnapshot.StatusChoices.ONLINE
        return DeviceSnapshot.StatusChoices.OFFLINE

    @classmethod
    def _summarize_mbapi2020_vehicle(cls, raw_vehicle: dict, controls: list[dict]) -> str:
        status_payload = raw_vehicle.get("status_payload") or {}
        parts: list[str] = []
        if raw_vehicle.get("license_plate"):
            parts.append(f"车牌 {raw_vehicle['license_plate']}")
        lock_status = cls._format_mbapi2020_status_value("doorlockstatusvehicle", status_payload.get("doorlockstatusvehicle"))
        if lock_status not in (None, "", {}, []):
            parts.append(f"车锁 {lock_status}")
        range_value = status_payload.get("electricrange") or status_payload.get("rangeelectric")
        if range_value not in (None, "", {}, []):
            parts.append(f"续航 {range_value}")
        if status_payload.get("odometer") not in (None, "", {}, []):
            parts.append(f"里程 {status_payload['odometer']}")
        if len(parts) < 2:
            action_count = len([item for item in controls if item["kind"] == DeviceControl.KindChoices.ACTION])
            parts.append(f"{action_count} 个可用动作")
        return " | ".join(parts[:3])

    @staticmethod
    def _map_hisense_ha_status(status_payload: dict) -> str:
        if not isinstance(status_payload, dict):
            return DeviceSnapshot.StatusChoices.OFFLINE
        indoor_temperature = status_payload.get("indoor_temperature")
        if status_payload.get("power_on") is True:
            return DeviceSnapshot.StatusChoices.ONLINE
        if indoor_temperature not in (None, "", {}, []):
            return DeviceSnapshot.StatusChoices.ATTENTION
        return DeviceSnapshot.StatusChoices.OFFLINE

    @staticmethod
    def _summarize_hisense_ha_device(status_payload: dict, controls: list[dict]) -> str:
        if not isinstance(status_payload, dict):
            return "离线"
        parts: list[str] = []
        power = "已开机" if status_payload.get("power_on") else "已关机"
        parts.append(power)
        target_temperature = status_payload.get("desired_temperature")
        if target_temperature not in (None, "", {}, []):
            parts.append(f"设定 {target_temperature}°C")
        indoor_temperature = status_payload.get("indoor_temperature")
        if indoor_temperature not in (None, "", {}, []):
            parts.append(f"室温 {indoor_temperature}°C")
        if len(parts) < 3:
            hvac_mode = status_payload.get("hvac_mode")
            if hvac_mode:
                parts.append(f"模式 {hvac_mode}")
        if len(parts) < 3:
            writable_count = len([item for item in controls if item.get("writable")])
            parts.append(f"{writable_count} 个可控项")
        return " | ".join(parts[:3])

    @staticmethod
    def _map_midea_cloud_status(raw_device: dict) -> str:
        for key in ("status", "online_status", "device_status", "state"):
            value = str(raw_device.get(key) or "").strip().lower()
            if not value:
                continue
            if value in {"offline", "disconnected", "unavailable", "0"}:
                return DeviceSnapshot.StatusChoices.OFFLINE
            if value in {"warning", "attention", "alarm", "fault"}:
                return DeviceSnapshot.StatusChoices.ATTENTION
            return DeviceSnapshot.StatusChoices.ONLINE
        return DeviceSnapshot.StatusChoices.ONLINE

    @staticmethod
    def _summarize_midea_cloud_device(raw_device: dict, controls: list[dict]) -> str:
        telemetry = str(raw_device.get("telemetry") or "").strip()
        if telemetry:
            return telemetry

        interesting = []
        for control in controls:
            if control["kind"] == DeviceControl.KindChoices.ACTION:
                continue
            value = control.get("value")
            if value in (None, "", [], {}):
                continue
            interesting.append(f"{control['label']}: {value}{control.get('unit', '')}")
            if len(interesting) >= 3:
                break
        return " | ".join(interesting) if interesting else "已连接"

    @staticmethod
    def _find_midea_cloud_option_payload(control: DeviceControl, value: Any) -> dict | None:
        for option in control.options or []:
            if not isinstance(option, dict):
                continue
            if option.get("value") == value:
                payload = option.get("control")
                return payload if isinstance(payload, dict) else None
        return None

    @staticmethod
    def _find_midea_cloud_action_payload(control: DeviceControl, action_id: Any) -> dict | None:
        source_payload = control.source_payload or {}
        mapping = source_payload.get("mapping") if isinstance(source_payload, dict) else {}
        actions = mapping.get("actions") if isinstance(mapping, dict) else {}
        payload = actions.get(action_id) if isinstance(actions, dict) else None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _slugify(value: str) -> str:
        return re.sub(r"[^a-zA-Z0-9]+", "_", str(value or "").strip()).strip("_").lower()

    @staticmethod
    def _titleize_slug(value: str) -> str:
        return str(value or "").replace("_", " ").replace("-", " ").strip().title() or "Home Assistant Device"

    @staticmethod
    def _looks_like_device_identifier(value: Any) -> bool:
        normalized = str(value or "").strip()
        if not normalized:
            return True
        compact = re.sub(r"[\s\-_:]+", "", normalized)
        if compact.isdigit() and len(compact) >= 6:
            return True
        return False

    @staticmethod
    def _build_empty_snapshot() -> dict:
        return {
            "source": "none",
            "rooms": [],
            "devices": [],
            "anomalies": [],
            "rules": [],
        }
