from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.models import Account
from care.models import CareSuggestion
from care.services.push import CarePushService
from devices.models import DeviceSnapshot
from memory.models import ProactiveLog


@pytest.mark.django_db
def test_select_due_suggestions_limits_to_three_and_skips_low_priority():
    account = Account.objects.create(email="care-push@example.com", name="care-push", password="x")
    device = DeviceSnapshot.objects.create(
        account=account,
        external_id="device-1",
        name="测试设备",
        category="sensor",
        status=DeviceSnapshot.StatusChoices.ONLINE,
    )

    for idx, priority in enumerate([8.2, 7.4, 6.0, 5.5, 3.0], start=1):
        CareSuggestion.objects.create(
            account=account,
            suggestion_type=CareSuggestion.SuggestionTypeChoices.CARE,
            device=device,
            title=f"建议 {idx}",
            body="body",
            priority=priority,
            dedupe_key=f"push:{idx}",
        )

    selected = CarePushService._select_due_suggestions(account)

    assert len(selected) == 3
    assert [item.title for item in selected] == ["建议 1", "建议 2", "建议 3"]


@pytest.mark.django_db
def test_select_due_suggestions_blocks_medium_priority_when_recent_medium_push_exists():
    account = Account.objects.create(email="care-push-medium@example.com", name="care-push-medium", password="x")
    device = DeviceSnapshot.objects.create(
        account=account,
        external_id="device-2",
        name="测试设备",
        category="sensor",
        status=DeviceSnapshot.StatusChoices.ONLINE,
    )
    CareSuggestion.objects.create(
        account=account,
        suggestion_type=CareSuggestion.SuggestionTypeChoices.CARE,
        device=device,
        title="中优先级建议",
        body="body",
        priority=6.2,
        dedupe_key="push:medium",
    )
    ProactiveLog.objects.create(
        account=account,
        message="已推送",
        feedback=ProactiveLog.FeedbackChoices.PENDING,
        score=6.2,
        source="care:push",
    )

    selected = CarePushService._select_due_suggestions(account)

    assert selected == []


@pytest.mark.django_db
def test_select_due_suggestions_blocks_recently_ignored_item_for_48_hours():
    account = Account.objects.create(email="care-push-ignore@example.com", name="care-push-ignore", password="x")
    device = DeviceSnapshot.objects.create(
        account=account,
        external_id="device-3",
        name="测试设备",
        category="sensor",
        status=DeviceSnapshot.StatusChoices.ONLINE,
    )
    CareSuggestion.objects.create(
        account=account,
        suggestion_type=CareSuggestion.SuggestionTypeChoices.CARE,
        device=device,
        title="忽略后的提醒",
        body="body",
        priority=8.4,
        dedupe_key="push:ignore",
        status=CareSuggestion.StatusChoices.PENDING,
        user_feedback={"action": "ignore"},
        feedback_collected_at=timezone.now() - timedelta(hours=12),
    )

    selected = CarePushService._select_due_suggestions(account)

    assert selected == []
