from unittest.mock import Mock, patch

import pytest

from accounts.models import Account
from care.models import CareSuggestion, ExternalDataSource
from care.services.processor import CareEventProcessor
from care.services.weather import WeatherDataService
from devices.models import DeviceControl, DeviceSnapshot


@pytest.mark.django_db
def test_weather_service_normalizes_open_meteo_payload():
    account = Account.objects.create(email="weather@example.com", name="weather", password="x")
    source = ExternalDataSource.objects.create(
        account=account,
        source_type=ExternalDataSource.SourceTypeChoices.WEATHER_API,
        name="Open Meteo",
        config={"endpoint": "https://api.open-meteo.com/v1/forecast", "latitude": 31.2, "longitude": 121.5},
        last_data={"temperature": 21.0, "condition": "weather_code:1", "fetched_at": "2026-04-04 08:00:00"},
    )

    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"current": {"temperature_2m": 13.5, "weather_code": 61}}

    with patch("care.services.weather.requests.get", return_value=response) as requests_get:
        updated = WeatherDataService.fetch_source(source)

    requests_get.assert_called_once()
    assert updated.last_data["temperature"] == 13.5
    assert updated.last_data["previous_temperature"] == 21.0
    assert updated.last_data["condition"] == "weather_code:61"


@pytest.mark.django_db
def test_weather_service_falls_back_to_cached_payload_when_remote_fails():
    account = Account.objects.create(email="weather-cache@example.com", name="weather-cache", password="x")
    source = ExternalDataSource.objects.create(
        account=account,
        source_type=ExternalDataSource.SourceTypeChoices.WEATHER_API,
        name="Open Meteo",
        config={"endpoint": "https://api.open-meteo.com/v1/forecast", "latitude": 31.2, "longitude": 121.5},
        last_data={"temperature": 18.0, "condition": "weather_code:2", "fetched_at": "2026-04-04 09:00:00"},
    )

    with patch("care.services.weather.requests.get", side_effect=RuntimeError("upstream timeout")):
        updated = WeatherDataService.fetch_source(source)

    assert updated.last_data["temperature"] == 18.0
    assert updated.last_data["degraded"] is True
    assert "timeout" in updated.last_data["error"]


@pytest.mark.django_db
def test_weather_service_supports_home_assistant_weather_entity():
    account = Account.objects.create(email="weather-ha@example.com", name="weather-ha", password="x")
    source = ExternalDataSource.objects.create(
        account=account,
        source_type=ExternalDataSource.SourceTypeChoices.HA_ENTITY,
        name="HA Weather",
        config={"ha_entity_id": "weather.home"},
        last_data={"temperature": 24.0, "condition": "sunny", "fetched_at": "2026-04-04 07:00:00"},
    )

    with patch(
        "care.services.weather.HomeAssistantAuthService.get_entity_states",
        return_value=(
            {},
            [{"entity_id": "weather.home", "state": "rainy", "attributes": {"temperature": 16.5, "condition": "rainy"}}],
        ),
    ) as mocked_get_states:
        updated = WeatherDataService.fetch_source(source)

    mocked_get_states.assert_called_once_with(account, ["weather.home"])
    assert updated.last_data["temperature"] == 16.5
    assert updated.last_data["condition"] == "rainy"
    assert updated.last_data["previous_temperature"] == 24.0


@pytest.mark.django_db
def test_weather_service_raises_when_cache_missing_and_remote_fails():
    account = Account.objects.create(email="weather-fail@example.com", name="weather-fail", password="x")
    source = ExternalDataSource.objects.create(
        account=account,
        source_type=ExternalDataSource.SourceTypeChoices.WEATHER_API,
        name="Open Meteo",
        config={"endpoint": "https://api.open-meteo.com/v1/forecast", "latitude": 31.2, "longitude": 121.5},
        last_data={},
    )

    with patch("care.services.weather.requests.get", side_effect=RuntimeError("upstream timeout")):
        with pytest.raises(RuntimeError, match="upstream timeout"):
            WeatherDataService.fetch_source(source)


@pytest.mark.django_db
def test_care_event_processor_creates_weather_drop_suggestion_with_climate_action():
    account = Account.objects.create(email="weather-care@example.com", name="weather-care", password="x")
    device = DeviceSnapshot.objects.create(
        account=account,
        external_id="home_assistant:climate.living_room_ac",
        name="客厅空调",
        category="空调",
        status=DeviceSnapshot.StatusChoices.ONLINE,
    )
    control = DeviceControl.objects.create(
        account=account,
        device=device,
        external_id="home_assistant:climate.living_room_ac:target_temperature",
        source_type=DeviceControl.SourceTypeChoices.HA_ENTITY,
        kind=DeviceControl.KindChoices.RANGE,
        key="climate.living_room_ac:target_temperature",
        label="客厅空调 目标温度",
        writable=True,
        value=24,
        unit="°C",
    )
    source = ExternalDataSource.objects.create(
        account=account,
        source_type=ExternalDataSource.SourceTypeChoices.WEATHER_API,
        name="Weather",
        config={"drop_threshold": 8},
        last_data={"temperature": 12.0, "previous_temperature": 22.0, "condition": "雨"},
    )

    suggestion = CareEventProcessor.process_weather_source(source)

    assert suggestion is not None
    assert suggestion.suggestion_type == CareSuggestion.SuggestionTypeChoices.CARE
    assert suggestion.device == device
    assert suggestion.control_target == control
    assert suggestion.action_spec["value"] == 25
    assert "下降了 10.0°C" in suggestion.title


@pytest.mark.django_db
def test_care_event_processor_merges_repeated_weather_drop_into_existing_suggestion():
    account = Account.objects.create(email="weather-merge@example.com", name="weather-merge", password="x")
    source = ExternalDataSource.objects.create(
        account=account,
        source_type=ExternalDataSource.SourceTypeChoices.WEATHER_API,
        name="Weather",
        config={"drop_threshold": 8},
        last_data={"temperature": 10.0, "previous_temperature": 22.0, "condition": "雨"},
    )

    first = CareEventProcessor.process_weather_source(source)
    source.last_data = {"temperature": 9.0, "previous_temperature": 21.0, "condition": "雨"}
    source.save(update_fields=["last_data", "updated_at"])
    second = CareEventProcessor.process_weather_source(source)

    assert first.id == second.id
    second.refresh_from_db()
    assert second.aggregated_count == 2
    assert second.aggregated_from == [source.id]
