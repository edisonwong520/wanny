from __future__ import annotations

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

    @classmethod
    def _get_state(cls) -> DeviceDashboardState:
        state, _ = DeviceDashboardState.objects.get_or_create(key=cls.state_key)
        return state

    @classmethod
    def _has_snapshot(cls) -> bool:
        return bool(cls._get_state().refreshed_at)

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
    def get_dashboard(cls) -> dict:
        state = cls._get_state()
        has_snapshot = cls._has_snapshot()

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

        rooms = list(DeviceRoom.objects.all())
        devices = list(DeviceSnapshot.objects.select_related("room").all())
        anomalies = list(DeviceAnomaly.objects.select_related("room", "device").filter(is_active=True))
        rules = list(DeviceAutomationRule.objects.select_related("room", "device").filter(is_active=True))

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
    def refresh(cls, *, trigger: str = "manual") -> dict:
        auth = None
        from providers.services import MijiaAuthService
        try:
            auth = MijiaAuthService.get_auth_record(active_only=True)
        except Exception as e:
            logger.error(f"[Device Sync] Failed to check Mijia auth state: {e}")

        if auth:
            payload = cls._build_mijia_snapshot()
        else:
            payload = cls._build_demo_snapshot()

        with transaction.atomic():
            state = cls._get_state()

            DeviceAnomaly.objects.all().delete()
            DeviceAutomationRule.objects.all().delete()
            DeviceSnapshot.objects.all().delete()
            DeviceRoom.objects.all().delete()

            room_map: dict[str, DeviceRoom] = {}
            for room_data in payload["rooms"]:
                room = DeviceRoom.objects.create(
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
            state.save(
                update_fields=[
                    "source",
                    "last_trigger",
                    "requested_trigger",
                    "refresh_requested_at",
                    "last_error",
                    "refreshed_at",
                    "updated_at",
                ]
            )

        return cls.get_dashboard()

    @classmethod
    def request_refresh(cls, *, trigger: str = "manual") -> dict:
        state = cls._get_state()
        cls._queue_refresh(state, trigger=trigger)
        return cls.get_dashboard()

    @classmethod
    def run_pending_refresh(cls, *, sync_interval_seconds: int | None = None) -> bool:
        state = cls._get_state()
        interval_seconds = sync_interval_seconds or cls.default_sync_interval_seconds
        now = timezone.now()
        has_snapshot = cls._has_snapshot()
        is_stale = (
            not has_snapshot
            or not state.refreshed_at
            or (now - state.refreshed_at).total_seconds() >= interval_seconds
        )

        if not state.refresh_requested_at and not is_stale:
            return False

        trigger = state.requested_trigger or ("worker_bootstrap" if not has_snapshot else "worker")
        try:
            cls.refresh(trigger=trigger)
            return True
        except Exception as error:
            state = cls._get_state()
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
    def _build_mijia_snapshot(cls) -> dict:
        from providers.services import MijiaAuthService

        try:
            api = MijiaAuthService.get_authenticated_api()
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
                    "id": h_id,
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
                    "id": "mijia-default",
                    "name": "默认家庭",
                    "climate": "未知",
                    "summary": "未检测到明确的米家家庭分组",
                    "sort_order": 10,
                }
            )

        devices_data = []
        for dev in devices:
            is_online = dev.get("isOnline", False)
            h_id = str(dev.get("home_id", "mijia-default"))
            if h_id not in home_map and h_id != "mijia-default":
                h_id = "mijia-default"

            devices_data.append(
                {
                    "id": dev["did"],
                    "room_id": h_id,
                    "name": dev["name"],
                    "category": cls._map_model_to_category(dev["model"]),
                    "status": "online" if is_online else "offline",
                    "telemetry": f"模型: {dev.get('model', 'unknown')}",
                    "note": f"DID: {dev['did']} | IP: {dev.get('localip', 'N/A')}",
                    "capabilities": [dev.get("model", "unknown")],
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
