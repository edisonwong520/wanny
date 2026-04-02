import os
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from accounts.models import Account
from providers.models import PlatformAuth

from .models import DeviceControl, DeviceDashboardState, DeviceRoom, DeviceSnapshot
from .services import DeviceDashboardService


def build_sample_snapshot(source: str = "home_assistant") -> dict:
    source_type_map = {
        "home_assistant": "ha_entity",
        "midea_cloud": "midea_cloud_property",
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
        self.account = Account.objects.create(
            email="device-test@example.com",
            name="Device Test",
            password="pwd",
        )

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

    def test_run_pending_refresh_persists_snapshot_and_clears_pending(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="home_assistant",
            auth_payload={"base_url": "http://ha.local:8123", "access_token": "ha-token"},
            is_active=True,
        )
        DeviceDashboardService.request_refresh(self.account, trigger="manual")

        with patch(
            "devices.services.DeviceDashboardService._build_home_assistant_snapshot",
            return_value=build_sample_snapshot(),
        ):
            refreshed = DeviceDashboardService.run_pending_refresh(self.account, sync_interval_seconds=300)

        self.assertTrue(refreshed)
        payload = DeviceDashboardService.get_dashboard(self.account)
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
        self.assertIn("power", control_keys)
        self.assertIn("hvac_mode", control_keys)
        self.assertIn("target_temperature", control_keys)
        power_control = next(control for control in snapshot["devices"][0]["controls"] if control["key"] == "power")
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

    def test_execute_control_refreshes_snapshot_after_action(self):
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
        refreshed_snapshot = build_sample_snapshot()
        refreshed_snapshot["devices"][0]["controls"][0]["value"] = "off"

        with patch(
            "devices.services.DeviceDashboardService._build_home_assistant_snapshot",
            side_effect=[initial_snapshot, refreshed_snapshot],
        ), patch("devices.services.requests.post") as requests_post:
            requests_post.return_value.raise_for_status.return_value = None
            DeviceDashboardService.refresh(self.account, trigger="seed")
            payload = DeviceDashboardService.execute_control(
                self.account,
                device_external_id="home_assistant:kitchen:fridge",
                control_external_id="home_assistant:switch.fridge_power",
                action="turn_off",
            )

        self.assertEqual(payload["snapshot"]["devices"][0]["controls"][0]["value"], "off")
        requests_post.assert_called_once()

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

        class LoopExit(Exception):
            pass

        call_order = []

        def fake_run_pending_refresh(*, account, sync_interval_seconds):
            call_order.append((account.email, sync_interval_seconds))
            return False

        with patch.dict(os.environ, {"DEVICE_SYNC_INTERVAL": "300"}, clear=False), patch(
            "devices.management.commands.runworker.Account.objects.all",
            return_value=[self.account, other_account],
        ), patch(
            "django.db.close_old_connections",
            return_value=None,
        ), patch(
            "devices.management.commands.runworker.DeviceDashboardService.run_pending_refresh",
            side_effect=fake_run_pending_refresh,
        ) as run_pending_refresh, patch(
            "devices.management.commands.runworker.time.sleep",
            side_effect=LoopExit,
        ):
            with self.assertRaises(LoopExit):
                call_command("runworker")

        self.assertEqual(run_pending_refresh.call_count, 2)
        self.assertEqual(
            call_order,
            [
                (self.account.email, 300),
                (other_account.email, 300),
            ],
        )


class DeviceDashboardApiTest(TestCase):
    def setUp(self):
        self.account = Account.objects.create(
            email="device-api@example.com",
            name="Device Api Test",
            password="pwd",
        )
        self.dashboard_url = reverse("devices:dashboard")
        self.refresh_url = reverse("devices:dashboard_refresh")
        self.list_url = reverse("devices:device_list")

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
        self.assertEqual([device["id"] for device in payload["devices"]], ["home_assistant:ac-1", "mijia:light-1"])

    def test_device_list_endpoint_sorts_by_status_then_enabled_then_platform(self):
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
                "mijia:light-enabled",
                "home_assistant:light-disabled",
                "home_assistant:fan-attention",
                "mijia:plug-offline",
            ],
        )

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
