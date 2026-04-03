"""
模拟天气骤降后生成主动关怀建议。

运行方式：
    cd backend
    uv run python tests/scripts/care/simulate_weather_change.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch


TEMP_DIR = tempfile.TemporaryDirectory(prefix="wanny-care-weather-")
BACKEND_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "apps"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wanny_server.settings")
os.environ["DB_ENGINE"] = "django.db.backends.sqlite3"
os.environ["DB_NAME"] = str(Path(TEMP_DIR.name) / "care_weather.sqlite3")

import django

django.setup()

from django.core.management import call_command

from accounts.models import Account
from care.models import ExternalDataSource
from care.services.processor import CareEventProcessor
from care.services.weather import WeatherDataService
from devices.models import DeviceControl, DeviceSnapshot


def main() -> int:
    print("Step 1: 初始化数据库...")
    call_command("migrate", verbosity=0, interactive=False)

    print("Step 2: 创建账户、空调设备和天气源...")
    account = Account.objects.create(
        email="care-weather-script@example.com",
        name="care-weather-script",
        password="pwd",
    )
    device = DeviceSnapshot.objects.create(
        account=account,
        external_id="ha:climate.living_room",
        name="客厅空调",
        category="climate",
        status=DeviceSnapshot.StatusChoices.ONLINE,
    )
    DeviceControl.objects.create(
        account=account,
        device=device,
        external_id="ha:climate.living_room:target_temperature",
        source_type=DeviceControl.SourceTypeChoices.HA_ENTITY,
        kind=DeviceControl.KindChoices.RANGE,
        key="target_temperature",
        label="目标温度",
        writable=True,
        value=24,
        unit="°C",
    )
    source = ExternalDataSource.objects.create(
        account=account,
        source_type=ExternalDataSource.SourceTypeChoices.WEATHER_API,
        name="Open-Meteo",
        config={
            "provider": "open_meteo",
            "endpoint": "https://api.open-meteo.com/v1/forecast",
            "latitude": 31.23,
            "longitude": 121.47,
            "timezone": "Asia/Shanghai",
            "drop_threshold": 8,
        },
        last_data={
            "provider": "open_meteo",
            "temperature": 24.0,
            "condition": "sunny",
            "fetched_at": "2026-04-04 09:00:00",
            "raw": {"current": {"temperature_2m": 24.0, "weather_code": 0}},
        },
    )

    print("Step 3: 模拟天气接口返回降温数据...")
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "current": {
            "temperature_2m": 12.0,
            "weather_code": 61,
        }
    }
    with patch("care.services.weather.requests.get", return_value=response):
        source = WeatherDataService.fetch_source(source)

    suggestion = CareEventProcessor.process_weather_source(source)
    if suggestion is None:
        raise AssertionError("天气骤降后没有生成建议")

    print("Step 4: 输出建议结果...")
    print("  标题:", suggestion.title)
    print("  内容:", suggestion.body)
    print("  优先级:", suggestion.priority)
    print("  动作:", suggestion.action_spec)
    print("\nPASS: 天气骤降模拟成功。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        TEMP_DIR.cleanup()
