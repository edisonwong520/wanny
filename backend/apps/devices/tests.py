import json
import os
import threading
import time
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from accounts.models import Account
from devices.management.commands.runworker import Command as RunWorkerCommand
from providers.models import PlatformAuth

from .models import DeviceControl, DeviceDashboardState, DeviceRoom, DeviceSnapshot
from .services import DeviceDashboardService


def build_sample_snapshot(source: str = "home_assistant") -> dict:
    source_type_map = {
        "home_assistant": "ha_entity",
        "midea_cloud": "midea_cloud_property",
        "mbapi2020": "mbapi2020_property",
        "hisense_ha": "hisense_ha_property",
    }
    default_source_type = source_type_map.get(source, "mijia_property")
    key_prefix = "switch.fridge_power" if source == "home_assistant" else "power"
    sensor_key_prefix = "sensor.fridge_refrigerator_temperature" if source == "home_assistant" else "refrigerator-temperature"
    return {
        "source": source,
        "rooms": [
            {
                "id": f"{source}:kitchen",
                "name": "厨房",
                "climate": "Asia/Shanghai",
                "summary": "测试房间",
                "sort_order": 10,
            }
        ],
        "devices": [
            {
                "id": f"{source}:kitchen:fridge",
                "room_id": f"{source}:kitchen",
                "name": "多开门冰箱",
                "category": "冰箱",
                "status": "online",
                "telemetry": "冷藏区: 4°C | 冷冻区: -18°C",
                "note": "测试设备",
                "capabilities": ["switch", "temperature"],
                "controls": [
                    {
                        "id": f"{source}:switch.fridge_power",
                        "parent_id": f"{source}:switch.fridge_power",
                        "source_type": default_source_type,
                        "kind": "toggle",
                        "key": key_prefix,
                        "label": "总电源",
                        "group_label": "整机",
                        "writable": True,
                        "value": "on",
                        "unit": "",
                        "options": [],
                        "range_spec": {},
                        "action_params": {
                            "service_domain": "switch",
                            "entity_id": "switch.fridge_power",
                            "actions": [
                                {"id": "turn_on", "label": "开启"},
                                {"id": "turn_off", "label": "关闭"},
                            ],
                        },
                        "source_payload": {},
                        "sort_order": 10,
                    },
                    {
                        "id": f"{source}:sensor.fridge_refrigerator_temperature",
                        "parent_id": f"{source}:sensor.fridge_refrigerator_temperature",
                        "source_type": default_source_type,
                        "kind": "sensor",
                        "key": sensor_key_prefix,
                        "label": "冷藏区温度",
                        "group_label": "冷藏区",
                        "writable": False,
                        "value": 4,
                        "unit": "°C",
                        "options": [],
                        "range_spec": {},
                        "action_params": {},
                        "source_payload": {},
                        "sort_order": 20,
                    },
                ],
                "last_seen": None,
                "sort_order": 10,
                "source_payload": {},
            }
        ],
        "anomalies": [],
        "rules": [],
    }


class DeviceDashboardServiceTest(TestCase):
    def setUp(self):
        self.env_patcher = patch.dict(os.environ, {"DEVICE_SYNC_QUEUE_BACKEND": "polling"}, clear=False)
        self.env_patcher.start()
        self.account = Account.objects.create(
            email="device-test@example.com",
            name="Device Test",
            password="pwd",
        )

    def tearDown(self):
        self.env_patcher.stop()

    def test_get_dashboard_queues_bootstrap_when_empty(self):
        payload = DeviceDashboardService.get_dashboard(self.account)

        self.assertEqual(payload["status"], "success")
        self.assertFalse(payload["snapshot"]["has_snapshot"])
        self.assertTrue(payload["snapshot"]["pending_refresh"])
        self.assertEqual(payload["snapshot"]["rooms"], [])
        self.assertEqual(payload["snapshot"]["devices"], [])

        state = DeviceDashboardState.objects.get(account=self.account, key=DeviceDashboardService.state_key)
        self.assertEqual(state.requested_trigger, "bootstrap")
        self.assertIsNotNone(state.refresh_requested_at)
        self.assertIsNone(state.refreshed_at)

    def test_request_refresh_persists_snapshot_and_clears_pending(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="home_assistant",
            auth_payload={"base_url": "http://ha.local:8123", "access_token": "ha-token"},
            is_active=True,
        )

        with patch(
            "devices.services.DeviceDashboardService._build_home_assistant_snapshot",
            return_value=build_sample_snapshot(),
        ):
            payload = DeviceDashboardService.request_refresh(self.account, trigger="manual")

        self.assertTrue(payload["snapshot"]["has_snapshot"])
        self.assertFalse(payload["snapshot"]["pending_refresh"])
        self.assertEqual(payload["snapshot"]["devices"][0]["name"], "多开门冰箱")
        self.assertEqual(len(payload["snapshot"]["devices"][0]["controls"]), 2)

        state = DeviceDashboardState.objects.get(account=self.account, key=DeviceDashboardService.state_key)
        self.assertEqual(state.last_trigger, "manual")
        self.assertEqual(state.requested_trigger, "")
        self.assertIsNone(state.refresh_requested_at)
        self.assertIsNotNone(state.refreshed_at)

    def test_get_dashboard_with_non_device_provider_auth_still_bootstraps(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="wechat",
            auth_payload={"token": "wx-token"},
            is_active=True,
        )

        payload = DeviceDashboardService.get_dashboard(self.account)

        self.assertFalse(payload["snapshot"]["has_snapshot"])
        self.assertTrue(payload["snapshot"]["pending_refresh"])

    def test_get_dashboard_with_device_provider_auth_refreshes_inline_on_polling_backend(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="mbapi2020",
            auth_payload={"access_token": "token", "region": "China"},
            is_active=True,
        )

        with patch(
            "devices.services.DeviceDashboardService.refresh",
            return_value={
                "status": "success",
                "snapshot": {
                    "has_snapshot": True,
                    "pending_refresh": False,
                    "source": "mbapi2020",
                    "last_trigger": "bootstrap",
                    "last_error": "",
                    "refreshed_at": "2026-04-02T22:00:00",
                    "rooms": [],
                    "devices": [],
                    "anomalies": [],
                    "rules": [],
                },
            },
        ) as mocked_refresh:
            payload = DeviceDashboardService.get_dashboard(self.account)

        mocked_refresh.assert_called_once_with(self.account, trigger="bootstrap")
        self.assertTrue(payload["snapshot"]["has_snapshot"])
        self.assertFalse(payload["snapshot"]["pending_refresh"])

    def test_request_refresh_enqueues_redis_task_when_enabled(self):
        with patch.dict(os.environ, {"DEVICE_SYNC_QUEUE_BACKEND": "redis"}, clear=False), patch(
            "devices.services.enqueue_account_refresh",
            return_value=True,
        ) as mocked_enqueue:
            payload = DeviceDashboardService.request_refresh(self.account, trigger="api")

        self.assertTrue(payload["snapshot"]["pending_refresh"])
        mocked_enqueue.assert_called_once_with(self.account.id)

    def test_request_refresh_falls_back_when_redis_enqueue_fails(self):
        with patch.dict(os.environ, {"DEVICE_SYNC_QUEUE_BACKEND": "redis"}, clear=False), patch(
            "devices.services.enqueue_account_refresh",
            side_effect=RuntimeError("redis unavailable"),
        ):
            payload = DeviceDashboardService.request_refresh(self.account, trigger="api")

        self.assertTrue(payload["snapshot"]["pending_refresh"])
        state = DeviceDashboardState.objects.get(account=self.account, key=DeviceDashboardService.state_key)
        self.assertEqual(state.requested_trigger, "api")

    def test_request_refresh_runs_inline_on_polling_backend_with_device_provider_auth(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="mbapi2020",
            auth_payload={"access_token": "token", "region": "China"},
            is_active=True,
        )

        with patch(
            "devices.services.DeviceDashboardService.refresh",
            return_value={
                "status": "success",
                "snapshot": {
                    "has_snapshot": True,
                    "pending_refresh": False,
                    "source": "mbapi2020",
                    "last_trigger": "api",
                    "last_error": "",
                    "refreshed_at": "2026-04-02T22:00:00",
                    "rooms": [],
                    "devices": [],
                    "anomalies": [],
                    "rules": [],
                },
            },
        ) as mocked_refresh:
            payload = DeviceDashboardService.request_refresh(self.account, trigger="api")

        mocked_refresh.assert_called_once_with(self.account, trigger="api")
        self.assertTrue(payload["snapshot"]["has_snapshot"])
        self.assertFalse(payload["snapshot"]["pending_refresh"])

    def test_request_refresh_runs_inline_on_redis_backend_for_interactive_trigger(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="mbapi2020",
            auth_payload={"access_token": "token", "region": "China"},
            is_active=True,
        )

        with patch.dict(os.environ, {"DEVICE_SYNC_QUEUE_BACKEND": "redis"}, clear=False), patch(
            "devices.services.DeviceDashboardService.refresh",
            return_value={
                "status": "success",
                "snapshot": {
                    "has_snapshot": True,
                    "pending_refresh": False,
                    "source": "mbapi2020",
                    "last_trigger": "api",
                    "last_error": "",
                    "refreshed_at": "2026-04-02T22:00:00",
                    "rooms": [],
                    "devices": [],
                    "anomalies": [],
                    "rules": [],
                },
            },
        ) as mocked_refresh, patch(
            "devices.services.enqueue_account_refresh"
        ) as mocked_enqueue:
            payload = DeviceDashboardService.request_refresh(self.account, trigger="api")

        mocked_refresh.assert_called_once_with(self.account, trigger="api")
        mocked_enqueue.assert_not_called()
        self.assertTrue(payload["snapshot"]["has_snapshot"])
        self.assertFalse(payload["snapshot"]["pending_refresh"])

    def test_request_refresh_does_not_run_inline_for_connect_trigger(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="hisense_ha",
            auth_payload={"username": "hisense@example.com", "refresh_token": "refresh-token"},
            is_active=True,
        )

        with patch(
            "devices.services.DeviceDashboardService.refresh",
        ) as mocked_refresh:
            payload = DeviceDashboardService.request_refresh(self.account, trigger="connect_hisense_ha")

        mocked_refresh.assert_not_called()
        self.assertFalse(payload["snapshot"]["has_snapshot"])
        self.assertTrue(payload["snapshot"]["pending_refresh"])
        state = DeviceDashboardState.objects.get(account=self.account, key=DeviceDashboardService.state_key)
        self.assertEqual(state.requested_trigger, "connect_hisense_ha")

    def test_refresh_uses_home_assistant_snapshot_when_authorized(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="home_assistant",
            auth_payload={
                "base_url": "http://ha.local:8123",
                "access_token": "ha-token",
                "instance_name": "My Home",
            },
            is_active=True,
        )

        with patch(
            "devices.services.DeviceDashboardService._build_home_assistant_snapshot",
            return_value=build_sample_snapshot(),
        ):
            payload = DeviceDashboardService.refresh(self.account, trigger="test")

        self.assertEqual(payload["snapshot"]["source"], "home_assistant")
        self.assertEqual(payload["snapshot"]["devices"][0]["name"], "多开门冰箱")
        self.assertEqual(payload["snapshot"]["devices"][0]["controls"][0]["label"], "总电源")

    def test_refresh_uses_midea_cloud_snapshot_when_authorized(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="midea_cloud",
            auth_payload={
                "account": "demo@example.com",
                "access_token": "midea-token",
            },
            is_active=True,
        )

        with patch(
            "devices.services.DeviceDashboardService._build_midea_cloud_snapshot",
            return_value=build_sample_snapshot("midea_cloud"),
        ):
            payload = DeviceDashboardService.refresh(self.account, trigger="test")

        self.assertEqual(payload["snapshot"]["source"], "midea_cloud")
        self.assertEqual(payload["snapshot"]["devices"][0]["name"], "多开门冰箱")
        self.assertEqual(payload["snapshot"]["devices"][0]["controls"][0]["source_type"], "midea_cloud_property")

    def test_refresh_uses_mbapi2020_snapshot_when_authorized(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="mbapi2020",
            auth_payload={
                "account": "driver@example.com",
                "access_token": "mb-token",
                "region": "China",
            },
            is_active=True,
        )

        with patch(
            "devices.services.DeviceDashboardService._build_mbapi2020_snapshot",
            return_value=build_sample_snapshot("mbapi2020"),
        ):
            payload = DeviceDashboardService.refresh(self.account, trigger="test")

        self.assertEqual(payload["snapshot"]["source"], "mbapi2020")
        self.assertEqual(payload["snapshot"]["devices"][0]["controls"][0]["source_type"], "mbapi2020_property")

    def test_refresh_uses_hisense_ha_snapshot_when_authorized(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="hisense_ha",
            auth_payload={"username": "hisense@example.com", "refresh_token": "refresh-token"},
            is_active=True,
        )

        snapshot = build_sample_snapshot("midea_cloud")
        snapshot["source"] = "hisense_ha"
        snapshot["devices"][0]["id"] = "hisense_ha:dev-1"
        snapshot["devices"][0]["controls"][0]["source_type"] = "hisense_ha_property"
        with patch(
            "devices.services.DeviceDashboardService._build_hisense_ha_snapshot",
            return_value=snapshot,
        ):
            payload = DeviceDashboardService.refresh(self.account, trigger="test")

        self.assertEqual(payload["snapshot"]["source"], "hisense_ha")
        self.assertEqual(payload["snapshot"]["devices"][0]["controls"][0]["source_type"], "hisense_ha_property")

    def test_mbapi2020_lock_status_is_humanized(self):
        raw_vehicle = {
            "vin": "LE4LG4GB2SL195893",
            "name": "E 300 L 豪华型轿车",
            "license_plate": "川GPT032",
            "status_payload": {
                "doorlockstatusvehicle": 2,
                "tanklevelpercent": 86,
            },
            "command_capabilities": [],
            "pin_available": False,
        }

        controls = DeviceDashboardService._build_mbapi2020_controls(raw_vehicle)
        lock_control = next(control for control in controls if control["key"] == "doorlockstatusvehicle")
        self.assertEqual(lock_control["value"], "已锁车")

        summary = DeviceDashboardService._summarize_mbapi2020_vehicle(raw_vehicle, controls)
        self.assertIn("车锁 已锁车", summary)

    def test_mbapi2020_common_status_strings_are_humanized(self):
        raw_vehicle = {
            "vin": "LE4LG4GB2SL195893",
            "name": "E 300 L 豪华型轿车",
            "license_plate": "川GPT032",
            "status_payload": {
                "decklidstatus": "open",
                "chargingstatusdisplay": "charging",
            },
            "command_capabilities": [],
            "pin_available": False,
        }

        controls = DeviceDashboardService._build_mbapi2020_controls(raw_vehicle)
        decklid = next(control for control in controls if control["key"] == "decklidstatus")
        charging = next(control for control in controls if control["key"] == "chargingstatusdisplay")

        self.assertEqual(decklid["value"], "已打开")
        self.assertEqual(charging["value"], "充电中")

    def test_mbapi2020_realistic_window_and_roof_statuses_are_humanized(self):
        raw_vehicle = {
            "vin": "LE4LG4GB2SL195893",
            "name": "E 300 L 豪华型轿车",
            "license_plate": "川GPT032",
            "status_payload": {
                "doorStatusOverall": "1",
                "windowstatusfrontleft": "2",
                "windowstatusfrontright": "2",
                "sunroofstatus": "0",
                "doorstatusfrontleft": False,
                "doorlockstatusfrontleft": False,
            },
            "command_capabilities": [],
            "pin_available": False,
        }

        controls = DeviceDashboardService._build_mbapi2020_controls(raw_vehicle)
        indexed = {control["key"]: control for control in controls}

        self.assertEqual(indexed["doorStatusOverall"]["label"], "车门总状态")
        self.assertEqual(indexed["doorStatusOverall"]["value"], "全部关闭")
        self.assertEqual(indexed["windowstatusfrontleft"]["label"], "左前窗")
        self.assertEqual(indexed["windowstatusfrontleft"]["value"], "已关闭")
        self.assertEqual(indexed["sunroofstatus"]["label"], "天窗状态")
        self.assertEqual(indexed["sunroofstatus"]["value"], "已关闭")
        self.assertEqual(indexed["doorstatusfrontleft"]["label"], "左前门")
        self.assertEqual(indexed["doorstatusfrontleft"]["value"], "已关闭")
        self.assertEqual(indexed["doorlockstatusfrontleft"]["label"], "左前门锁")
        self.assertEqual(indexed["doorlockstatusfrontleft"]["value"], "已锁止")

    def test_mbapi2020_brake_and_parking_statuses_are_humanized(self):
        raw_vehicle = {
            "vin": "LE4LG4GB2SL195893",
            "name": "E 300 L 豪华型轿车",
            "license_plate": "川GPT032",
            "status_payload": {
                "parkbrakestatus": True,
                "warningbrakefluid": False,
            },
            "command_capabilities": [],
            "pin_available": False,
        }

        controls = DeviceDashboardService._build_mbapi2020_controls(raw_vehicle)
        indexed = {control["key"]: control for control in controls}

        self.assertEqual(indexed["parkbrakestatus"]["label"], "驻车制动")
        self.assertEqual(indexed["parkbrakestatus"]["value"], "已启用")
        self.assertEqual(indexed["warningbrakefluid"]["label"], "制动液状态")
        self.assertEqual(indexed["warningbrakefluid"]["value"], "正常")

    def test_refresh_runs_provider_snapshots_in_parallel(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="mijia",
            auth_payload={"serviceToken": "demo", "ssecurity": "demo", "userId": "demo"},
            is_active=True,
        )
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="mbapi2020",
            auth_payload={"account": "driver@example.com", "access_token": "mb-token", "region": "China"},
            is_active=True,
        )

        started = set()
        started_lock = threading.Lock()
        second_started = threading.Event()
        def slow_mijia(_account):
            with started_lock:
                started.add("mijia")
                if "mbapi2020" in started:
                    second_started.set()
            second_started.wait(timeout=2)
            return build_sample_snapshot("mijia")

        def fast_mbapi(_account):
            with started_lock:
                started.add("mbapi2020")
                if "mijia" in started:
                    second_started.set()
            return build_sample_snapshot("mbapi2020")

        with patch(
            "devices.services.DeviceDashboardService._build_mijia_snapshot",
            side_effect=slow_mijia,
        ), patch(
            "devices.services.DeviceDashboardService._build_mbapi2020_snapshot",
            side_effect=fast_mbapi,
        ):
            DeviceDashboardService.refresh(self.account, trigger="test")

        self.assertTrue(second_started.is_set())

    def test_refresh_preserves_existing_device_sort_order(self):
        room = DeviceRoom.objects.create(
            account=self.account,
            slug="manual-room",
            name="手动房间",
            climate="",
            summary="",
            sort_order=50,
        )
        DeviceSnapshot.objects.create(
            account=self.account,
            external_id="mijia:manual-2",
            room=room,
            name="第二台",
            category="灯光",
            status="online",
            telemetry="在线",
            sort_order=10,
        )
        DeviceSnapshot.objects.create(
            account=self.account,
            external_id="mijia:manual-1",
            room=room,
            name="第一台",
            category="灯光",
            status="online",
            telemetry="在线",
            sort_order=20,
        )

        with patch(
            "devices.services.DeviceDashboardService._build_mijia_snapshot",
            return_value={
                "source": "mijia",
                "rooms": [
                    {
                        "id": "manual-room",
                        "name": "手动房间",
                        "climate": "",
                        "summary": "",
                        "sort_order": 10,
                    }
                ],
                "devices": [
                    {
                        "id": "mijia:manual-1",
                        "room_id": "manual-room",
                        "name": "第一台",
                        "category": "灯光",
                        "status": "online",
                        "telemetry": "在线",
                        "note": "",
                        "capabilities": [],
                        "controls": [],
                        "last_seen": None,
                        "sort_order": 10,
                    },
                    {
                        "id": "mijia:manual-2",
                        "room_id": "manual-room",
                        "name": "第二台",
                        "category": "灯光",
                        "status": "online",
                        "telemetry": "在线",
                        "note": "",
                        "capabilities": [],
                        "controls": [],
                        "last_seen": None,
                        "sort_order": 20,
                    },
                ],
                "anomalies": [],
                "rules": [],
            },
        ), patch(
            "providers.services.MijiaAuthService.get_auth_record",
            return_value=object(),
        ), patch(
            "providers.services.HomeAssistantAuthService.get_auth_record",
            return_value=None,
        ), patch(
            "providers.services.MideaCloudAuthService.get_auth_record",
            return_value=None,
        ), patch(
            "providers.services.MbApi2020AuthService.get_auth_record",
            return_value=None,
        ):
            payload = DeviceDashboardService.refresh(self.account, trigger="test")

        ordered_ids = [device["id"] for device in payload["snapshot"]["devices"]]
        self.assertEqual(ordered_ids[:2], ["mijia:manual-2", "mijia:manual-1"])

    def test_mbapi2020_snapshot_builds_action_controls_from_command_capabilities(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="mbapi2020",
            auth_payload={
                "account": "driver@example.com",
                "access_token": "mb-token",
                "region": "China",
                "pin": "1234",
            },
            is_active=True,
        )

        with patch("providers.services.MbApi2020AuthService.get_client") as mocked_get_client:
            mocked_get_client.return_value.list_devices.return_value = [
                {
                    "vin": "VIN123456",
                    "name": "EQE SUV",
                    "license_plate": "沪A12345",
                    "region": "China",
                    "pin_available": True,
                    "status_payload": {
                        "doorlockstatusvehicle": "locked",
                        "rangeelectric": 420,
                    },
                    "command_capabilities": [
                        {"commandName": "DOORS_LOCK", "isAvailable": True},
                        {"commandName": "DOORS_UNLOCK", "isAvailable": True},
                        {"commandName": "SIGPOS_START", "isAvailable": True},
                    ],
                }
            ]

            snapshot = DeviceDashboardService._build_mbapi2020_snapshot(self.account)

        self.assertEqual(snapshot["source"], "mbapi2020")
        self.assertEqual(snapshot["devices"][0]["id"], "mbapi2020:VIN123456")
        action_keys = {control["key"] for control in snapshot["devices"][0]["controls"] if control["kind"] == "action"}
        self.assertIn("door_lock", action_keys)
        self.assertIn("sigpos", action_keys)

    def test_mbapi2020_snapshot_prefers_vehicle_model_name_over_numeric_code(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="mbapi2020",
            auth_payload={
                "account": "driver@example.com",
                "access_token": "mb-token",
                "region": "China",
            },
            is_active=True,
        )

        with patch("providers.services.MbApi2020AuthService.get_client") as mocked_get_client:
            mocked_get_client.return_value.list_devices.return_value = [
                {
                    "vin": "VIN123456",
                    "name": "214",
                    "model": "E 300 L 豪华型轿车",
                    "license_plate": "沪A12345",
                    "region": "China",
                    "status_payload": {},
                    "command_capabilities": [],
                    "raw": {
                        "licensePlate": "沪A12345",
                        "salesRelatedInformation": {
                            "baumuster": {
                                "baumusterDescription": "E 300 L 豪华型轿车",
                            }
                        },
                    },
                }
            ]

            snapshot = DeviceDashboardService._build_mbapi2020_snapshot(self.account)

        self.assertEqual(snapshot["devices"][0]["name"], "E 300 L 豪华型轿车")

    def test_midea_cloud_snapshot_builds_sensor_controls_from_status_payload(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="midea_cloud",
            auth_payload={
                "account": "demo@example.com",
                "password": "secret",
                "server": 2,
            },
            is_active=True,
        )

        with patch("providers.services.MideaCloudAuthService.get_client") as mocked_get_client:
            mocked_get_client.return_value.list_devices.return_value = [
                {
                    "id": "998877",
                    "device_id": "998877",
                    "appliance_code": 998877,
                    "home_id": "1001",
                    "home_name": "我的家",
                    "room_name": "客厅",
                    "name": "客厅空调",
                    "device_type": 0xAC,
                    "category": "air_conditioner",
                    "model": "9ABCDEFG",
                    "model_number": "KFR-35GW",
                    "manufacturer_code": "0000",
                    "smart_product_id": "sp-1",
                    "sn": "123456789ABCDEFG",
                    "sn8": "9ABCDEFG",
                    "online": True,
                    "status": "online",
                    "status_payload": {"power": "on", "target_temperature": 24, "indoor_temperature": 27},
                }
            ]

            snapshot = DeviceDashboardService._build_midea_cloud_snapshot(self.account)

        self.assertEqual(snapshot["source"], "midea_cloud")
        self.assertEqual(snapshot["rooms"][0]["name"], "客厅")
        self.assertEqual(snapshot["devices"][0]["id"], "midea_cloud:998877")
        control_keys = {control["key"] for control in snapshot["devices"][0]["controls"]}
        self.assertIn("thermostat:power", control_keys)
        self.assertIn("thermostat:hvac_mode", control_keys)
        self.assertIn("thermostat:target_temperature", control_keys)
        power_control = next(
            control for control in snapshot["devices"][0]["controls"] if control["key"] == "thermostat:power"
        )
        self.assertTrue(power_control["writable"])
        self.assertEqual(snapshot["devices"][0]["category"], "空调")

    def test_midea_cloud_snapshot_uses_dynamic_name_attribute_for_control_label(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="midea_cloud",
            auth_payload={
                "account": "demo@example.com",
                "password": "secret",
                "server": 2,
            },
            is_active=True,
        )

        with patch("providers.services.MideaCloudAuthService.get_client") as mocked_get_client:
            mocked_get_client.return_value.list_devices.return_value = [
                {
                    "id": "2468",
                    "device_id": "2468",
                    "appliance_code": 2468,
                    "home_id": "1001",
                    "home_name": "我的家",
                    "room_name": "客厅",
                    "name": "四键面板",
                    "device_type": 0x21,
                    "category": "panel",
                    "model": "00000000",
                    "model_number": "68",
                    "manufacturer_code": "0000",
                    "smart_product_id": "sp-2",
                    "sn": "123456789ABCDEFG",
                    "sn8": "00000000",
                    "online": True,
                    "status": "online",
                    "status_payload": {
                        "endpoint_1_OnOff": "1",
                        "endpoint_1_name": "客厅主灯",
                    },
                }
            ]

            snapshot = DeviceDashboardService._build_midea_cloud_snapshot(self.account)

        control = next(control for control in snapshot["devices"][0]["controls"] if control["key"] == "endpoint_1_OnOff")
        self.assertEqual(control["label"], "客厅主灯")
        control_keys = {control["key"] for control in snapshot["devices"][0]["controls"]}
        self.assertNotIn("endpoint_1_name", control_keys)

    def test_midea_cloud_snapshot_keeps_refrigerator_zone_temperature_controls(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="midea_cloud",
            auth_payload={
                "account": "demo@example.com",
                "password": "secret",
                "server": 2,
            },
            is_active=True,
        )

        with patch("providers.services.MideaCloudAuthService.get_client") as mocked_get_client:
            mocked_get_client.return_value.list_devices.return_value = [
                {
                    "id": "556677",
                    "device_id": "556677",
                    "appliance_code": 556677,
                    "home_id": "1001",
                    "home_name": "我的家",
                    "room_name": "厨房",
                    "name": "法式冰箱",
                    "device_type": 0xCA,
                    "category": "refrigerator",
                    "model": "CA000001",
                    "model_number": "BCD-123",
                    "manufacturer_code": "0000",
                    "smart_product_id": "sp-fridge",
                    "sn": "123456789ABCDEFG",
                    "sn8": "00000000",
                    "online": True,
                    "status": "online",
                    "status_payload": {
                        "storage_power": "on",
                        "storage_temperature": 4,
                        "refrigeration_real_temperature": 5,
                        "freezing_power": "on",
                        "freezing_temperature": -18,
                        "freezing_real_temperature": -17,
                    },
                }
            ]

            snapshot = DeviceDashboardService._build_midea_cloud_snapshot(self.account)

        controls = snapshot["devices"][0]["controls"]
        control_keys = {control["key"] for control in controls}
        self.assertIn("storage_zone:target_temperature", control_keys)
        self.assertIn("freezing_zone:target_temperature", control_keys)

        storage_target = next(control for control in controls if control["key"] == "storage_zone:target_temperature")
        freezing_target = next(control for control in controls if control["key"] == "freezing_zone:target_temperature")
        self.assertEqual(storage_target["group_label"], "冷藏区")
        self.assertEqual(storage_target["value"], 4)
        self.assertEqual(storage_target["action_params"]["control_key"], "storage_temperature")
        self.assertEqual(freezing_target["group_label"], "冷冻区")
        self.assertEqual(freezing_target["value"], -18)
        self.assertEqual(freezing_target["action_params"]["control_key"], "freezing_temperature")

    def test_midea_cloud_snapshot_translates_dishwasher_controls_and_hides_cmd_sensor(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="midea_cloud",
            auth_payload={
                "account": "demo@example.com",
                "password": "secret",
                "server": 2,
            },
            is_active=True,
        )

        with patch("providers.services.MideaCloudAuthService.get_client") as mocked_get_client:
            mocked_get_client.return_value.list_devices.return_value = [
                {
                    "id": "210006736966621",
                    "device_id": "210006736966621",
                    "appliance_code": 210006736966621,
                    "home_id": "1001",
                    "home_name": "我的家",
                    "room_name": "厨房",
                    "name": "洗碗机",
                    "device_type": 0xE1,
                    "category": "dishwasher",
                    "model": "GX1000S Max尊享版",
                    "model_number": "3",
                    "manufacturer_code": "0000",
                    "smart_product_id": "10009112",
                    "sn": "0000E1531760064ACA3101D000494394",
                    "sn8": "760064AC",
                    "online": True,
                    "status": "online",
                    "status_payload": {
                        "cmd": "deadbeef",
                        "waterswitch": 0,
                        "uvswitch": 1,
                        "airswitch": 1,
                        "dryswitch": 0,
                        "dry_step_switch": 1,
                        "air_set_hour": 4,
                        "work_status": "power_off",
                        "mode": "neutral_gear",
                        "temperature": 21,
                        "softwater": 3,
                        "left_time": 0,
                        "air_left_hour": 0,
                        "doorswitch": 1,
                        "air_status": 0,
                        "water_lack": 0,
                        "softwater_lack": 0,
                        "wash_stage": 0,
                        "bright_lack": 1,
                    },
                }
            ]

            snapshot = DeviceDashboardService._build_midea_cloud_snapshot(self.account)

        controls = snapshot["devices"][0]["controls"]
        control_keys = {control["key"] for control in controls}
        self.assertNotIn("cmd", control_keys)

        waterswitch = next(control for control in controls if control["key"] == "waterswitch")
        self.assertEqual(waterswitch["label"], "热水开关")
        self.assertEqual(waterswitch["group_label"], "整机")

        work_status = next(control for control in controls if control["key"] == "work_status")
        self.assertEqual(work_status["label"], "工作状态")
        option_labels = [option["label"] for option in work_status["options"]]
        self.assertIn("关机", option_labels)
        self.assertIn("开机", option_labels)

        wash_mode = next(control for control in controls if control["key"] == "wash_mode")
        self.assertEqual(wash_mode["label"], "洗涤模式")
        self.assertEqual(wash_mode["group_label"], "模式")
        wash_mode_labels = [option["label"] for option in wash_mode["options"]]
        self.assertIn("智能洗", wash_mode_labels)
        self.assertIn("强力洗", wash_mode_labels)

    def test_midea_cloud_snapshot_marks_button_panel_controls_as_actions(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="midea_cloud",
            auth_payload={
                "account": "demo@example.com",
                "password": "secret",
                "server": 2,
            },
            is_active=True,
        )

        with patch("providers.services.MideaCloudAuthService.get_client") as mocked_get_client:
            mocked_get_client.return_value.list_devices.return_value = [
                {
                    "id": "1357",
                    "device_id": "1357",
                    "appliance_code": 1357,
                    "home_id": "1001",
                    "home_name": "我的家",
                    "room_name": "玄关",
                    "name": "四键按钮面板",
                    "device_type": 0x21,
                    "category": "panel",
                    "model": "00000000",
                    "model_number": "78",
                    "manufacturer_code": "0000",
                    "smart_product_id": "sp-3",
                    "sn": "123456789ABCDEFG",
                    "sn8": "00000000",
                    "online": True,
                    "status": "online",
                    "status_payload": {
                        "endpoint_1_name": "回家模式",
                        "endpoint_2_name": "离家模式",
                        "endpoint_3_name": "影院模式",
                        "endpoint_4_name": "睡眠模式",
                    },
                }
            ]

            snapshot = DeviceDashboardService._build_midea_cloud_snapshot(self.account)

        controls = snapshot["devices"][0]["controls"]
        self.assertEqual(len([control for control in controls if control["kind"] == "action"]), 4)
        first = next(control for control in controls if control["key"] == "endpoint_1_OnOff")
        self.assertEqual(first["source_type"], DeviceControl.SourceTypeChoices.MIDEA_CLOUD_ACTION)
        self.assertEqual(first["label"], "回家模式")

    def test_execute_midea_cloud_control_passes_mapped_payload(self):
        device = DeviceSnapshot(
            external_id="midea_cloud:998877",
            source_payload={"device_id": "998877"},
        )
        control = DeviceControl(
            external_id="midea_cloud:998877:power",
            key="power",
            kind=DeviceControl.KindChoices.TOGGLE,
            source_type=DeviceControl.SourceTypeChoices.MIDEA_CLOUD_PROPERTY,
            writable=True,
            action_params={
                "device_id": "998877",
                "actions": [
                    {"id": "turn_on", "label": "Turn On"},
                    {"id": "turn_off", "label": "Turn Off"},
                ],
            },
            source_payload={
                "mapping": {
                    "actions": {
                        "turn_on": {"power": "on"},
                        "turn_off": {"power": "off"},
                    }
                }
            },
        )

        with patch("providers.services.MideaCloudAuthService.get_client") as mocked_get_client:
            DeviceDashboardService._execute_midea_cloud_control(
                self.account,
                device=device,
                control=control,
                action="turn_off",
                value=None,
            )

        mocked_get_client.return_value.execute_control.assert_called_once_with(
            device_id="998877",
            control={
                "key": "power",
                "kind": DeviceControl.KindChoices.TOGGLE,
                "source_type": DeviceControl.SourceTypeChoices.MIDEA_CLOUD_PROPERTY,
                "action_params": {
                    "device_id": "998877",
                    "actions": [
                        {"id": "turn_on", "label": "Turn On"},
                        {"id": "turn_off", "label": "Turn Off"},
                    ],
                    "control": {"power": "off"},
                },
            },
            value=None,
        )

    def test_home_assistant_snapshot_prefers_registry_grouping(self):
        states = [
            {
                "entity_id": "switch.fridge_power",
                "state": "on",
                "attributes": {"friendly_name": "冰箱 电源"},
            },
            {
                "entity_id": "sensor.fridge_refrigerator_temperature",
                "state": "4",
                "attributes": {"friendly_name": "冰箱 冷藏区温度", "unit_of_measurement": "°C"},
            },
        ]
        registry = {
            "areas": [{"area_id": "kitchen", "name": "厨房"}],
            "devices": [{"id": "device-fridge", "area_id": "kitchen", "name": "多开门冰箱"}],
            "entities": [
                {"entity_id": "switch.fridge_power", "device_id": "device-fridge"},
                {"entity_id": "sensor.fridge_refrigerator_temperature", "device_id": "device-fridge"},
            ],
        }

        with patch(
            "providers.services.HomeAssistantAuthService.get_graph",
            return_value=(
                {"location_name": "My Home", "time_zone": "Asia/Shanghai"},
                states,
                registry,
            ),
        ):
            snapshot = DeviceDashboardService._build_home_assistant_snapshot(self.account)

        self.assertEqual(snapshot["rooms"][0]["name"], "厨房")
        self.assertEqual(len(snapshot["devices"]), 1)
        self.assertEqual(snapshot["devices"][0]["name"], "多开门冰箱")
        self.assertEqual(snapshot["devices"][0]["id"], "home_assistant:device_device_fridge")
        self.assertEqual(len(snapshot["devices"][0]["controls"]), 2)
        self.assertEqual(snapshot["devices"][0]["controls"][0]["group_label"], "整机")
        self.assertEqual(snapshot["devices"][0]["controls"][1]["group_label"], "冷藏区")

    def test_home_assistant_snapshot_falls_back_when_registry_name_is_numeric_identifier(self):
        states = [
            {
                "entity_id": "switch.camera_power",
                "state": "on",
                "attributes": {"friendly_name": "Camera Pro 电源"},
            }
        ]
        registry = {
            "areas": [{"area_id": "study", "name": "书房"}],
            "devices": [{"id": "device-camera", "area_id": "study", "name": "210006736906642"}],
            "entities": [
                {"entity_id": "switch.camera_power", "device_id": "device-camera"},
            ],
        }

        with patch(
            "providers.services.HomeAssistantAuthService.get_graph",
            return_value=(
                {"location_name": "My Home", "time_zone": "Asia/Shanghai"},
                states,
                registry,
            ),
        ):
            snapshot = DeviceDashboardService._build_home_assistant_snapshot(self.account)

        self.assertEqual(snapshot["devices"][0]["name"], "Camera")

    def test_home_assistant_climate_builds_rich_controls(self):
        controls = DeviceDashboardService._build_home_assistant_controls(
            [
                {
                    "entity_id": "climate.living_room_ac",
                    "state": "cool",
                    "attributes": {
                        "friendly_name": "客厅空调",
                        "temperature": 24,
                        "current_temperature": 27,
                        "hvac_modes": ["off", "cool", "heat"],
                        "preset_modes": ["none", "sleep"],
                        "fan_modes": ["auto", "low", "high"],
                        "min_temp": 16,
                        "max_temp": 30,
                    },
                }
            ]
        )

        keys = {control["key"] for control in controls}
        self.assertIn("climate.living_room_ac:hvac_mode", keys)
        self.assertIn("climate.living_room_ac:target_temperature", keys)
        self.assertIn("climate.living_room_ac:current_temperature", keys)
        self.assertIn("climate.living_room_ac:preset_mode", keys)
        self.assertIn("climate.living_room_ac:fan_mode", keys)

    def test_infer_mijia_device_name_avoids_numeric_identifier(self):
        name = DeviceDashboardService._infer_mijia_device_name(
            dev={"name": "210006736906642"},
            did="210006736906642",
            model="camera",
        )

        self.assertEqual(name, "监控")

    def test_execute_home_assistant_control_refreshes_only_target_device(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="home_assistant",
            auth_payload={
                "base_url": "http://ha.local:8123",
                "access_token": "ha-token",
            },
            is_active=True,
        )

        initial_snapshot = build_sample_snapshot()
        initial_snapshot["devices"][0]["source_payload"] = {
            "entity_ids": ["switch.fridge_power"],
            "device_id": "device-fridge",
            "device_name": "多开门冰箱",
            "area_id": "kitchen",
        }
        refreshed_entities = [
            {
                "entity_id": "switch.fridge_power",
                "state": "off",
                "attributes": {"friendly_name": "冰箱 电源"},
            }
        ]

        with patch(
            "devices.services.DeviceDashboardService._build_home_assistant_snapshot",
            return_value=initial_snapshot,
        ), patch("devices.services.requests.post") as requests_post, patch(
            "providers.services.HomeAssistantAuthService.get_entity_states",
            return_value=({"location_name": "My Home", "time_zone": "Asia/Shanghai"}, refreshed_entities),
        ), patch("devices.services.DeviceDashboardService.request_refresh") as mocked_request_refresh:
            requests_post.return_value.raise_for_status.return_value = None
            DeviceDashboardService.refresh(self.account, trigger="seed")
            payload = DeviceDashboardService.execute_control(
                self.account,
                device_external_id="home_assistant:kitchen:fridge",
                control_external_id="home_assistant:switch.fridge_power",
                action="turn_off",
            )

        self.assertEqual(payload["snapshot"]["devices"][0]["controls"][0]["value"], "off")
        self.assertFalse(payload["snapshot"]["pending_refresh"])
        mocked_request_refresh.assert_not_called()
        requests_post.assert_called_once()

    def test_execute_mijia_control_refreshes_only_target_device(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="mijia",
            auth_payload={"serviceToken": "demo", "ssecurity": "demo", "userId": "demo"},
            is_active=True,
        )

        snapshot = build_sample_snapshot(source="mijia")
        snapshot["devices"][0]["id"] = "mijia:998877"
        snapshot["devices"][0]["controls"][0]["id"] = "mijia:998877:property:power"
        snapshot["devices"][0]["controls"][0]["parent_id"] = "mijia:998877"
        snapshot["devices"][0]["controls"][0]["key"] = "power"
        snapshot["devices"][0]["controls"][0]["action_params"] = {"did": "998877"}
        snapshot["devices"][0]["controls"][0]["source_payload"] = {"siid": 2, "piid": 1}
        snapshot["devices"][0]["source_payload"] = {"did": "998877", "model": "fridge.demo", "name": "多开门冰箱"}

        refreshed_controls = [
            {
                "id": "mijia:998877:property:power",
                "parent_id": "mijia:998877",
                "source_type": DeviceControl.SourceTypeChoices.MIJIA_PROPERTY,
                "kind": DeviceControl.KindChoices.TOGGLE,
                "key": "power",
                "label": "总电源",
                "group_label": "整机",
                "writable": True,
                "value": "off",
                "unit": "",
                "options": [],
                "range_spec": {},
                "action_params": {"did": "998877"},
                "source_payload": {"siid": 2, "piid": 1},
                "sort_order": 10,
            }
        ]

        with patch(
            "devices.services.DeviceDashboardService._build_mijia_snapshot",
            return_value=snapshot,
        ), patch("mijiaAPI.mijiaDevice") as mocked_mijia_device, patch(
            "mijiaAPI.get_device_info",
            return_value={},
        ), patch(
            "devices.services.DeviceDashboardService._build_mijia_controls",
            return_value=refreshed_controls,
        ), patch(
            "providers.services.MijiaAuthService.get_authenticated_api"
        ) as mocked_get_api, patch("devices.services.DeviceDashboardService.request_refresh") as mocked_request_refresh:
            mocked_client = mocked_mijia_device.return_value
            mocked_client.set.return_value = None
            mocked_get_api.return_value = object()

            DeviceDashboardService.refresh(self.account, trigger="seed")
            payload = DeviceDashboardService.execute_control(
                self.account,
                device_external_id="mijia:998877",
                control_external_id="mijia:998877:property:power",
                value="off",
            )

        self.assertFalse(payload["snapshot"]["pending_refresh"])
        power_control = next(control for control in payload["snapshot"]["devices"][0]["controls"] if control["key"] == "power")
        self.assertEqual(power_control["value"], "off")
        mocked_request_refresh.assert_not_called()
        mocked_client.set.assert_called_once_with("power", "off")

    def test_refresh_reuses_existing_mijia_controls_when_spec_load_fails(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="mijia",
            auth_payload={"serviceToken": "demo", "ssecurity": "demo", "userId": "demo"},
            is_active=True,
        )
        room = DeviceRoom.objects.create(
            account=self.account,
            slug="mijia:kitchen",
            name="厨房",
            climate="默认家庭",
            summary="来自米家家庭: 默认家庭",
            sort_order=10,
        )
        device = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="mijia:998877",
            room=room,
            name="餐厅灯",
            category="light",
            status=DeviceSnapshot.StatusChoices.ONLINE,
            telemetry="已开启",
            note="旧设备",
            capabilities=["power"],
            sort_order=10,
            source_payload={"did": "998877", "model": "ftd.light.ftdlmp", "name": "餐厅灯"},
        )
        DeviceControl.objects.create(
            account=self.account,
            device=device,
            external_id="mijia:998877:property:power",
            parent_external_id="mijia:998877",
            source_type=DeviceControl.SourceTypeChoices.MIJIA_PROPERTY,
            kind=DeviceControl.KindChoices.TOGGLE,
            key="power",
            label="电源",
            group_label="灯光",
            writable=True,
            value=True,
            action_params={"did": "998877", "property": "power"},
            source_payload={"name": "power"},
            sort_order=10,
        )

        mocked_api = type(
            "MockedMijiaApi",
            (),
            {
                "get_devices_list": lambda self: [
                    {
                        "did": "998877",
                        "model": "ftd.light.ftdlmp",
                        "name": "餐厅灯",
                        "home_id": "1",
                        "room_name": "厨房",
                        "isOnline": True,
                    }
                ],
                "get_homes_list": lambda self: [{"id": "1", "name": "默认家庭"}],
            },
        )()

        with patch(
            "providers.services.MijiaAuthService.get_authenticated_api",
            return_value=mocked_api,
        ), patch(
            "mijiaAPI.get_device_info",
            side_effect=RuntimeError("获取设备型号 'ftd.light.ftdlmp' 的设备信息失败"),
        ):
            payload = DeviceDashboardService.refresh(self.account, trigger="spec-fallback")

        refreshed_device = DeviceSnapshot.objects.get(account=self.account, external_id="mijia:998877")
        controls = list(DeviceControl.objects.filter(account=self.account, device=refreshed_device).order_by("sort_order"))
        self.assertEqual(len(controls), 1)
        self.assertEqual(controls[0].key, "power")
        self.assertEqual(payload["snapshot"]["devices"][0]["controls"][0]["key"], "power")

    def test_single_mijia_refresh_reuses_existing_controls_when_spec_load_fails(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="mijia",
            auth_payload={"serviceToken": "demo", "ssecurity": "demo", "userId": "demo"},
            is_active=True,
        )
        room = DeviceRoom.objects.create(
            account=self.account,
            slug="mijia:kitchen",
            name="厨房",
            climate="默认家庭",
            summary="来自米家家庭: 默认家庭",
            sort_order=10,
        )
        device = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="mijia:998877",
            room=room,
            name="餐厅灯",
            category="light",
            status=DeviceSnapshot.StatusChoices.ONLINE,
            telemetry="已开启",
            note="旧设备",
            capabilities=["power"],
            sort_order=10,
            source_payload={"did": "998877", "model": "ftd.light.ftdlmp", "name": "餐厅灯"},
        )
        DeviceControl.objects.create(
            account=self.account,
            device=device,
            external_id="mijia:998877:property:power",
            parent_external_id="mijia:998877",
            source_type=DeviceControl.SourceTypeChoices.MIJIA_PROPERTY,
            kind=DeviceControl.KindChoices.TOGGLE,
            key="power",
            label="电源",
            group_label="灯光",
            writable=True,
            value=False,
            action_params={"did": "998877", "property": "power"},
            source_payload={"name": "power"},
            sort_order=10,
        )

        with patch(
            "providers.services.MijiaAuthService.get_authenticated_api",
            return_value=object(),
        ), patch("mijiaAPI.mijiaDevice"), patch(
            "mijiaAPI.get_device_info",
            side_effect=RuntimeError("获取设备型号 'ftd.light.ftdlmp' 的设备信息失败"),
        ):
            payload = DeviceDashboardService._refresh_mijia_device(self.account, device=device, trigger="single-refresh")

        refreshed_device = DeviceSnapshot.objects.get(account=self.account, external_id="mijia:998877")
        controls = list(DeviceControl.objects.filter(account=self.account, device=refreshed_device).order_by("sort_order"))
        self.assertEqual(len(controls), 1)
        self.assertEqual(controls[0].key, "power")
        self.assertEqual(payload["snapshot"]["devices"][0]["controls"][0]["key"], "power")

    def test_execute_midea_cloud_control_refreshes_only_target_device(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="midea_cloud",
            auth_payload={"account": "demo@example.com", "password": "secret", "server": 2},
            is_active=True,
        )

        snapshot = build_sample_snapshot(source="midea_cloud")
        snapshot["devices"][0]["id"] = "midea_cloud:998877"
        snapshot["devices"][0]["controls"][0]["id"] = "midea_cloud:998877:power"
        snapshot["devices"][0]["controls"][0]["parent_id"] = "midea_cloud:998877"
        snapshot["devices"][0]["controls"][0]["key"] = "power"
        snapshot["devices"][0]["controls"][0]["action_params"] = {
            "device_id": "998877",
            "actions": [
                {"id": "turn_on", "label": "开启"},
                {"id": "turn_off", "label": "关闭"},
            ],
        }
        snapshot["devices"][0]["source_payload"] = {"id": "998877", "device_id": "998877"}

        refreshed_raw_device = {
            "id": "998877",
            "device_id": "998877",
            "name": "多开门冰箱",
            "room_name": "厨房",
            "home_name": "猛薯之家",
            "device_type": 0xCA,
            "category": "refrigerator",
            "sn8": "12345678",
            "status": "online",
            "status_payload": {
                "power": "off",
                "storage_temperature": 2,
                "_meta": {},
            },
        }

        with patch(
            "devices.services.DeviceDashboardService._build_midea_cloud_snapshot",
            return_value=snapshot,
        ), patch("providers.services.MideaCloudAuthService.get_client") as mocked_get_client, patch(
            "devices.services.DeviceDashboardService.request_refresh"
        ) as mocked_request_refresh:
            mocked_get_client.return_value.execute_control.return_value = None
            mocked_get_client.return_value.get_device.return_value = refreshed_raw_device

            DeviceDashboardService.refresh(self.account, trigger="seed")
            payload = DeviceDashboardService.execute_control(
                self.account,
                device_external_id="midea_cloud:998877",
                control_external_id="midea_cloud:998877:power",
                action="turn_off",
            )

        self.assertFalse(payload["snapshot"]["pending_refresh"])
        power_control = next(control for control in payload["snapshot"]["devices"][0]["controls"] if control["key"] == "power")
        self.assertEqual(power_control["value"], "off")
        mocked_request_refresh.assert_not_called()

    def test_execute_mbapi2020_control_refreshes_only_target_device(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="mbapi2020",
            auth_payload={"account": "driver@example.com", "access_token": "mb-token", "region": "China"},
            is_active=True,
        )

        snapshot = build_sample_snapshot(source="mbapi2020")
        snapshot["devices"][0]["id"] = "mbapi2020:VIN123456"
        snapshot["devices"][0]["controls"][0]["id"] = "mbapi2020:VIN123456:door_lock"
        snapshot["devices"][0]["controls"][0]["parent_id"] = "mbapi2020:VIN123456"
        snapshot["devices"][0]["controls"][0]["key"] = "door_lock"
        snapshot["devices"][0]["controls"][0]["kind"] = DeviceControl.KindChoices.ACTION
        snapshot["devices"][0]["controls"][0]["source_type"] = DeviceControl.SourceTypeChoices.MBAPI2020_ACTION
        snapshot["devices"][0]["controls"][0]["action_params"] = {
            "vehicle_id": "VIN123456",
            "actions": [{"id": "DOORS_LOCK", "label": "锁车"}],
        }
        snapshot["devices"][0]["source_payload"] = {"vin": "VIN123456", "region": "China"}

        refreshed_raw_vehicle = {
            "vin": "VIN123456",
            "name": "EQE SUV",
            "license_plate": "沪A12345",
            "region": "China",
            "pin_available": False,
            "status_payload": {
                "doorlockstatusvehicle": "locked",
                "rangeelectric": 418,
            },
            "command_capabilities": [
                {"commandName": "DOORS_LOCK", "isAvailable": True},
            ],
        }

        with patch(
            "devices.services.DeviceDashboardService._build_mbapi2020_snapshot",
            return_value=snapshot,
        ), patch("providers.services.MbApi2020AuthService.get_client") as mocked_get_client, patch(
            "devices.services.DeviceDashboardService.request_refresh"
        ) as mocked_request_refresh:
            mocked_get_client.return_value.execute_control.return_value = None
            mocked_get_client.return_value.get_device.return_value = refreshed_raw_vehicle

            DeviceDashboardService.refresh(self.account, trigger="seed")
            payload = DeviceDashboardService.execute_control(
                self.account,
                device_external_id="mbapi2020:VIN123456",
                control_external_id="mbapi2020:VIN123456:door_lock",
                action="DOORS_LOCK",
            )

        self.assertFalse(payload["snapshot"]["pending_refresh"])
        action_control = next(control for control in payload["snapshot"]["devices"][0]["controls"] if control["key"] == "door_lock")
        self.assertEqual(action_control["source_type"], DeviceControl.SourceTypeChoices.MBAPI2020_ACTION)
        mocked_request_refresh.assert_not_called()

    def test_syncdevicesnapshot_command_refreshes_target_account(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="home_assistant",
            auth_payload={"base_url": "http://ha.local:8123", "access_token": "ha-token"},
            is_active=True,
        )

        with patch(
            "devices.services.DeviceDashboardService._build_home_assistant_snapshot",
            return_value=build_sample_snapshot(),
        ):
            call_command("syncdevicesnapshot", "--email", self.account.email)

        state = DeviceDashboardState.objects.get(account=self.account, key=DeviceDashboardService.state_key)
        self.assertEqual(state.last_trigger, "command")
        self.assertIsNotNone(state.refreshed_at)

    def test_runworker_processes_each_account(self):
        other_account = Account.objects.create(
            email="device-other@example.com",
            name="Other Device Test",
            password="pwd",
        )

        call_order = []

        def fake_run_pending_refresh(*, account, sync_interval_seconds):
            call_order.append((account.email, sync_interval_seconds))
            return False

        command = RunWorkerCommand()
        with patch.dict(os.environ, {"DEVICE_SYNC_INTERVAL": "300"}, clear=False), patch(
            "devices.management.commands.runworker.Account.objects.all",
            return_value=[self.account, other_account],
        ), patch(
            "django.db.close_old_connections",
            return_value=None,
        ), patch(
            "devices.management.commands.runworker.DeviceDashboardService.run_pending_refresh",
            side_effect=fake_run_pending_refresh,
        ) as run_pending_refresh:
            command.run_iteration(sync_interval=300, block_timeout=1)

        self.assertEqual(run_pending_refresh.call_count, 2)
        self.assertEqual(
            call_order,
            [
                (self.account.email, 300),
                (other_account.email, 300),
            ],
        )

    def test_runworker_consumes_redis_queue_before_scan(self):
        other_account = Account.objects.create(
            email="device-redis@example.com",
            name="Redis Device Test",
            password="pwd",
        )

        call_order = []

        def fake_run_pending_refresh(*, account, sync_interval_seconds):
            call_order.append((account.email, sync_interval_seconds))
            return False

        command = RunWorkerCommand()
        with patch.dict(
            os.environ,
            {
                "DEVICE_SYNC_QUEUE_BACKEND": "redis",
                "DEVICE_SYNC_QUEUE_BLOCK_TIMEOUT": "1",
                "DEVICE_SYNC_INTERVAL": "300",
            },
            clear=False,
        ), patch(
            "devices.management.commands.runworker.dequeue_account_refresh",
            return_value=self.account.id,
        ), patch(
            "devices.management.commands.runworker.Account.objects.all",
            return_value=[self.account, other_account],
        ), patch(
            "django.db.close_old_connections",
            return_value=None,
        ), patch(
            "devices.management.commands.runworker.DeviceDashboardService.run_pending_refresh",
            side_effect=fake_run_pending_refresh,
        ) as run_pending_refresh:
            command.run_iteration(sync_interval=300, block_timeout=1)

        self.assertEqual(run_pending_refresh.call_count, 1)
        self.assertEqual(
            call_order,
            [
                (self.account.email, 300),
            ],
        )

    def test_runworker_skips_full_scan_when_redis_queue_is_idle(self):
        other_account = Account.objects.create(
            email="device-redis-idle@example.com",
            name="Redis Idle Device Test",
            password="pwd",
        )

        command = RunWorkerCommand()
        command._last_scan_at = time.monotonic()

        with patch.dict(
            os.environ,
            {
                "DEVICE_SYNC_QUEUE_BACKEND": "redis",
                "DEVICE_SYNC_QUEUE_BLOCK_TIMEOUT": "1",
                "DEVICE_SYNC_INTERVAL": "300",
            },
            clear=False,
        ), patch(
            "devices.management.commands.runworker.dequeue_account_refresh",
            return_value=None,
        ), patch(
            "devices.management.commands.runworker.Account.objects.all",
            return_value=[self.account, other_account],
        ), patch(
            "django.db.close_old_connections",
            return_value=None,
        ), patch(
            "devices.management.commands.runworker.DeviceDashboardService.run_pending_refresh",
        ) as run_pending_refresh:
            refreshed = command.run_iteration(sync_interval=300, block_timeout=1)

        self.assertEqual(refreshed, 0)
        run_pending_refresh.assert_not_called()


class DeviceDashboardApiTest(TestCase):
    def setUp(self):
        self.env_patcher = patch.dict(os.environ, {"DEVICE_SYNC_QUEUE_BACKEND": "polling"}, clear=False)
        self.env_patcher.start()
        self.account = Account.objects.create(
            email="device-api@example.com",
            name="Device Api Test",
            password="pwd",
        )
        self.dashboard_url = reverse("devices:dashboard")
        self.refresh_url = reverse("devices:dashboard_refresh")
        self.list_url = reverse("devices:device_list")

    def tearDown(self):
        self.env_patcher.stop()

    def test_dashboard_endpoint_returns_pending_snapshot_when_worker_has_not_run(self):
        response = self.client.get(self.dashboard_url, HTTP_X_WANNY_EMAIL=self.account.email)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertFalse(payload["snapshot"]["has_snapshot"])
        self.assertTrue(payload["snapshot"]["pending_refresh"])

    def test_dashboard_endpoint_returns_persisted_snapshot(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="home_assistant",
            auth_payload={"base_url": "http://ha.local:8123", "access_token": "ha-token"},
            is_active=True,
        )
        with patch(
            "devices.services.DeviceDashboardService._build_home_assistant_snapshot",
            return_value=build_sample_snapshot(),
        ):
            DeviceDashboardService.refresh(self.account, trigger="test")

        response = self.client.get(self.dashboard_url, HTTP_X_WANNY_EMAIL=self.account.email)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertTrue(payload["snapshot"]["has_snapshot"])
        self.assertEqual(payload["snapshot"]["rooms"][0]["name"], "厨房")
        self.assertEqual(payload["snapshot"]["devices"][0]["controls"][1]["label"], "冷藏区温度")

    def test_refresh_endpoint_queues_worker_refresh(self):
        response = self.client.post(self.refresh_url, HTTP_X_WANNY_EMAIL=self.account.email)

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload["status"], "accepted")
        self.assertTrue(payload["snapshot"]["pending_refresh"])

        state = DeviceDashboardState.objects.get(account=self.account, key=DeviceDashboardService.state_key)
        self.assertEqual(state.requested_trigger, "api")
        self.assertIsNotNone(state.refresh_requested_at)

    def test_device_list_endpoint_filters_by_multiple_platforms(self):
        room = DeviceRoom.objects.create(
            account=self.account,
            slug="living-room",
            name="客厅",
            climate="",
            summary="",
            sort_order=10,
        )
        DeviceSnapshot.objects.create(
            account=self.account,
            external_id="mijia:light-1",
            room=room,
            name="米家台灯",
            category="灯光",
            status="online",
            telemetry="在线",
            sort_order=10,
        )
        DeviceSnapshot.objects.create(
            account=self.account,
            external_id="home_assistant:ac-1",
            room=room,
            name="HA 空调",
            category="空调",
            status="online",
            telemetry="制冷",
            sort_order=20,
        )
        DeviceSnapshot.objects.create(
            account=self.account,
            external_id="unknown:device-1",
            room=room,
            name="未知设备",
            category="其他设备",
            status="offline",
            telemetry="离线",
            sort_order=30,
        )

        response = self.client.get(
            f"{self.list_url}?platforms=mijia&platforms=home_assistant",
            HTTP_X_WANNY_EMAIL=self.account.email,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["pagination"]["total"], 2)
        self.assertEqual([device["id"] for device in payload["devices"]], ["mijia:light-1", "home_assistant:ac-1"])

    def test_device_list_endpoint_sorts_hisense_after_mbapi2020_before_unknown(self):
        room = DeviceRoom.objects.create(
            account=self.account,
            slug="study",
            name="书房",
            climate="",
            summary="",
            sort_order=10,
        )
        DeviceSnapshot.objects.create(
            account=self.account,
            external_id="mbapi2020:VIN001",
            room=room,
            name="奔驰",
            category="汽车",
            status="online",
            telemetry="在线",
            sort_order=0,
        )
        DeviceSnapshot.objects.create(
            account=self.account,
            external_id="hisense_ha:ac-1",
            room=room,
            name="海信空调",
            category="空调",
            status="online",
            telemetry="制冷",
            sort_order=0,
        )
        DeviceSnapshot.objects.create(
            account=self.account,
            external_id="unknown:device-1",
            room=room,
            name="未知设备",
            category="其他",
            status="online",
            telemetry="在线",
            sort_order=0,
        )

        response = self.client.get(self.list_url, HTTP_X_WANNY_EMAIL=self.account.email)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            [device["id"] for device in payload["devices"][:3]],
            ["mbapi2020:VIN001", "hisense_ha:ac-1", "unknown:device-1"],
        )

    def test_device_list_endpoint_sorts_by_manual_order_first(self):
        room = DeviceRoom.objects.create(
            account=self.account,
            slug="bedroom",
            name="卧室",
            climate="",
            summary="",
            sort_order=10,
        )
        enabled_mijia = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="mijia:light-enabled",
            room=room,
            name="米家启用灯",
            category="灯光",
            status="online",
            telemetry="在线",
            sort_order=30,
        )
        disabled_home_assistant = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="home_assistant:light-disabled",
            room=room,
            name="HA 未启用灯",
            category="灯光",
            status="online",
            telemetry="在线",
            sort_order=10,
        )
        attention_home_assistant = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="home_assistant:fan-attention",
            room=room,
            name="HA 风扇",
            category="风扇",
            status="attention",
            telemetry="需留意",
            sort_order=20,
        )
        offline_mijia = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="mijia:plug-offline",
            room=room,
            name="米家插座",
            category="开关",
            status="offline",
            telemetry="离线",
            sort_order=40,
        )

        DeviceControl.objects.create(
            account=self.account,
            device=enabled_mijia,
            external_id="mijia:light-enabled:power",
            source_type=DeviceControl.SourceTypeChoices.MIJIA_PROPERTY,
            kind=DeviceControl.KindChoices.TOGGLE,
            key="power",
            label="电源",
            writable=True,
            value="on",
        )
        DeviceControl.objects.create(
            account=self.account,
            device=disabled_home_assistant,
            external_id="home_assistant:light-disabled:power",
            source_type=DeviceControl.SourceTypeChoices.HA_ENTITY,
            kind=DeviceControl.KindChoices.TOGGLE,
            key="switch.light_disabled",
            label="电源",
            writable=True,
            value="off",
        )

        response = self.client.get(self.list_url, HTTP_X_WANNY_EMAIL=self.account.email)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            [device["id"] for device in payload["devices"]],
            [
                "home_assistant:light-disabled",
                "home_assistant:fan-attention",
                "mijia:light-enabled",
                "mijia:plug-offline",
            ],
        )

    def test_device_list_reorder_endpoint_updates_sort_order(self):
        room = DeviceRoom.objects.create(
            account=self.account,
            slug="reorder-room",
            name="排序房间",
            climate="",
            summary="",
            sort_order=10,
        )
        first = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="mijia:first",
            room=room,
            name="第一台",
            category="灯光",
            status="online",
            telemetry="在线",
            sort_order=10,
        )
        second = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="mijia:second",
            room=room,
            name="第二台",
            category="灯光",
            status="online",
            telemetry="在线",
            sort_order=20,
        )
        third = DeviceSnapshot.objects.create(
            account=self.account,
            external_id="mijia:third",
            room=room,
            name="第三台",
            category="灯光",
            status="online",
            telemetry="在线",
            sort_order=30,
        )

        response = self.client.post(
            reverse("devices:device_list_reorder"),
            data=json.dumps({"device_ids": [third.external_id, first.external_id]}),
            content_type="application/json",
            HTTP_X_WANNY_EMAIL=self.account.email,
        )

        self.assertEqual(response.status_code, 200)
        ordered_ids = list(
            DeviceSnapshot.objects.filter(account=self.account)
            .order_by("sort_order", "id")
            .values_list("external_id", flat=True)
        )
        self.assertEqual(ordered_ids, [third.external_id, second.external_id, first.external_id])

    def test_control_endpoint_executes_action(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="home_assistant",
            auth_payload={"base_url": "http://ha.local:8123", "access_token": "ha-token"},
            is_active=True,
        )

        with patch(
            "devices.services.DeviceDashboardService._build_home_assistant_snapshot",
            side_effect=[build_sample_snapshot(), build_sample_snapshot()],
        ), patch("devices.services.requests.post") as requests_post:
            requests_post.return_value.raise_for_status.return_value = None
            DeviceDashboardService.refresh(self.account, trigger="seed")

            url = reverse(
                "devices:device_control",
                kwargs={
                    "device_id": "home_assistant:kitchen:fridge",
                    "control_id": "home_assistant:switch.fridge_power",
                },
            )
            response = self.client.post(
                url,
                data='{"action":"turn_off"}',
                content_type="application/json",
                HTTP_X_WANNY_EMAIL=self.account.email,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        requests_post.assert_called_once()
