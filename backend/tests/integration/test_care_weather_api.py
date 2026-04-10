from unittest.mock import Mock, patch
import json

import pytest
from django.urls import reverse

from accounts.models import Account
from accounts.test_utils import auth_headers
from care.models import CareSuggestion, ExternalDataSource
from devices.models import DeviceControl, DeviceSnapshot


@pytest.mark.django_db
def test_weather_refresh_endpoint_updates_source_and_generates_suggestion(client):
    account = Account.objects.create(email="weather-api@example.com", name="weather-api", password="x")
    device = DeviceSnapshot.objects.create(
        account=account,
        external_id="home_assistant:climate.study_ac",
        name="书房空调",
        category="空调",
        status=DeviceSnapshot.StatusChoices.ONLINE,
    )
    DeviceControl.objects.create(
        account=account,
        device=device,
        external_id="home_assistant:climate.study_ac:target_temperature",
        source_type=DeviceControl.SourceTypeChoices.HA_ENTITY,
        kind=DeviceControl.KindChoices.RANGE,
        key="climate.study_ac:target_temperature",
        label="书房空调 目标温度",
        writable=True,
        value=23,
        unit="°C",
    )
    ExternalDataSource.objects.create(
        account=account,
        source_type=ExternalDataSource.SourceTypeChoices.WEATHER_API,
        name="Open Meteo",
        config={"endpoint": "https://api.open-meteo.com/v1/forecast", "latitude": 31.2, "longitude": 121.5},
        last_data={"temperature": 22.0, "condition": "weather_code:1", "fetched_at": "2026-04-04 08:00:00"},
        is_active=True,
    )

    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"current": {"temperature_2m": 13.0, "weather_code": 3}}

    with patch("care.services.weather.requests.get", return_value=response):
        result = client.post(reverse("care:weather_refresh"), data="{}", content_type="application/json", **auth_headers(account))

    assert result.status_code == 200
    payload = result.json()
    assert payload["weather"]["temperature"] == 13.0
    assert payload["suggestionId"] is not None
    assert CareSuggestion.objects.filter(account=account, suggestion_type=CareSuggestion.SuggestionTypeChoices.CARE).count() == 1


@pytest.mark.django_db
def test_weather_source_creation_rejects_invalid_home_assistant_config(client):
    account = Account.objects.create(email="weather-source@example.com", name="weather-source", password="x")

    response = client.post(
        reverse("care:data_sources"),
        data='{"source_type":"ha_entity","name":"HA Weather","config":{}}',
        content_type="application/json",
        **auth_headers(account),
    )

    assert response.status_code == 400
    assert "ha_entity_id" in response.json()["error"]


@pytest.mark.django_db
def test_weather_source_creation_rejects_invalid_qweather_config(client):
    account = Account.objects.create(email="weather-qweather-source@example.com", name="weather-qweather-source", password="x")

    response = client.post(
        reverse("care:data_sources"),
        data='{"source_type":"weather_api","name":"QWeather","config":{"provider":"qweather"}}',
        content_type="application/json",
        **auth_headers(account),
    )

    assert response.status_code == 400
    assert "api_key" in response.json()["error"]


@pytest.mark.django_db
def test_weather_source_creation_rejects_qweather_without_endpoint(client):
    account = Account.objects.create(email="weather-qweather-host@example.com", name="weather-qweather-host", password="x")

    response = client.post(
        reverse("care:data_sources"),
        data='{"source_type":"weather_api","name":"QWeather","config":{"provider":"qweather","api_key":"Q0606E43B6","location":"101020100"}}',
        content_type="application/json",
        **auth_headers(account),
    )

    assert response.status_code == 400
    assert "endpoint" in response.json()["error"]


@pytest.mark.django_db
def test_weather_refresh_flow_exposes_generated_suggestion_with_action_spec(client):
    account = Account.objects.create(email="weather-flow@example.com", name="weather-flow", password="x")
    device = DeviceSnapshot.objects.create(
        account=account,
        external_id="home_assistant:climate.living_room",
        name="客厅空调",
        category="climate",
        status=DeviceSnapshot.StatusChoices.ONLINE,
    )
    control = DeviceControl.objects.create(
        account=account,
        device=device,
        external_id="home_assistant:climate.living_room:target_temperature",
        source_type=DeviceControl.SourceTypeChoices.HA_ENTITY,
        kind=DeviceControl.KindChoices.RANGE,
        key="target_temperature",
        label="目标温度",
        writable=True,
        value=24,
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
        last_data={"temperature": 24.0, "condition": "sunny", "fetched_at": "2026-04-04 09:00:00"},
        is_active=True,
    )

    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"current": {"temperature_2m": 12.0, "weather_code": 61}}

    with patch("care.services.weather.requests.get", return_value=response):
        refresh_result = client.post(reverse("care:weather_refresh"), data="{}", content_type="application/json", **auth_headers(account))

    assert refresh_result.status_code == 200
    suggestion_id = refresh_result.json()["suggestionId"]
    assert suggestion_id is not None

    suggestions_result = client.get(reverse("care:suggestions"), **auth_headers(account))
    assert suggestions_result.status_code == 200
    suggestion = suggestions_result.json()["suggestions"][0]
    assert suggestion["id"] == suggestion_id
    assert suggestion["device"]["id"] == device.external_id
    assert suggestion["control"]["id"] == control.external_id
    assert suggestion["actionSpec"]["value"] == 25


@pytest.mark.django_db
def test_weather_refresh_supports_qweather_source(client):
    account = Account.objects.create(email="weather-qweather-flow@example.com", name="weather-qweather-flow", password="x")
    device = DeviceSnapshot.objects.create(
        account=account,
        external_id="home_assistant:climate.bedroom",
        name="卧室空调",
        category="climate",
        status=DeviceSnapshot.StatusChoices.ONLINE,
    )
    DeviceControl.objects.create(
        account=account,
        device=device,
        external_id="home_assistant:climate.bedroom:target_temperature",
        source_type=DeviceControl.SourceTypeChoices.HA_ENTITY,
        kind=DeviceControl.KindChoices.RANGE,
        key="target_temperature",
        label="目标温度",
        writable=True,
        value=25,
        unit="°C",
    )
    ExternalDataSource.objects.create(
        account=account,
        source_type=ExternalDataSource.SourceTypeChoices.WEATHER_API,
        name="QWeather Shanghai",
        config={
            "provider": "qweather",
            "endpoint": "https://p27mdaprbw.re.qweatherapi.com",
            "api_key": "Q0606E43B6",
            "location": "101020100",
            "longitude": 121.47,
            "latitude": 31.23,
            "drop_threshold": 8,
        },
        last_data={"temperature": 26.0, "condition": "晴", "fetched_at": "2026-04-04 09:00:00"},
        is_active=True,
    )

    def build_response(payload):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = payload
        return response

    with patch(
        "care.services.weather.requests.get",
        side_effect=[
            build_response({"code": "200", "now": {"temp": "16", "text": "阴", "humidity": "75", "feelsLike": "15"}}),
            build_response({"code": "200", "daily": [{"fxDate": "2026-04-05", "textDay": "阴", "tempMin": "14", "tempMax": "20"}]}),
            build_response({"code": "200", "hourly": [{"fxTime": "2026-04-05T13:00+08:00", "text": "阴", "temp": "16", "pop": "5"}]}),
            build_response({"code": "200", "daily": [{"name": "穿衣指数", "category": "凉", "text": "建议外套"}]}),
            build_response({"code": "200", "warning": []}),
            build_response({"indexes": [{"aqiDisplay": "31", "category": "Excellent", "primaryPollutant": {"name": "PM2.5"}}]}),
        ],
    ):
        refresh_result = client.post(reverse("care:weather_refresh"), data="{}", content_type="application/json", **auth_headers(account))

    assert refresh_result.status_code == 200
    payload = refresh_result.json()
    assert payload["weather"]["provider"] == "qweather"
    assert payload["weather"]["temperature"] == 16.0
    assert payload["weather"]["air_quality"]["aqi"] == "31"
    assert payload["weather"]["hourly_forecast"][0]["text"] == "阴"
    assert payload["weather"]["indices"][0]["name"] == "穿衣指数"
    assert payload["suggestionId"] is not None
