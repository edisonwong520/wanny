from asgiref.sync import async_to_sync
import pytest

from accounts.models import Account
from care.models import CareSuggestion
from care.services.push import CarePushService
from devices.models import DeviceSnapshot
from memory.models import ProactiveLog
from providers.models import PlatformAuth


class FakeBot:
    def __init__(self):
        self._context_tokens = {"wx-care-user": "token"}
        self.sent = []

    async def send(self, user_id, text):
        self.sent.append((user_id, text))


@pytest.mark.django_db
def test_care_push_service_sends_due_suggestions_to_wechat():
    account = Account.objects.create(email="care-push-flow@example.com", name="care-push-flow", password="x")
    PlatformAuth.objects.create(
        account=account,
        platform_name="wechat",
        is_active=True,
        auth_payload={"user_id": "wx-care-user"},
    )
    device = DeviceSnapshot.objects.create(
        account=account,
        external_id="device-push-1",
        name="客厅空调",
        category="climate",
        status=DeviceSnapshot.StatusChoices.ONLINE,
    )
    suggestion = CareSuggestion.objects.create(
        account=account,
        suggestion_type=CareSuggestion.SuggestionTypeChoices.CARE,
        device=device,
        title="天气转凉，建议调高空调温度",
        body="外部温度下降较快，建议提高空调目标温度。",
        priority=8.1,
        dedupe_key="care-push-flow-1",
    )

    bot = FakeBot()
    pushed = async_to_sync(CarePushService.deliver_due_suggestions)(bot=bot)

    assert pushed == 1
    assert bot.sent
    suggestion.refresh_from_db()
    assert suggestion.user_feedback["push"]["count"] == 1
    assert ProactiveLog.objects.filter(account=account, source="care:push").exists()


@pytest.mark.django_db
def test_care_push_service_sends_without_active_context_tokens():
    account = Account.objects.create(email="care-push-no-context@example.com", name="care-push-no-context", password="x")
    PlatformAuth.objects.create(
        account=account,
        platform_name="wechat",
        is_active=True,
        auth_payload={"user_id": "wx-care-user"},
    )
    CareSuggestion.objects.create(
        account=account,
        suggestion_type=CareSuggestion.SuggestionTypeChoices.CARE,
        title="天气提醒",
        body="body",
        priority=8.3,
        dedupe_key="care-push-flow-no-context",
    )

    bot = FakeBot()
    bot._context_tokens = {}
    pushed = async_to_sync(CarePushService.deliver_due_suggestions)(bot=bot)

    assert pushed == 1
    assert bot.sent
