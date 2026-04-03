"""
模拟主动关怀微信推送。

运行方式：
    cd backend
    uv run python tests/scripts/care/test_push_notification.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from asgiref.sync import async_to_sync


TEMP_DIR = tempfile.TemporaryDirectory(prefix="wanny-care-push-")
BACKEND_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "apps"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wanny_server.settings")
os.environ["DB_ENGINE"] = "django.db.backends.sqlite3"
os.environ["DB_NAME"] = str(Path(TEMP_DIR.name) / "care_push.sqlite3")

import django

django.setup()

from django.core.management import call_command

from accounts.models import Account
from care.models import CareSuggestion
from care.services.push import CarePushService
from devices.models import DeviceSnapshot
from providers.models import PlatformAuth


class FakeBot:
    def __init__(self):
        self._context_tokens = {"wx-care-script-user": "token"}
        self.sent: list[tuple[str, str]] = []

    async def send(self, user_id: str, text: str):
        self.sent.append((user_id, text))


def main() -> int:
    print("Step 1: 初始化数据库...")
    call_command("migrate", verbosity=0, interactive=False)

    print("Step 2: 创建账号、微信授权和关怀建议...")
    account = Account.objects.create(
        email="care-push-script@example.com",
        name="care-push-script",
        password="pwd",
    )
    PlatformAuth.objects.create(
        account=account,
        platform_name="wechat",
        is_active=True,
        auth_payload={"user_id": "wx-care-script-user"},
    )
    device = DeviceSnapshot.objects.create(
        account=account,
        external_id="ha:climate.study",
        name="书房空调",
        category="climate",
        status=DeviceSnapshot.StatusChoices.ONLINE,
    )
    CareSuggestion.objects.create(
        account=account,
        suggestion_type=CareSuggestion.SuggestionTypeChoices.CARE,
        device=device,
        title="天气转凉，建议调高书房空调温度",
        body="外部温度下降较快，建议把目标温度上调 1°C。",
        priority=8.2,
        dedupe_key="care-push-script-1",
    )

    print("Step 3: 执行推送...")
    bot = FakeBot()
    pushed = async_to_sync(CarePushService.deliver_due_suggestions)(bot=bot)
    if pushed != 1 or not bot.sent:
        raise AssertionError("推送未成功发出")

    user_id, message = bot.sent[0]
    print("  用户:", user_id)
    print("  消息:")
    print(message)
    print("\nPASS: 主动关怀推送模拟成功。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        TEMP_DIR.cleanup()
