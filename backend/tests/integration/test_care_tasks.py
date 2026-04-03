from unittest.mock import Mock, patch

from asgiref.sync import async_to_sync
import pytest

from accounts.models import Account
from care.models import CareSuggestion, ExternalDataSource, InspectionRule
from care.tasks import deliver_care_suggestions, fetch_weather_and_generate_care, run_periodic_inspection
from comms.bot_runtime import set_current_bot
from devices.models import DeviceControl, DeviceSnapshot
from providers.models import PlatformAuth


class FakeBot:
    def __init__(self):
        self._context_tokens = {"wx-care-task-user": "token"}
        self.sent = []

    async def send(self, user_id, text):
        self.sent.append((user_id, text))


@pytest.mark.django_db
def test_run_periodic_inspection_generates_suggestion_and_pushes_to_wechat():
    account = Account.objects.create(email="care-task-inspection@example.com", name="care-task-inspection", password="x")
    PlatformAuth.objects.create(
        account=account,
        platform_name="wechat",
        is_active=True,
        auth_payload={"user_id": "wx-care-task-user"},
    )
    device = DeviceSnapshot.objects.create(
        account=account,
        external_id="mijia:purifier-care-task",
        name="净水器",
        category="water_purifier",
        status=DeviceSnapshot.StatusChoices.ONLINE,
    )
    DeviceControl.objects.create(
        account=account,
        device=device,
        external_id="mijia:purifier-care-task:filter",
        source_type=DeviceControl.SourceTypeChoices.MIJIA_PROPERTY,
        kind=DeviceControl.KindChoices.SENSOR,
        key="filter_life_percent",
        label="滤芯寿命",
        value=8,
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

    bot = FakeBot()
    set_current_bot(bot)
    try:
        created = async_to_sync(run_periodic_inspection)()
    finally:
        set_current_bot(None)

    assert created == 1
    assert CareSuggestion.objects.filter(account=account).count() == 1
    assert bot.sent
    assert "净水器 需要更换滤芯" in bot.sent[0][1]


@pytest.mark.django_db
def test_fetch_weather_and_generate_care_generates_suggestion_and_pushes_to_wechat():
    account = Account.objects.create(email="care-task-weather@example.com", name="care-task-weather", password="x")
    PlatformAuth.objects.create(
        account=account,
        platform_name="wechat",
        is_active=True,
        auth_payload={"user_id": "wx-care-task-user"},
    )
    device = DeviceSnapshot.objects.create(
        account=account,
        external_id="home_assistant:climate.study_room",
        name="书房空调",
        category="climate",
        status=DeviceSnapshot.StatusChoices.ONLINE,
    )
    DeviceControl.objects.create(
        account=account,
        device=device,
        external_id="home_assistant:climate.study_room:target_temperature",
        source_type=DeviceControl.SourceTypeChoices.HA_ENTITY,
        kind=DeviceControl.KindChoices.RANGE,
        key="climate.study_room:target_temperature",
        label="书房空调 目标温度",
        writable=True,
        value=23,
        unit="°C",
    )
    ExternalDataSource.objects.create(
        account=account,
        source_type=ExternalDataSource.SourceTypeChoices.WEATHER_API,
        name="Open Meteo",
        config={
            "provider": "open_meteo",
            "endpoint": "https://api.open-meteo.com/v1/forecast",
            "latitude": 31.23,
            "longitude": 121.47,
            "timezone": "Asia/Shanghai",
            "drop_threshold": 8,
        },
        last_data={"temperature": 23.0, "condition": "sunny", "fetched_at": "2026-04-04 09:00:00"},
        is_active=True,
    )

    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"current": {"temperature_2m": 12.0, "weather_code": 61}}

    bot = FakeBot()
    set_current_bot(bot)
    try:
        with patch("care.services.weather.requests.get", return_value=response):
            created = async_to_sync(fetch_weather_and_generate_care)()
    finally:
        set_current_bot(None)

    assert created == 1
    suggestion = CareSuggestion.objects.get(account=account)
    assert suggestion.device == device
    assert suggestion.action_spec["value"] == 24
    assert bot.sent
    assert "外部温度下降了 11.0°C" in bot.sent[0][1]


@pytest.mark.django_db
def test_fetch_weather_and_generate_care_supports_home_assistant_entity_sources():
    account = Account.objects.create(email="care-task-weather-ha@example.com", name="care-task-weather-ha", password="x")
    PlatformAuth.objects.create(
        account=account,
        platform_name="wechat",
        is_active=True,
        auth_payload={"user_id": "wx-care-task-user"},
    )
    device = DeviceSnapshot.objects.create(
        account=account,
        external_id="home_assistant:climate.living_room",
        name="客厅空调",
        category="climate",
        status=DeviceSnapshot.StatusChoices.ONLINE,
    )
    DeviceControl.objects.create(
        account=account,
        device=device,
        external_id="home_assistant:climate.living_room:target_temperature",
        source_type=DeviceControl.SourceTypeChoices.HA_ENTITY,
        kind=DeviceControl.KindChoices.RANGE,
        key="climate.living_room:target_temperature",
        label="客厅空调 目标温度",
        writable=True,
        value=24,
        unit="°C",
    )
    ExternalDataSource.objects.create(
        account=account,
        source_type=ExternalDataSource.SourceTypeChoices.HA_ENTITY,
        name="HA Weather",
        config={"ha_entity_id": "weather.home", "drop_threshold": 6},
        last_data={"temperature": 21.0, "condition": "sunny", "fetched_at": "2026-04-04 07:00:00"},
        is_active=True,
    )

    bot = FakeBot()
    set_current_bot(bot)
    try:
        with patch(
            "care.services.weather.HomeAssistantAuthService.get_entity_states",
            return_value=(
                {},
                [{"entity_id": "weather.home", "state": "rainy", "attributes": {"temperature": 14.0, "condition": "rainy"}}],
            ),
        ):
            created = async_to_sync(fetch_weather_and_generate_care)()
    finally:
        set_current_bot(None)

    assert created == 1
    suggestion = CareSuggestion.objects.get(account=account)
    assert suggestion.device == device
    assert suggestion.source_event["event"] == "weather_temperature_drop"
    assert bot.sent


@pytest.mark.django_db
def test_deliver_care_suggestions_returns_zero_without_active_bot():
    account = Account.objects.create(email="care-task-push-empty@example.com", name="care-task-push-empty", password="x")
    PlatformAuth.objects.create(
        account=account,
        platform_name="wechat",
        is_active=True,
        auth_payload={"user_id": "wx-care-task-user"},
    )
    CareSuggestion.objects.create(
        account=account,
        suggestion_type=CareSuggestion.SuggestionTypeChoices.CARE,
        title="天气提醒",
        body="body",
        priority=8,
        dedupe_key="care-task-push-empty",
    )

    set_current_bot(None)
    pushed = async_to_sync(deliver_care_suggestions)()

    assert pushed == 0
