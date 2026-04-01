"""
验证 Home Assistant 冰箱冷藏区温度控制链路是否生效。

脚本会：
1. 使用临时 SQLite 数据库初始化 Django；
2. 注入一份模拟的 HA 冰箱设备图谱；
3. 刷新本地设备快照，确认已经生成“冷藏区温度”范围控制；
4. 执行把多开门冰箱冷藏区温度改为 2 度；
5. 校验 HA 下发请求是否命中 `number.set_value`，以及刷新后的控制值是否变成 2。

运行方式：
    cd backend
    uv run python tests/scripts/verify_ha_fridge_temperature_control.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch


TEMP_DIR = tempfile.TemporaryDirectory(prefix="wanny-ha-fridge-")
BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "apps"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wanny_server.settings")
os.environ["DB_ENGINE"] = "django.db.backends.sqlite3"
os.environ["DB_NAME"] = str(Path(TEMP_DIR.name) / "ha_fridge_control.sqlite3")

import django

django.setup()

from django.core.management import call_command

from accounts.models import Account
from devices.models import DeviceControl
from devices.services import DeviceDashboardService
from providers.models import PlatformAuth


def build_ha_graph(target_temperature: int) -> tuple[dict, list[dict], dict]:
    config = {
        "location_name": "My Home",
        "time_zone": "Asia/Shanghai",
        "unit_system": {"temperature": "C"},
    }
    states = [
        {
            "entity_id": "switch.fridge_power",
            "state": "on",
            "attributes": {
                "friendly_name": "多开门冰箱 总电源",
            },
        },
        {
            "entity_id": "number.fridge_refrigerator_target_temperature",
            "state": str(target_temperature),
            "attributes": {
                "friendly_name": "多开门冰箱 冷藏区温度",
                "min": 2,
                "max": 8,
                "step": 1,
                "unit_of_measurement": "°C",
            },
        },
        {
            "entity_id": "sensor.fridge_refrigerator_temperature",
            "state": str(target_temperature),
            "attributes": {
                "friendly_name": "多开门冰箱 冷藏区当前温度",
                "unit_of_measurement": "°C",
            },
        },
        {
            "entity_id": "sensor.fridge_freezer_temperature",
            "state": "-18",
            "attributes": {
                "friendly_name": "多开门冰箱 冷冻区温度",
                "unit_of_measurement": "°C",
            },
        },
    ]
    registry = {
        "areas": [
            {"area_id": "kitchen", "name": "厨房"},
        ],
        "devices": [
            {"id": "device-fridge", "area_id": "kitchen", "name": "多开门冰箱"},
        ],
        "entities": [
            {"entity_id": "switch.fridge_power", "device_id": "device-fridge"},
            {"entity_id": "number.fridge_refrigerator_target_temperature", "device_id": "device-fridge"},
            {"entity_id": "sensor.fridge_refrigerator_temperature", "device_id": "device-fridge"},
            {"entity_id": "sensor.fridge_freezer_temperature", "device_id": "device-fridge"},
        ],
    }
    return config, states, registry


def assert_equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected={expected!r}, actual={actual!r}")


def main() -> int:
    print("Step 1: 初始化临时数据库并执行迁移...")
    call_command("migrate", verbosity=0, interactive=False)

    print("Step 2: 创建测试账户和 Home Assistant 授权...")
    Account.objects.filter(email="ha-fridge-script@example.com").delete()
    account = Account.objects.create(
        email="ha-fridge-script@example.com",
        name="HA Fridge Script",
        password="pwd",
    )
    PlatformAuth.objects.create(
        account=account,
        platform_name="ha",
        auth_payload={
            "base_url": "http://ha.local:8123",
            "access_token": "ha-token",
        },
        is_active=True,
    )

    initial_graph = build_ha_graph(target_temperature=4)
    refreshed_graph = build_ha_graph(target_temperature=2)

    print("Step 3: 刷新设备快照，确认生成冷藏区温控项...")
    with patch("providers.services.HomeAssistantAuthService.get_graph", return_value=deepcopy(initial_graph)):
        dashboard = DeviceDashboardService.refresh(account, trigger="script-seed")

    devices = dashboard["snapshot"]["devices"]
    fridge = next((device for device in devices if device["name"] == "多开门冰箱"), None)
    if fridge is None:
        raise AssertionError("未找到名为“多开门冰箱”的设备")

    control = next(
        (
            item
            for item in fridge["controls"]
            if item["group_label"] == "冷藏区"
            and item["kind"] == DeviceControl.KindChoices.RANGE
            and item["writable"]
        ),
        None,
    )
    if control is None:
        raise AssertionError("未找到可写的“冷藏区”温度控制项")

    assert_equal(control["value"], 4.0, "初始冷藏区温度控件值不正确")
    assert_equal(control["action_params"]["service_domain"], "number", "service_domain 不正确")
    assert_equal(control["action_params"]["service"], "set_value", "service 不正确")
    assert_equal(control["action_params"]["value_field"], "value", "value_field 不正确")
    assert_equal(
        control["action_params"]["entity_id"],
        "number.fridge_refrigerator_target_temperature",
        "entity_id 不正确",
    )
    print("  已识别到可写控件:", control["label"], control["value"], control["unit"])

    print("Step 4: 执行把多开门冰箱冷藏区温度调整到 2°C ...")
    with patch(
        "providers.services.HomeAssistantAuthService.get_graph",
        side_effect=[deepcopy(refreshed_graph)],
    ), patch("devices.services.requests.post") as requests_post:
        requests_post.return_value.raise_for_status.return_value = None
        payload = DeviceDashboardService.execute_control(
            account,
            device_external_id=fridge["id"],
            control_external_id=control["id"],
            value=2,
        )

    requests_post.assert_called_once()
    call_args = requests_post.call_args
    request_url = call_args.args[0]
    request_headers = call_args.kwargs["headers"]
    request_json = call_args.kwargs["json"]

    assert_equal(
        request_url,
        "http://ha.local:8123/api/services/number/set_value",
        "HA 请求 URL 不正确",
    )
    assert_equal(request_headers["Authorization"], "Bearer ha-token", "HA 鉴权头不正确")
    assert_equal(
        request_json,
        {"entity_id": "number.fridge_refrigerator_target_temperature", "value": 2},
        "HA 请求体不正确",
    )

    updated_fridge = next(
        (device for device in payload["snapshot"]["devices"] if device["name"] == "多开门冰箱"),
        None,
    )
    if updated_fridge is None:
        raise AssertionError("控制执行后未找到刷新后的冰箱设备")

    updated_control = next(
        (
            item
            for item in updated_fridge["controls"]
            if item["id"] == control["id"]
        ),
        None,
    )
    if updated_control is None:
        raise AssertionError("控制执行后未找到刷新后的冷藏区温度控件")

    assert_equal(updated_control["value"], 2.0, "刷新后的冷藏区温度不是 2°C")

    print("Step 5: 校验通过。")
    print("  HA URL:", request_url)
    print("  HA Body:", request_json)
    print("  刷新后控件值:", updated_control["value"], updated_control["unit"])
    print("\nPASS: HA 冰箱冷藏区温度控制逻辑生效。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        TEMP_DIR.cleanup()
