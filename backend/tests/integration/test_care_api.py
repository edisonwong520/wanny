import json
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from django.utils import timezone
from django.urls import reverse

from accounts.models import Account
from care.models import CareSuggestion, ExternalDataSource, InspectionRule
from devices.models import DeviceControl, DeviceSnapshot
from memory.models import ProactiveLog, UserProfile


@pytest.mark.django_db
def test_care_suggestion_feedback_approve_creates_mission(client):
    account = Account.objects.create(email="care-api@example.com", name="care-api", password="x")
    device = DeviceSnapshot.objects.create(
        account=account,
        external_id="mijia:light-1",
        name="客厅灯",
        category="light",
        status=DeviceSnapshot.StatusChoices.ONLINE,
    )
    control = DeviceControl.objects.create(
        account=account,
        device=device,
        external_id="mijia:light-1:power",
        source_type=DeviceControl.SourceTypeChoices.MIJIA_PROPERTY,
        kind=DeviceControl.KindChoices.TOGGLE,
        key="power",
        label="电源",
        writable=True,
        value=False,
    )
    suggestion = CareSuggestion.objects.create(
        account=account,
        suggestion_type=CareSuggestion.SuggestionTypeChoices.CARE,
        device=device,
        control_target=control,
        title="天气转凉，建议开灯",
        body="可以提前打开客厅灯。",
        action_spec={
            "device_id": device.external_id,
            "control_id": control.external_id,
            "control_key": control.key,
            "action": "turn_on",
            "value": True,
        },
        priority=6,
        dedupe_key="care:test:1",
    )

    response = client.post(
        reverse("care:suggestion_feedback", args=[suggestion.id]),
        data=json.dumps({"action": "approve"}),
        content_type="application/json",
        HTTP_X_WANNY_EMAIL=account.email,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "approved"
    suggestion.refresh_from_db()
    assert suggestion.mission_id is not None
    assert suggestion.status == CareSuggestion.StatusChoices.APPROVED


@pytest.mark.django_db
def test_care_run_inspection_endpoint_creates_suggestion(client):
    account = Account.objects.create(email="care-run@example.com", name="care-run", password="x")
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
        external_id="mijia:purifier-1:filter",
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
        condition_spec={"field": "control.filter_life_percent", "operator": "<", "threshold": 20},
        suggestion_template="{device_name} 需要更换滤芯。",
        priority=8,
    )

    response = client.post(
        reverse("care:run_inspection"),
        data="{}",
        content_type="application/json",
        HTTP_X_WANNY_EMAIL=account.email,
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["created"]) == 1
    assert payload["created"][0]["title"] == "净水器 需要更换滤芯。"


@pytest.mark.django_db
def test_care_feedback_updates_logs_and_profiles(client):
    account = Account.objects.create(email="care-feedback@example.com", name="care-feedback", password="x")
    device = DeviceSnapshot.objects.create(
        account=account,
        external_id="home_assistant:climate.ac-1",
        name="客厅空调",
        category="climate",
        status=DeviceSnapshot.StatusChoices.ONLINE,
    )
    control = DeviceControl.objects.create(
        account=account,
        device=device,
        external_id="home_assistant:climate.ac-1:target_temperature",
        source_type=DeviceControl.SourceTypeChoices.HA_ENTITY,
        kind=DeviceControl.KindChoices.RANGE,
        key="target_temperature",
        label="目标温度",
        writable=True,
        value=24,
    )
    suggestion = CareSuggestion.objects.create(
        account=account,
        suggestion_type=CareSuggestion.SuggestionTypeChoices.CARE,
        device=device,
        control_target=control,
        title="降温关怀",
        body="天气转凉，建议调高空调。",
        action_spec={"device_id": device.external_id, "control_id": control.external_id, "value": 25},
        priority=6,
        dedupe_key="care:weather:1",
        source_event={"event": "weather_temperature_drop"},
    )

    response = client.post(
        reverse("care:suggestion_feedback", args=[suggestion.id]),
        data=json.dumps({"action": "approve"}),
        content_type="application/json",
        HTTP_X_WANNY_EMAIL=account.email,
    )

    assert response.status_code == 200
    assert ProactiveLog.objects.filter(account=account, source="care:event:weather_temperature_drop").exists()
    profile = UserProfile.objects.get(account=account, key="care_preferred_cold_weather_target_temp")
    assert profile.value == "25"


@pytest.mark.django_db
def test_create_rule_rejects_invalid_condition_spec(client):
    account = Account.objects.create(email="care-invalid-rule@example.com", name="care-invalid-rule", password="x")

    response = client.post(
        reverse("care:rules"),
        data=json.dumps(
            {
                "rule_type": "custom",
                "name": "坏规则",
                "condition_spec": {"field": "control.power", "operator": "bad-op"},
            }
        ),
        content_type="application/json",
        HTTP_X_WANNY_EMAIL=account.email,
    )

    assert response.status_code == 400
    assert "condition_spec.operator" in response.json()["error"]


@pytest.mark.django_db
def test_system_rule_can_toggle_active_but_cannot_edit_fields(client):
    account = Account.objects.create(email="care-system-rule@example.com", name="care-system-rule", password="x")
    rule = InspectionRule.objects.create(
        account=None,
        is_system_default=True,
        rule_type=InspectionRule.RuleTypeChoices.MAINTENANCE,
        device_category="water_purifier",
        name="系统滤芯提醒",
        description="系统规则",
        condition_spec={"field": "control.filter_life_percent", "operator": "<", "threshold": 20},
        suggestion_template="{device_name} 需要更换滤芯。",
        priority=8,
        is_active=True,
    )

    toggle_response = client.put(
        reverse("care:rule_detail", args=[rule.id]),
        data=json.dumps({"is_active": False}),
        content_type="application/json",
        HTTP_X_WANNY_EMAIL=account.email,
    )

    assert toggle_response.status_code == 200
    rule.refresh_from_db()
    assert rule.is_active is False

    update_response = client.put(
        reverse("care:rule_detail", args=[rule.id]),
        data=json.dumps({"name": "被改掉的系统规则"}),
        content_type="application/json",
        HTTP_X_WANNY_EMAIL=account.email,
    )

    assert update_response.status_code == 400
    assert "only supports is_active updates" in update_response.json()["error"]


@pytest.mark.django_db
def test_care_suggestion_list_includes_semantic_aggregation_sources_for_rules(client):
    account = Account.objects.create(email="care-aggregation-rule@example.com", name="care-aggregation-rule", password="x")
    rule = InspectionRule.objects.create(
        account=account,
        rule_type=InspectionRule.RuleTypeChoices.MAINTENANCE,
        device_category="water_purifier",
        name="滤芯更换提醒",
        condition_spec={"field": "control.filter_life_percent", "operator": "<", "threshold": 20},
        suggestion_template="{device_name} 需要更换滤芯。",
        priority=8,
    )
    suggestion = CareSuggestion.objects.create(
        account=account,
        suggestion_type=CareSuggestion.SuggestionTypeChoices.INSPECTION,
        source_rule=rule,
        title="净水器需要更换滤芯",
        body="body",
        priority=8.5,
        dedupe_key="care:agg:rule:1",
        aggregated_count=2,
        aggregated_from=[rule.id],
    )

    response = client.get(
        reverse("care:suggestions"),
        HTTP_X_WANNY_EMAIL=account.email,
    )

    assert response.status_code == 200
    item = response.json()["suggestions"][0]
    assert item["id"] == suggestion.id
    assert item["aggregationSources"][0]["kind"] == "rule"
    assert item["aggregationSources"][0]["label"] == "滤芯更换提醒"


@pytest.mark.django_db
def test_care_suggestion_list_includes_semantic_aggregation_sources_for_weather(client):
    account = Account.objects.create(email="care-aggregation-weather@example.com", name="care-aggregation-weather", password="x")
    source = ExternalDataSource.objects.create(
        account=account,
        source_type=ExternalDataSource.SourceTypeChoices.WEATHER_API,
        name="Open-Meteo Shanghai",
        config={"provider": "open_meteo"},
        fetch_frequency="30m",
    )
    suggestion = CareSuggestion.objects.create(
        account=account,
        suggestion_type=CareSuggestion.SuggestionTypeChoices.CARE,
        title="外部温度下降了 9°C",
        body="body",
        priority=7.2,
        dedupe_key="care:agg:weather:1",
        aggregated_count=2,
        aggregated_from=[source.id],
        source_event={"event": "weather_temperature_drop", "source_id": source.id},
    )

    response = client.get(
        reverse("care:suggestions"),
        HTTP_X_WANNY_EMAIL=account.email,
    )

    assert response.status_code == 200
    item = response.json()["suggestions"][0]
    assert item["id"] == suggestion.id
    assert item["aggregationSources"][0]["kind"] == "data_source"
    assert item["aggregationSources"][0]["label"] == "Open-Meteo Shanghai"
    assert item["aggregationSources"][1]["kind"] == "event"


@pytest.mark.django_db
def test_care_suggestion_list_includes_push_audit(client):
    account = Account.objects.create(email="care-audit@example.com", name="care-audit", password="x")
    suggestion = CareSuggestion.objects.create(
        account=account,
        suggestion_type=CareSuggestion.SuggestionTypeChoices.CARE,
        title="天气提醒",
        body="body",
        priority=3.5,
        dedupe_key="care:audit:1",
        user_feedback={
            "action": "ignore",
            "push": {
                "count": 2,
                "last_pushed_at": (timezone.now() - timedelta(hours=3)).isoformat(),
            },
        },
        feedback_collected_at=timezone.now() - timedelta(hours=2),
    )

    response = client.get(
        reverse("care:suggestions"),
        HTTP_X_WANNY_EMAIL=account.email,
    )

    assert response.status_code == 200
    payload = response.json()["suggestions"]
    assert len(payload) == 1
    item = payload[0]
    assert item["id"] == suggestion.id
    assert item["pushAudit"]["level"] == "low"
    assert item["pushAudit"]["pushCount"] == 2
    assert item["pushAudit"]["consoleOnly"] is True
    assert item["pushAudit"]["suppressReason"] == "console_only"
    assert item["pushAudit"]["ignoredUntil"] is not None


@pytest.mark.django_db
def test_run_inspection_flow_merges_repeated_hits_into_existing_suggestion(client):
    account = Account.objects.create(email="care-inspection-flow@example.com", name="care-inspection-flow", password="x")
    device = DeviceSnapshot.objects.create(
        account=account,
        external_id="mijia:purifier-flow-1",
        name="净水器",
        category="water_purifier",
        status=DeviceSnapshot.StatusChoices.ONLINE,
    )
    control = DeviceControl.objects.create(
        account=account,
        device=device,
        external_id="mijia:purifier-flow-1:filter",
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
        condition_spec={"field": "control.filter_life_percent", "operator": "<", "threshold": 20},
        suggestion_template="{device_name} 需要更换滤芯。",
        priority=8,
        cooldown_hours=24,
    )

    first = client.post(reverse("care:run_inspection"), data="{}", content_type="application/json", HTTP_X_WANNY_EMAIL=account.email)
    second = client.post(reverse("care:run_inspection"), data="{}", content_type="application/json", HTTP_X_WANNY_EMAIL=account.email)

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(first.json()["created"]) == 1
    assert len(second.json()["created"]) == 0

    suggestion = CareSuggestion.objects.get(account=account, control_target=control)
    assert suggestion.aggregated_count >= 2
    assert suggestion.status == CareSuggestion.StatusChoices.PENDING


@pytest.mark.django_db
def test_execute_suggestion_api_returns_failed_status_when_device_operation_fails(client):
    account = Account.objects.create(email="care-execute-fail@example.com", name="care-execute-fail", password="x")
    device = DeviceSnapshot.objects.create(
        account=account,
        external_id="home_assistant:climate.study",
        name="书房空调",
        category="climate",
        status=DeviceSnapshot.StatusChoices.ONLINE,
    )
    control = DeviceControl.objects.create(
        account=account,
        device=device,
        external_id="home_assistant:climate.study:target_temperature",
        source_type=DeviceControl.SourceTypeChoices.HA_ENTITY,
        kind=DeviceControl.KindChoices.RANGE,
        key="target_temperature",
        label="目标温度",
        writable=True,
        value=24,
    )
    suggestion = CareSuggestion.objects.create(
        account=account,
        suggestion_type=CareSuggestion.SuggestionTypeChoices.CARE,
        device=device,
        control_target=control,
        title="建议调高温度",
        body="body",
        action_spec={"device_id": device.external_id, "control_id": control.external_id, "action": "set", "value": 25},
        priority=7.0,
        dedupe_key="care:execute:fail",
    )

    with patch(
        "care.services.workflow.DeviceCommandService.execute_device_operation",
        new=AsyncMock(return_value={"success": False, "message": "device offline"}),
    ):
        response = client.post(
            reverse("care:suggestion_execute", args=[suggestion.id]),
            data=json.dumps({"confirmed": True}),
            content_type="application/json",
            HTTP_X_WANNY_EMAIL=account.email,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == CareSuggestion.StatusChoices.FAILED
    assert payload["result"]["success"] is False
    suggestion.refresh_from_db()
    assert suggestion.status == CareSuggestion.StatusChoices.FAILED
    assert suggestion.mission.status == "failed"
