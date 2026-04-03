from __future__ import annotations

from datetime import datetime
from typing import Any

import requests

from care.models import ExternalDataSource
from providers.services import HomeAssistantAuthService


class WeatherDataService:
    default_open_meteo_endpoint = "https://api.open-meteo.com/v1/forecast"

    @classmethod
    def fetch_all_active_sources(cls) -> list[ExternalDataSource]:
        updated: list[ExternalDataSource] = []
        for source in ExternalDataSource.objects.filter(
            source_type__in=[
                ExternalDataSource.SourceTypeChoices.WEATHER_API,
                ExternalDataSource.SourceTypeChoices.HA_ENTITY,
            ],
            is_active=True,
        ).order_by("id"):
            updated.append(cls.fetch_source(source))
        return updated

    @classmethod
    def fetch_source(cls, source: ExternalDataSource) -> ExternalDataSource:
        config = source.config or {}
        previous_data = source.last_data if isinstance(source.last_data, dict) else {}
        degraded = False
        error_message = ""
        try:
            payload = cls._fetch_remote(source=source, config=config)
            normalized = cls._normalize_payload(payload, previous=previous_data, config=config)
        except Exception as error:
            if not previous_data:
                raise
            payload = previous_data.get("raw") if isinstance(previous_data.get("raw"), dict) else {}
            normalized = dict(previous_data)
            degraded = True
            error_message = str(error)
        if degraded:
            normalized["degraded"] = True
            normalized["error"] = error_message
        else:
            normalized.pop("degraded", None)
            normalized.pop("error", None)
        source.last_data = normalized
        source.last_fetch_at = datetime.now()
        source.save(update_fields=["last_data", "last_fetch_at", "updated_at"])
        return source

    @classmethod
    def _fetch_remote(cls, *, source: ExternalDataSource, config: dict) -> dict:
        if source.source_type == ExternalDataSource.SourceTypeChoices.HA_ENTITY:
            return cls._fetch_home_assistant_entity(source=source, config=config)

        endpoint = str(config.get("endpoint") or "").strip()
        if not endpoint and config.get("latitude") is not None and config.get("longitude") is not None:
            endpoint = cls.default_open_meteo_endpoint

        timeout = max(int(config.get("timeout_seconds") or 8), 1)

        if "open-meteo.com" in endpoint:
            params = {
                "latitude": config.get("latitude"),
                "longitude": config.get("longitude"),
                "current": "temperature_2m,weather_code",
                "timezone": config.get("timezone", "Asia/Shanghai"),
            }
            response = requests.get(endpoint, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()

        params = dict(config.get("params") or {})
        if config.get("api_key") and "key" not in params:
            params["key"] = config.get("api_key")
        if config.get("location") and "location" not in params:
            params["location"] = config.get("location")
        response = requests.get(endpoint, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()

    @classmethod
    def _fetch_home_assistant_entity(cls, *, source: ExternalDataSource, config: dict) -> dict:
        entity_id = str(config.get("ha_entity_id") or config.get("entity_id") or "").strip()
        if not entity_id:
            raise ValueError("HA weather source requires ha_entity_id")
        _, states = HomeAssistantAuthService.get_entity_states(source.account, [entity_id])
        if not states:
            raise ValueError("HA weather entity was not found")
        return states[0]

    @classmethod
    def _normalize_payload(cls, payload: dict, *, previous: dict, config: dict) -> dict:
        current_temp = cls._extract_temperature(payload, config)
        current_text = cls._extract_condition_text(payload, config)
        normalized = {
            "provider": config.get("provider") or cls._detect_provider(config),
            "temperature": current_temp,
            "condition": current_text,
            "raw": payload,
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        if isinstance(previous, dict):
            if "temperature" in previous:
                normalized["previous_temperature"] = previous.get("temperature")
            if "condition" in previous:
                normalized["previous_condition"] = previous.get("condition")
            if "fetched_at" in previous:
                normalized["previous_fetched_at"] = previous.get("fetched_at")
        return normalized

    @classmethod
    def _detect_provider(cls, config: dict) -> str:
        endpoint = str(config.get("endpoint") or "").lower()
        if "open-meteo" in endpoint:
            return "open_meteo"
        if "qweather" in endpoint:
            return "qweather"
        return "custom"

    @classmethod
    def _extract_temperature(cls, payload: dict, config: dict) -> float | None:
        custom_path = str(config.get("temperature_path") or "").strip()
        if custom_path:
            return cls._to_float(cls._dig(payload, custom_path))

        if isinstance(payload.get("current"), dict):
            current = payload["current"]
            if "temperature_2m" in current:
                return cls._to_float(current.get("temperature_2m"))
        if isinstance(payload.get("attributes"), dict):
            attributes = payload["attributes"]
            if "temperature" in attributes:
                return cls._to_float(attributes.get("temperature"))
        if isinstance(payload.get("current_weather"), dict):
            return cls._to_float(payload["current_weather"].get("temperature"))
        if isinstance(payload.get("now"), dict):
            return cls._to_float(payload["now"].get("temp"))
        return None

    @classmethod
    def _extract_condition_text(cls, payload: dict, config: dict) -> str:
        custom_path = str(config.get("condition_path") or "").strip()
        if custom_path:
            value = cls._dig(payload, custom_path)
            return str(value or "").strip()
        if isinstance(payload.get("now"), dict):
            return str(payload["now"].get("text") or "").strip()
        if isinstance(payload.get("attributes"), dict):
            attributes = payload["attributes"]
            if attributes.get("condition"):
                return str(attributes.get("condition") or "").strip()
        if payload.get("state") is not None:
            return str(payload.get("state") or "").strip()
        if isinstance(payload.get("current"), dict):
            code = payload["current"].get("weather_code")
            if code is not None:
                return f"weather_code:{code}"
        if isinstance(payload.get("current_weather"), dict):
            code = payload["current_weather"].get("weathercode")
            if code is not None:
                return f"weather_code:{code}"
        return ""

    @classmethod
    def _dig(cls, payload: dict, path: str) -> Any:
        current: Any = payload
        for part in path.split("."):
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    @classmethod
    def _to_float(cls, value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
