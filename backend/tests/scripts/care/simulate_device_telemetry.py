"""
模拟设备遥测命中巡检规则。

运行方式：
    cd backend
    uv run python tests/scripts/care/simulate_device_telemetry.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


TEMP_DIR = tempfile.TemporaryDirectory(prefix="wanny-care-telemetry-")
BACKEND_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "apps"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wanny_server.settings")
os.environ["DB_ENGINE"] = "django.db.backends.sqlite3"
os.environ["DB_NAME"] = str(Path(TEMP_DIR.name) / "care_telemetry.sqlite3")

import django

django.setup()

from django.core.management import call_command

from accounts.models import Account
from care.models import InspectionRule
from care.services.scanner import InspectionScanner
from devices.models import DeviceControl, DeviceSnapshot


def main() -> int:
    print("Step 1: 初始化数据库...")
    call_command("migrate", verbosity=0, interactive=False)

    print("Step 2: 创建设备遥测和巡检规则...")
    account = Account.objects.create(
        email="care-telemetry-script@example.com",
        name="care-telemetry-script",
        password="pwd",
    )
    device = DeviceSnapshot.objects.create(
        account=account,
        external_id="mijia:purifier-1",
        name="净水器",
        category="water_purifier",
        status=DeviceSnapshot.StatusChoices.ONLINE,
    )
    DeviceControl.objects.create(
        account=account,
        device=device,
        external_id="mijia:purifier-1:filter_life_percent",
        source_type=DeviceControl.SourceTypeChoices.MIJIA_PROPERTY,
        kind=DeviceControl.KindChoices.SENSOR,
        key="filter_life_percent",
        label="滤芯寿命",
        value=9,
        unit="%",
    )
    InspectionRule.objects.create(
        account=account,
        rule_type=InspectionRule.RuleTypeChoices.MAINTENANCE,
        device_category="water_purifier",
        name="滤芯更换提醒",
        description="滤芯寿命过低时提醒更换。",
        condition_spec={
            "field": "control.filter_life_percent",
            "operator": "<",
            "threshold": 20,
        },
        suggestion_template="{device_name} 需要更换滤芯。",
        priority=8,
        cooldown_hours=24,
    )

    print("Step 3: 执行巡检扫描...")
    created = InspectionScanner.scan_account(account)
    if len(created) != 1:
        raise AssertionError(f"预期生成 1 条建议，实际为 {len(created)}")

    suggestion = created[0]
    print("  标题:", suggestion.title)
    print("  内容:", suggestion.body)
    print("  优先级:", suggestion.priority)
    print("  聚合键:", suggestion.dedupe_key)
    print("\nPASS: 设备遥测模拟成功。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        TEMP_DIR.cleanup()
