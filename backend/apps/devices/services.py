from __future__ import annotations
import hashlib
import re
from typing import TYPE_CHECKING

from providers.models import PlatformAuth

if TYPE_CHECKING:
    from accounts.models import Account

from collections import Counter
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from utils.logger import logger
from .models import (
    DeviceAnomaly,
    DeviceAutomationRule,
    DeviceDashboardState,
    DeviceRoom,
    DeviceSnapshot,
)


class DeviceDashboardService:
    state_key = "default"
    default_sync_interval_seconds = 300
    device_provider_names = ("mijia", "home_assistant")

    @classmethod
    def _get_state(cls, account: Account) -> DeviceDashboardState:
        state, _ = DeviceDashboardState.objects.get_or_create(account=account, key=cls.state_key)
        return state

    @classmethod
    def _has_snapshot(cls, account: Account) -> bool:
        return bool(cls._get_state(account).refreshed_at)

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
        state.requested_trigger = trigger
        if not state.refresh_requested_at:
            state.refresh_requested_at = timezone.now()
        state.last_error = ""
        state.save(update_fields=["requested_trigger", "refresh_requested_at", "last_error", "updated_at"])

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
        devices = list(DeviceSnapshot.objects.filter(account=account).select_related("room").all())
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
        """
        彻底清理指定账户下所有的房间、设备快照、异常记录和自动化规则。
        通常在断开平台（如米家）授权时调用，以确保隐私与数据一致性。
        """
        with transaction.atomic():
            # 1. 删除所有关联业务数据
            DeviceAnomaly.objects.filter(account=account).delete()
            DeviceAutomationRule.objects.filter(account=account).delete()
            DeviceSnapshot.objects.filter(account=account).delete()
            DeviceRoom.objects.filter(account=account).delete()

            # 2. 重置总览状态
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
        provider_payloads: list[dict] = []
        from providers.services import HomeAssistantAuthService, MijiaAuthService

        try:
            if MijiaAuthService.get_auth_record(account=account, active_only=True):
                provider_payloads.append(cls._build_mijia_snapshot(account))
        except Exception as error:
            logger.error(f"[Device Sync] Failed to check Mijia auth state for user {account.email}: {error}")

        try:
            if HomeAssistantAuthService.get_auth_record(account=account, active_only=True):
                provider_payloads.append(cls._build_home_assistant_snapshot(account))
        except Exception as error:
            logger.error(f"[Device Sync] Failed to check Home Assistant auth state for user {account.email}: {error}")

        if provider_payloads:
            payload = cls._merge_snapshots(provider_payloads)
        else:
            payload = cls._build_demo_snapshot()

        with transaction.atomic():
            state = cls._get_state(account)

            DeviceAnomaly.objects.filter(account=account).delete()
            DeviceAutomationRule.objects.filter(account=account).delete()
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
        state = cls._get_state(account)
        cls._queue_refresh(state, trigger=trigger)
        return cls.get_dashboard(account)

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
            cls.refresh(account, trigger=trigger)
            return
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

        if not state.refresh_requested_at and not is_stale:
            return False

        trigger = state.requested_trigger or ("worker_bootstrap" if not has_snapshot else "worker")
        try:
            cls.refresh(account, trigger=trigger)
            return True
        except Exception as error:
            state = cls._get_state(account)
            if not state.refresh_requested_at:
                state.refresh_requested_at = now
            if not state.requested_trigger:
                state.requested_trigger = trigger
            state.last_error = str(error)
            state.save(
                update_fields=[
                    "requested_trigger",
                    "refresh_requested_at",
                    "last_error",
                    "updated_at",
                ]
            )
            raise

    @classmethod
    def _build_mijia_snapshot(cls, account: Account) -> dict:
        from providers.services import MijiaAuthService

        try:
            api = MijiaAuthService.get_authenticated_api(account=account)
            devices = api.get_devices_list()
            homes = api.get_homes_list()
        except Exception as e:
            logger.error(f"[Device Sync] Failed to fetch real MiJia data, falling back to demo: {e}")
            return cls._build_demo_snapshot()

        home_map = {str(h["id"]): h["name"] for h in homes}

        rooms_data = []
        for h_id, h_name in home_map.items():
            rooms_data.append(
                {
                    "id": f"mijia:{h_id}",
                    "name": h_name,
                    "climate": "已连接",
                    "summary": f"来自米家家庭: {h_name}",
                    "sort_order": 10,
                }
            )

        # Ensure at least one room exists if devices have no home_id or if homes list is empty
        if not rooms_data:
            rooms_data.append(
                {
                    "id": "mijia:default",
                    "name": "默认家庭",
                    "climate": "未知",
                    "summary": "未检测到明确的米家家庭分组",
                    "sort_order": 10,
                }
            )

        devices_data = []
        for dev in devices:
            is_online = dev.get("isOnline", False)
            raw_home_id = str(dev.get("home_id", "default"))
            if raw_home_id not in home_map and raw_home_id != "default":
                raw_home_id = "default"

            devices_data.append(
                {
                    "id": f"mijia:{dev['did']}",
                    "room_id": f"mijia:{raw_home_id}",
                    "name": dev["name"],
                    "category": cls._map_model_to_category(dev["model"]),
                    "status": "online" if is_online else "offline",
                    "telemetry": "已连接" if is_online else "离线",
                    "note": f"DID: {dev['did']} | IP: {dev.get('localip', 'N/A')} | 模型: {dev.get('model', 'unknown')}",
                    "capabilities": [],
                    "last_seen": timezone.now(),
                    "sort_order": 10,
                    "source_payload": dev,
                }
            )

        return {
            "source": "mijia",
            "rooms": rooms_data,
            "devices": devices_data,
            "anomalies": [],
            "rules": [],
        }

    @classmethod
    def _build_home_assistant_snapshot(cls, account: Account) -> dict:
        from providers.services import HomeAssistantAuthService

        config, states = HomeAssistantAuthService.get_states(account=account)
        default_room_name = config.get("location_name") or "Home Assistant"
        room_bucket_id = cls._make_room_id("home_assistant", "default")
        room_map = {
            room_bucket_id: {
                "id": room_bucket_id,
                "name": default_room_name,
                "climate": config.get("time_zone", ""),
                "summary": f"来自 Home Assistant 实例: {default_room_name}",
                "sort_order": 10,
            }
        }

        devices_data = []
        for index, entity in enumerate(states, start=1):
            entity_id = str(entity.get("entity_id", "")).strip()
            if not entity_id:
                continue

            domain = entity_id.split(".", 1)[0]
            if domain not in {
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
            }:
                continue

            attributes = entity.get("attributes") or {}
            room_name = (
                attributes.get("room")
                or attributes.get("area_name")
                or attributes.get("floor_name")
                or default_room_name
            )
            room_id = cls._make_room_id("home_assistant", room_name)
            if room_id not in room_map:
                room_map[room_id] = {
                    "id": room_id,
                    "name": str(room_name),
                    "climate": "",
                    "summary": f"来自 Home Assistant 分组: {room_name}",
                    "sort_order": 10 + len(room_map) * 10,
                }

            state = str(entity.get("state", "")).strip()
            devices_data.append(
                {
                    "id": f"home_assistant:{entity_id}",
                    "room_id": room_id,
                    "name": attributes.get("friendly_name") or entity_id,
                    "category": cls._map_home_assistant_domain_to_category(domain),
                    "status": cls._map_home_assistant_status(state),
                    "telemetry": cls._describe_home_assistant_telemetry(state, attributes),
                    "note": f"Entity: {entity_id} | Domain: {domain}",
                    "capabilities": cls._extract_home_assistant_capabilities(domain, attributes),
                    "last_seen": timezone.now(),
                    "sort_order": index * 10,
                    "source_payload": entity,
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
        model = (model or "").lower()
        if "light" in model:
            return "灯光"
        if "sensor" in model:
            return "传感器"
        if "airpurifier" in model or "purifier" in model:
            return "空气护理"
        if "acpartner" in model or "aircondition" in model or "climate" in model:
            return "空调"
        if "fountain" in model or "feeder" in model:
            return "宠物照护"
        if "switch" in model or "plug" in model:
            return "开关"
        if "curtain" in model:
            return "窗帘"
        if "camera" in model:
            return "监控"
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
        }
        return mapping.get(domain, "其他设备")

    @staticmethod
    def _map_home_assistant_status(state: str) -> str:
        normalized = (state or "").lower()
        if normalized in {"unavailable", "unknown", "offline"}:
            return "offline"
        if normalized in {"on", "open", "unlocking", "locking", "jammed", "problem"}:
            return "attention"
        return "online"

    @staticmethod
    def _describe_home_assistant_telemetry(state: str, attributes: dict) -> str:
        candidates = [
            attributes.get("current_temperature"),
            attributes.get("temperature"),
            attributes.get("humidity"),
            attributes.get("power"),
            attributes.get("brightness"),
        ]
        details = [str(item) for item in candidates if item not in (None, "", [])]
        return " / ".join([state] + details[:2]) if details else state

    @staticmethod
    def _extract_home_assistant_capabilities(domain: str, attributes: dict) -> list[str]:
        capabilities = [domain]
        for key in ("supported_color_modes", "hvac_modes", "preset_modes", "effect_list"):
            value = attributes.get(key)
            if isinstance(value, list) and value:
                capabilities.extend(str(item) for item in value[:4])
        return capabilities

    @staticmethod
    def _build_empty_snapshot() -> dict:
        return {
            "source": "none",
            "rooms": [],
            "devices": [],
            "anomalies": [],
            "rules": [],
        }

    @staticmethod
    def _build_demo_snapshot() -> dict:
        now = timezone.now()

        return {
            "source": "demo-cache",
            "rooms": [
                {
                    "id": "living",
                    "name": "客厅",
                    "climate": "26°C / 58% RH",
                    "summary": "主要观察照明、门口传感器和离家状态是否一致。",
                    "sort_order": 10,
                },
                {
                    "id": "bedroom",
                    "name": "主卧",
                    "climate": "24°C / 自动",
                    "summary": "主卧设备整体稳定，适合作为逐步自动化的样板房间。",
                    "sort_order": 20,
                },
                {
                    "id": "studio",
                    "name": "书房",
                    "climate": "AQI 82 / 稍差",
                    "summary": "空气质量和净化器策略是书房当前的重点。",
                    "sort_order": 30,
                },
                {
                    "id": "pet",
                    "name": "宠物角",
                    "climate": "饮水余量 18%",
                    "summary": "宠物相关设备保持保守策略，优先保证安全。",
                    "sort_order": 40,
                },
            ],
            "devices": [
                {
                    "id": "living-light",
                    "room_id": "living",
                    "name": "客厅灯",
                    "category": "灯光",
                    "status": "attention",
                    "telemetry": "已开 / 68% 亮度",
                    "note": "离家模式下仍保持开启，和预期策略不一致。",
                    "capabilities": ["亮度控制", "场景联动"],
                    "last_seen": now - timedelta(minutes=3),
                    "sort_order": 10,
                },
                {
                    "id": "entry-sensor",
                    "room_id": "living",
                    "name": "入户传感器",
                    "category": "传感器",
                    "status": "online",
                    "telemetry": "门已关闭 / 空闲",
                    "note": "在线且状态正常，是离家判断的重要参考。",
                    "capabilities": ["开合检测", "离家联动"],
                    "last_seen": now - timedelta(minutes=1),
                    "sort_order": 20,
                },
                {
                    "id": "bedroom-ac",
                    "room_id": "bedroom",
                    "name": "主卧空调",
                    "category": "空调",
                    "status": "online",
                    "telemetry": "24°C / 自动模式",
                    "note": "温控稳定，适合尝试更细的自动化策略。",
                    "capabilities": ["温度设定", "风速模式"],
                    "last_seen": now - timedelta(minutes=6),
                    "sort_order": 30,
                },
                {
                    "id": "studio-purifier",
                    "room_id": "studio",
                    "name": "书房净化器",
                    "category": "空气护理",
                    "status": "attention",
                    "telemetry": "AQI 82 / 自动挡",
                    "note": "设备在线，但空气质量已进入需要关注的区间。",
                    "capabilities": ["空气质量监测", "自动净化"],
                    "last_seen": now - timedelta(minutes=8),
                    "sort_order": 40,
                },
                {
                    "id": "pet-fountain",
                    "room_id": "pet",
                    "name": "宠物饮水机",
                    "category": "宠物照护",
                    "status": "offline",
                    "telemetry": "最近一次心跳 27 分钟前",
                    "note": "需要同时确认水量和在线状态。",
                    "capabilities": ["低水位提醒", "运行状态监测"],
                    "last_seen": now - timedelta(minutes=27),
                    "sort_order": 50,
                },
            ],
            "anomalies": [
                {
                    "id": "alert-living-light",
                    "room_id": "living",
                    "device_id": "living-light",
                    "severity": "medium",
                    "title": "离家模式下客厅灯仍然开启",
                    "body": "系统判断这是一条低风险但值得自动化的节能动作。",
                    "recommendation": "先人工确认一次关灯，再决定是否升级成自动执行。",
                    "sort_order": 10,
                },
                {
                    "id": "alert-studio-air",
                    "room_id": "studio",
                    "device_id": "studio-purifier",
                    "severity": "medium",
                    "title": "书房空气质量持续走低",
                    "body": "净化器在线，但主动关怀尚未提前介入。",
                    "recommendation": "检查书房规则阈值，必要时提高净化触发优先级。",
                    "sort_order": 20,
                },
                {
                    "id": "alert-pet-fountain",
                    "room_id": "pet",
                    "device_id": "pet-fountain",
                    "severity": "high",
                    "title": "宠物饮水机状态异常",
                    "body": "设备心跳变旧且水量偏低，需要优先人工确认。",
                    "recommendation": "先确认供电和余量，再判断是否需要重新配对或更换。",
                    "sort_order": 30,
                },
            ],
            "rules": [
                {
                    "id": "rule-away-light",
                    "room_id": "living",
                    "device_id": "living-light",
                    "mode_key": "away",
                    "mode_label": "离家",
                    "target": "客厅灯 / 开关",
                    "condition": "离家 10 分钟后，客厅灯亮度仍大于 0。",
                    "decision": "ask",
                    "rationale": "这条规则已经很接近自动化，但仍保留一次确认。",
                    "sort_order": 10,
                },
                {
                    "id": "rule-away-ac",
                    "room_id": "bedroom",
                    "device_id": "bedroom-ac",
                    "mode_key": "away",
                    "mode_label": "离家",
                    "target": "主卧空调 / 开关",
                    "condition": "离家 20 分钟后，主卧无人活动。",
                    "decision": "always",
                    "rationale": "误判成本较低，节能收益明确，适合自动执行。",
                    "sort_order": 20,
                },
                {
                    "id": "rule-home-purifier",
                    "room_id": "studio",
                    "device_id": "studio-purifier",
                    "mode_key": "home",
                    "mode_label": "在家",
                    "target": "书房净化器 / 开关",
                    "condition": "AQI 高于 75 且主人正在书房停留。",
                    "decision": "ask",
                    "rationale": "人在场时先说明原因再执行，更容易建立信任。",
                    "sort_order": 30,
                },
                {
                    "id": "rule-pet-fountain",
                    "room_id": "pet",
                    "device_id": "pet-fountain",
                    "mode_key": "all-day",
                    "mode_label": "全天",
                    "target": "宠物饮水机 / 断电",
                    "condition": "任何自动关闭动作都必须先通过人工确认。",
                    "decision": "never",
                    "rationale": "涉及宠物安全的设备默认不允许自动断电。",
                    "sort_order": 40,
                },
            ],
        }
