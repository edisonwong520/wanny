from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from typing import TYPE_CHECKING, Any

import requests
from django.db import transaction
from django.utils import timezone

from providers.models import PlatformAuth
from utils.logger import logger

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
    state_key = "default"
    default_sync_interval_seconds = 300
    device_provider_names = ("mijia", "home_assistant")
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
        logger.info(f"[Device Sync] Refresh queued for account_id={state.account_id}, waiting for worker to process")

    @classmethod
    def get_dashboard(cls, account: Account) -> dict:
        state = cls._get_state(account)
        has_snapshot = cls._has_snapshot(account)

        if not has_snapshot and not state.refresh_requested_at:
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
        logger.info(f"[Device Sync] refresh() called for account_id={account.id} email={account.email} trigger={trigger}")
        provider_payloads: list[dict] = []
        from providers.services import HomeAssistantAuthService, MijiaAuthService

        try:
            mijia_auth = MijiaAuthService.get_auth_record(account=account, active_only=True)
            logger.debug(f"[Device Sync] Mijia auth check for account_id={account.id}: found={mijia_auth is not None}")
            if mijia_auth:
                logger.info(f"[Device Sync] Building Mijia snapshot for account_id={account.id}")
                mijia_payload = cls._build_mijia_snapshot(account)
                logger.info(f"[Device Sync] Mijia snapshot built for account_id={account.id}: devices={len(mijia_payload.get('devices', []))}")
                provider_payloads.append(mijia_payload)
        except Exception as error:
            logger.error(f"[Device Sync] Failed to check Mijia auth state for user {account.email}: {error}")

        try:
            ha_auth = HomeAssistantAuthService.get_auth_record(account=account, active_only=True)
            logger.debug(f"[Device Sync] HomeAssistant auth check for account_id={account.id}: found={ha_auth is not None}")
            if ha_auth:
                logger.info(f"[Device Sync] Building HomeAssistant snapshot for account_id={account.id}")
                ha_payload = cls._build_home_assistant_snapshot(account)
                logger.info(f"[Device Sync] HomeAssistant snapshot built for account_id={account.id}: devices={len(ha_payload.get('devices', []))}")
                provider_payloads.append(ha_payload)
        except Exception as error:
            logger.error(f"[Device Sync] Failed to check Home Assistant auth state for user {account.email}: {error}")

        logger.info(f"[Device Sync] Merging {len(provider_payloads)} provider payloads for account_id={account.id}")
        payload = cls._merge_snapshots(provider_payloads) if provider_payloads else cls._build_empty_snapshot()
        logger.info(f"[Device Sync] Final payload for account_id={account.id}: rooms={len(payload['rooms'])} devices={len(payload['devices'])}")

        with transaction.atomic():
            state = cls._get_state(account)

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
                    sort_order=room_data["sort_order"],
                )
                room_map[room.slug] = room

            device_map: dict[str, DeviceSnapshot] = {}
            for device_data in payload["devices"]:
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
                    sort_order=device_data["sort_order"],
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

        return cls.get_dashboard(account)

    @classmethod
    def request_refresh(cls, account: Account, *, trigger: str = "manual") -> dict:
        logger.info(f"[Device Sync] request_refresh called: account_id={account.id} email={account.email} trigger={trigger}")
        state = cls._get_state(account)
        cls._queue_refresh(state, trigger=trigger)
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
        else:
            raise ValueError(f"Unsupported control source: {control.source_type}")

        return cls.refresh(account, trigger="control")

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

        logger.debug(f"[Device Sync] _build_mijia_snapshot start for account_id={account.id}")
        try:
            logger.debug(f"[Device Sync] Getting Mijia authenticated API for account_id={account.id}")
            api = MijiaAuthService.get_authenticated_api(account=account)
            logger.debug(f"[Device Sync] Fetching devices list from Mijia for account_id={account.id}")
            devices = api.get_devices_list()
            logger.info(f"[Device Sync] Mijia devices list fetched for account_id={account.id}: count={len(devices)}")
            homes = api.get_homes_list()
            logger.debug(f"[Device Sync] Mijia homes list fetched for account_id={account.id}: count={len(homes)}")
        except Exception as error:
            logger.error(f"[Device Sync] Failed to fetch real MiJia data, falling back to empty: {error}")
            return cls._build_empty_snapshot()

        home_map = {str(h.get("id")): h.get("name") or "默认家庭" for h in homes}
        room_index: dict[str, dict] = {}
        devices_data: list[dict] = []

        for index, dev in enumerate(devices, start=1):
            did = str(dev.get("did", "")).strip()
            if not did:
                continue

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

            try:
                spec = get_device_info(model)
            except Exception as error:
                logger.warning(f"[Device Sync] Failed to load MiJia spec for {model}: {error}")
                spec = {}

            if spec:
                try:
                    device_client = mijiaDevice(api, did=did)
                except Exception as error:
                    logger.warning(f"[Device Sync] Failed to create MiJia device client for {did}: {error}")

            for control in cls._build_mijia_controls(dev=dev, spec=spec, device_client=device_client):
                controls.append(control)
                if control["kind"] != DeviceControl.KindChoices.SENSOR and control["key"] not in control_capabilities:
                    control_capabilities.append(control["key"])

            is_online = bool(dev.get("isOnline", False))
            devices_data.append(
                {
                    "id": f"mijia:{did}",
                    "room_id": room_id,
                    "name": dev.get("name") or did,
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

        return {
            "source": "mijia",
            "rooms": list(room_index.values()),
            "devices": devices_data,
            "anomalies": [],
            "rules": [],
        }

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
        if registry_name:
            return str(registry_name)
        if " " in friendly_name:
            return friendly_name.split(" ", 1)[0]
        if "·" in friendly_name:
            return friendly_name.split("·", 1)[0]
        return cls._titleize_slug(device_key)

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
    def _slugify(value: str) -> str:
        return re.sub(r"[^a-zA-Z0-9]+", "_", str(value or "").strip()).strip("_").lower()

    @staticmethod
    def _titleize_slug(value: str) -> str:
        return str(value or "").replace("_", " ").replace("-", " ").strip().title() or "Home Assistant Device"

    @staticmethod
    def _build_empty_snapshot() -> dict:
        return {
            "source": "none",
            "rooms": [],
            "devices": [],
            "anomalies": [],
            "rules": [],
        }
