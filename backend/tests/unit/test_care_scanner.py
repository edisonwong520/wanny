import pytest

from accounts.models import Account
from care.defaults import seed_system_rules
from care.models import CareSuggestion, InspectionRule
from care.services.learner import FeedbackLearner
from care.services.scanner import InspectionScanner
from devices.models import DeviceControl, DeviceSnapshot
from memory.models import ProactiveLog


@pytest.mark.django_db
def test_inspection_scanner_creates_suggestion_for_low_filter_life():
    account = Account.objects.create(email="care-scan@example.com", name="care-scan", password="x")
    device = DeviceSnapshot.objects.create(
        account=account,
        external_id="mijia:device-1",
        name="饮水机",
        category="water_purifier",
        status=DeviceSnapshot.StatusChoices.ONLINE,
    )
    control = DeviceControl.objects.create(
        account=account,
        device=device,
        external_id="mijia:device-1:filter",
        source_type=DeviceControl.SourceTypeChoices.MIJIA_PROPERTY,
        kind=DeviceControl.KindChoices.SENSOR,
        key="filter_life_percent",
        label="滤芯寿命",
        value=12,
        unit="%",
    )
    rule = InspectionRule.objects.create(
        account=account,
        rule_type=InspectionRule.RuleTypeChoices.MAINTENANCE,
        device_category="water_purifier",
        name="滤芯更换提醒",
        description="建议尽快检查滤芯状态。",
        condition_spec={"field": "control.filter_life_percent", "operator": "<", "threshold": 20},
        suggestion_template="{device_name} 的 {control_label} 仅剩 {current_value}，建议处理。",
        priority=8,
    )

    created = InspectionScanner.scan_account(account)

    assert len(created) == 1
    suggestion = created[0]
    assert suggestion.source_rule == rule
    assert suggestion.device == device
    assert suggestion.control_target == control
    assert suggestion.status == CareSuggestion.StatusChoices.PENDING
    assert suggestion.priority >= 8
    assert "滤芯寿命" in suggestion.title


@pytest.mark.django_db
def test_inspection_scanner_respects_cooldown_dedupe():
    account = Account.objects.create(email="care-dedupe@example.com", name="care-dedupe", password="x")
    device = DeviceSnapshot.objects.create(
        account=account,
        external_id="mijia:device-2",
        name="净水器",
        category="water_purifier",
        status=DeviceSnapshot.StatusChoices.ONLINE,
    )
    DeviceControl.objects.create(
        account=account,
        device=device,
        external_id="mijia:device-2:filter",
        source_type=DeviceControl.SourceTypeChoices.MIJIA_PROPERTY,
        kind=DeviceControl.KindChoices.SENSOR,
        key="filter_life_percent",
        label="滤芯寿命",
        value=10,
        unit="%",
    )
    InspectionRule.objects.create(
        account=account,
        rule_type=InspectionRule.RuleTypeChoices.MAINTENANCE,
        device_category="water_purifier",
        name="滤芯更换提醒",
        condition_spec={"field": "control.filter_life_percent", "operator": "<", "threshold": 20},
        suggestion_template="{device_name} 需要更换滤芯。",
        cooldown_hours=24,
    )

    assert len(InspectionScanner.scan_account(account)) == 1
    assert len(InspectionScanner.scan_account(account)) == 0
    assert CareSuggestion.objects.filter(account=account).count() == 1


@pytest.mark.django_db
def test_seed_system_rules_is_idempotent():
    first = seed_system_rules()
    second = seed_system_rules()

    assert first == second
    assert InspectionRule.objects.filter(account__isnull=True, is_system_default=True).count() >= 3
    assert InspectionRule.objects.filter(system_key="water_filter_low_life", account__isnull=True).count() == 1


@pytest.mark.django_db
def test_inspection_scanner_merges_same_dedupe_key_into_existing_suggestion():
    account = Account.objects.create(email="care-merge@example.com", name="care-merge", password="x")
    device = DeviceSnapshot.objects.create(
        account=account,
        external_id="mijia:device-merge",
        name="净水器",
        category="water_purifier",
        status=DeviceSnapshot.StatusChoices.ONLINE,
    )
    DeviceControl.objects.create(
        account=account,
        device=device,
        external_id="mijia:device-merge:filter",
        source_type=DeviceControl.SourceTypeChoices.MIJIA_PROPERTY,
        kind=DeviceControl.KindChoices.SENSOR,
        key="filter_life_percent",
        label="滤芯寿命",
        value=9,
        unit="%",
    )
    InspectionRule.objects.create(
        account=account,
        rule_type=InspectionRule.RuleTypeChoices.CUSTOM,
        name="规则一",
        condition_spec={"field": "control.filter_life_percent", "operator": "<", "threshold": 20},
        suggestion_template="{device_name} 需要关注",
        priority=5,
    )
    InspectionRule.objects.create(
        account=account,
        rule_type=InspectionRule.RuleTypeChoices.CUSTOM,
        name="规则二",
        condition_spec={"field": "control.filter_life_percent", "operator": "<", "threshold": 30},
        suggestion_template="{device_name} 需要关注",
        priority=7,
    )

    created = InspectionScanner.scan_account(account)

    assert len(created) == 1
    suggestion = CareSuggestion.objects.get(account=account)
    assert suggestion.aggregated_count >= 2
    assert len(suggestion.aggregated_from) >= 2
    assert suggestion.priority >= 7


@pytest.mark.django_db
def test_feedback_history_lowers_priority_for_repeated_denials():
    account = Account.objects.create(email="care-priority@example.com", name="care-priority", password="x")
    rule = InspectionRule.objects.create(
        account=account,
        rule_type=InspectionRule.RuleTypeChoices.CUSTOM,
        name="离线提醒",
        condition_spec={"field": "device_offline_hours", "operator": ">", "threshold": 4},
        priority=8,
    )
    topic_key = FeedbackLearner.build_topic_key(
        suggestion=CareSuggestion(
            account=account,
            suggestion_type=CareSuggestion.SuggestionTypeChoices.INSPECTION,
            source_rule=rule,
            title="x",
            body="x",
            dedupe_key="x",
        )
    )
    for _ in range(3):
        ProactiveLog.objects.create(
            account=account,
            message="x",
            feedback=ProactiveLog.FeedbackChoices.DENIED,
            score=8,
            source=topic_key,
        )

    priority = InspectionScanner._compute_priority(account, rule, 10)

    assert priority == 2.4


@pytest.mark.django_db
def test_inspection_scanner_reactivates_ignored_suggestion_when_rule_hits_again():
    account = Account.objects.create(email="care-reactivate@example.com", name="care-reactivate", password="x")
    device = DeviceSnapshot.objects.create(
        account=account,
        external_id="mijia:device-reactivate",
        name="净水器",
        category="water_purifier",
        status=DeviceSnapshot.StatusChoices.ONLINE,
    )
    control = DeviceControl.objects.create(
        account=account,
        device=device,
        external_id="mijia:device-reactivate:filter",
        source_type=DeviceControl.SourceTypeChoices.MIJIA_PROPERTY,
        kind=DeviceControl.KindChoices.SENSOR,
        key="filter_life_percent",
        label="滤芯寿命",
        value=8,
        unit="%",
    )
    rule = InspectionRule.objects.create(
        account=account,
        rule_type=InspectionRule.RuleTypeChoices.CUSTOM,
        name="滤芯提醒",
        condition_spec={"field": "control.filter_life_percent", "operator": "<", "threshold": 20},
        suggestion_template="{device_name} 需要关注",
        priority=6,
    )
    suggestion = CareSuggestion.objects.create(
        account=account,
        suggestion_type=CareSuggestion.SuggestionTypeChoices.INSPECTION,
        source_rule=rule,
        device=device,
        control_target=control,
        title="净水器 需要关注",
        body="body",
        priority=6,
        dedupe_key=f"{device.external_id}:{control.external_id}:control.filter_life_percent",
        status=CareSuggestion.StatusChoices.IGNORED,
        aggregated_count=1,
        aggregated_from=[rule.id],
    )

    created = InspectionScanner.scan_account(account)

    assert created == []
    suggestion.refresh_from_db()
    assert suggestion.status == CareSuggestion.StatusChoices.PENDING
    assert suggestion.aggregated_count >= 2
