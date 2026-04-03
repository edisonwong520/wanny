"""
简单压测主动关怀聚合器。

运行方式：
    cd backend
    uv run python tests/scripts/care/benchmark_aggregator.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path


TEMP_DIR = tempfile.TemporaryDirectory(prefix="wanny-care-agg-")
BACKEND_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "apps"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wanny_server.settings")
os.environ["DB_ENGINE"] = "django.db.backends.sqlite3"
os.environ["DB_NAME"] = str(Path(TEMP_DIR.name) / "care_aggregator.sqlite3")

import django

django.setup()

from django.core.management import call_command

from accounts.models import Account
from care.models import CareSuggestion
from care.services.aggregator import SuggestionAggregator
from devices.models import DeviceControl, DeviceSnapshot


def main() -> int:
    print("Step 1: 初始化数据库...")
    call_command("migrate", verbosity=0, interactive=False)

    print("Step 2: 准备账户、设备和控制项...")
    account = Account.objects.create(
        email="care-benchmark@example.com",
        name="care-benchmark",
        password="pwd",
    )
    device = DeviceSnapshot.objects.create(
        account=account,
        external_id="benchmark-device-1",
        name="压测设备",
        category="sensor",
        status=DeviceSnapshot.StatusChoices.ONLINE,
    )
    control = DeviceControl.objects.create(
        account=account,
        device=device,
        external_id="benchmark-device-1:filter_life_percent",
        source_type=DeviceControl.SourceTypeChoices.MIJIA_PROPERTY,
        kind=DeviceControl.KindChoices.SENSOR,
        key="filter_life_percent",
        label="滤芯寿命",
        value=9,
        unit="%",
    )

    iterations = 1000
    print(f"Step 3: 连续调用聚合器 {iterations} 次...")
    start = time.perf_counter()
    for idx in range(iterations):
        SuggestionAggregator.upsert(
            account=account,
            dedupe_key="benchmark:device-1:filter",
            cooldown_hours=24,
            aggregation_marker=idx,
            defaults={
                "account": account,
                "suggestion_type": CareSuggestion.SuggestionTypeChoices.INSPECTION,
                "device": device,
                "control_target": control,
                "title": "滤芯寿命过低",
                "body": "压测建议体。",
                "action_spec": {},
                "priority": 8.0,
                "dedupe_key": "benchmark:device-1:filter",
                "source_event": {"current_value": 9, "threshold": 20},
            },
        )
    elapsed = time.perf_counter() - start

    suggestion = CareSuggestion.objects.get(account=account, dedupe_key="benchmark:device-1:filter")
    print("  总耗时:", f"{elapsed:.4f}s")
    print("  单次平均:", f"{elapsed / iterations * 1000:.4f}ms")
    print("  聚合数量:", suggestion.aggregated_count)
    print("  来源标记数:", len(suggestion.aggregated_from))
    print("\nPASS: 聚合器压测完成。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        TEMP_DIR.cleanup()
