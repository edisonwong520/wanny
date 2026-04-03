from unittest.mock import AsyncMock, patch

import pytest

from accounts.models import Account
from care.models import CareSuggestion
from care.services.workflow import CareWorkflowService
from comms.models import Mission
from devices.models import DeviceControl, DeviceSnapshot


@pytest.mark.django_db
def test_create_mission_for_suggestion_is_idempotent():
    account = Account.objects.create(email="care-workflow@example.com", name="care-workflow", password="x")
    device = DeviceSnapshot.objects.create(
        account=account,
        external_id="ha:light.kitchen",
        name="厨房灯",
        category="light",
        status=DeviceSnapshot.StatusChoices.ONLINE,
    )
    control = DeviceControl.objects.create(
        account=account,
        device=device,
        external_id="ha:light.kitchen:power",
        source_type=DeviceControl.SourceTypeChoices.HA_ENTITY,
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
        title="建议开灯",
        body="body",
        action_spec={"device_id": device.external_id, "control_id": control.external_id, "action": "turn_on", "value": True},
        priority=6.5,
        dedupe_key="care:workflow:idempotent",
    )

    first = CareWorkflowService.create_mission_for_suggestion(suggestion)
    second = CareWorkflowService.create_mission_for_suggestion(suggestion)

    assert first.id == second.id
    assert Mission.objects.filter(account=account).count() == 1


@pytest.mark.django_db
def test_execute_suggestion_marks_failed_when_device_operation_fails():
    account = Account.objects.create(email="care-workflow-fail@example.com", name="care-workflow-fail", password="x")
    device = DeviceSnapshot.objects.create(
        account=account,
        external_id="ha:climate.study",
        name="书房空调",
        category="climate",
        status=DeviceSnapshot.StatusChoices.ONLINE,
    )
    control = DeviceControl.objects.create(
        account=account,
        device=device,
        external_id="ha:climate.study:target_temperature",
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
        priority=7,
        dedupe_key="care:workflow:fail",
    )

    with patch(
        "care.services.workflow.DeviceCommandService.execute_device_operation",
        new=AsyncMock(return_value={"success": False, "message": "device offline"}),
    ):
        result = CareWorkflowService.execute_suggestion(suggestion)

    suggestion.refresh_from_db()
    mission = suggestion.mission
    assert result["success"] is False
    assert suggestion.status == CareSuggestion.StatusChoices.FAILED
    assert mission.status == Mission.StatusChoices.FAILED
    assert suggestion.user_feedback["executed"] is False
    assert suggestion.user_feedback["result"] == "device offline"
