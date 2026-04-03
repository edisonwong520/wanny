from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable

import aiohttp
import requests
from google.protobuf.json_format import MessageToDict

from .proto_runtime import load_proto_modules


REGION_EUROPE = "Europe"
REGION_NORAM = "North America"
REGION_APAC = "Asia-Pacific"
REGION_CHINA = "China"

REST_API_BASE = "https://bff.emea-prod.mobilesdk.mercedes-benz.com"
REST_API_BASE_CN = "https://bff.cn-prod.mobilesdk.mercedes-benz.com"
REST_API_BASE_NA = "https://bff.amap-prod.mobilesdk.mercedes-benz.com"
REST_API_BASE_PA = "https://bff.amap-prod.mobilesdk.mercedes-benz.com"
WEBSOCKET_API_BASE = "wss://websocket.emea-prod.mobilesdk.mercedes-benz.com/v2/ws"
WEBSOCKET_API_BASE_NA = "wss://websocket.amap-prod.mobilesdk.mercedes-benz.com/v2/ws"
WEBSOCKET_API_BASE_PA = "wss://websocket.amap-prod.mobilesdk.mercedes-benz.com/v2/ws"
WEBSOCKET_API_BASE_CN = "wss://websocket.cn-prod.mobilesdk.mercedes-benz.com/v2/ws"

LOGIN_BASE_URI = "https://id.mercedes-benz.com"
LOGIN_BASE_URI_CN = "https://ciam-1.mercedes-benz.com.cn"

RIS_APPLICATION_VERSION = "1.63.0 (3044)"
RIS_APPLICATION_VERSION_NA = "3.63.0"
RIS_APPLICATION_VERSION_CN = "1.63.0"
RIS_APPLICATION_VERSION_PA = "1.63.0"
RIS_SDK_VERSION = "3.26.2"
RIS_OS_VERSION = "26.3"
RIS_OS_NAME = "ios"

X_APPLICATIONNAME_ECE = "mycar-store-ece"
X_APPLICATIONNAME_US = "mycar-store-us"
X_APPLICATIONNAME_AP = "mycar-store-ap"
X_APPLICATIONNAME_CN = "mycar-store-cn"

WEBSOCKET_USER_AGENT = "Mercedes-Benz/3044 CFNetwork/3860.400.22 Darwin/25.3.0"
WEBSOCKET_USER_AGENT_CN = "MyStarCN/1.63.0 (com.daimler.ris.mercedesme.cn.ios; build:1758; iOS 16.3.1) Alamofire/5.4.0"
WEBSOCKET_USER_AGENT_PA = f"mycar-store-ap {RIS_APPLICATION_VERSION}, {RIS_OS_NAME} {RIS_OS_VERSION}, SDK {RIS_SDK_VERSION}"
WEBSOCKET_USER_AGENT_US = f"mycar-store-us v{RIS_APPLICATION_VERSION_NA}, {RIS_OS_NAME} {RIS_OS_VERSION}, SDK {RIS_SDK_VERSION}"

DEFAULT_LOCALE = "en-GB"
RIS_SDK_VERSION_CN = "2.132.2"

REGION_ALIASES = {
    "eu": REGION_EUROPE,
    "europe": REGION_EUROPE,
    "emea": REGION_EUROPE,
    "na": REGION_NORAM,
    "us": REGION_NORAM,
    "noram": REGION_NORAM,
    "north america": REGION_NORAM,
    "ap": REGION_APAC,
    "apac": REGION_APAC,
    "asia-pacific": REGION_APAC,
    "asia pacific": REGION_APAC,
    "cn": REGION_CHINA,
    "china": REGION_CHINA,
}


@dataclass
class MbApi2020Vehicle:
    vin: str
    name: str
    model: str
    fuel_type: str
    license_plate: str
    fin: str
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.vin,
            "vin": self.vin,
            "name": self.name,
            "model": self.model,
            "fuel_type": self.fuel_type,
            "license_plate": self.license_plate,
            "fin": self.fin,
            "raw": self.raw,
        }


class MbApi2020Client:
    default_timeout_seconds = 15

    def __init__(self, payload: dict[str, Any], *, on_token_update: Callable[[dict[str, Any]], None] | None = None):
        self.payload = self.validate_payload(payload)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Wanny-MbApi2020/0.1",
                "Accept": "application/json",
            }
        )
        self._session_id = str(uuid.uuid4())
        self._on_token_update = on_token_update

    @classmethod
    def normalize_payload(cls, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("mbapi2020 payload must be a JSON object")

        normalized = dict(payload)
        for source_key, target_key in (
            ("token", "access_token"),
            ("bearer_token", "access_token"),
            ("base_url", "api_base"),
            ("username", "account"),
            ("email", "account"),
        ):
            value = normalized.get(source_key)
            if value and not normalized.get(target_key):
                normalized[target_key] = value

        region_value = str(normalized.get("region") or normalized.get("server") or REGION_EUROPE).strip()
        normalized["region"] = cls._normalize_region(region_value)
        normalized["api_base"] = str(normalized.get("api_base") or cls._resolve_rest_base(normalized["region"])).strip().rstrip("/")
        normalized["login_base"] = str(normalized.get("login_base") or cls._resolve_login_base(normalized["region"])).strip().rstrip("/")
        normalized["locale"] = str(normalized.get("locale") or DEFAULT_LOCALE).strip()
        normalized["access_token"] = str(normalized.get("access_token") or "").strip()
        normalized["refresh_token"] = str(normalized.get("refresh_token") or "").strip()
        normalized["account"] = str(normalized.get("account") or "").strip()
        normalized["device_guid"] = str(normalized.get("device_guid") or uuid.uuid4()).strip()
        normalized["pin_available"] = bool(normalized.get("pin_available"))

        expires_at = normalized.get("expires_at")
        expires_in = normalized.get("expires_in")
        if expires_at in ("", None) and expires_in not in ("", None):
            try:
                normalized["expires_at"] = int(time.time()) + int(expires_in)
            except (TypeError, ValueError):
                pass
        elif expires_at not in ("", None):
            try:
                normalized["expires_at"] = int(expires_at)
            except (TypeError, ValueError):
                raise ValueError("mbapi2020 expires_at must be an integer timestamp") from None

        return normalized

    @classmethod
    def validate_payload(cls, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = cls.normalize_payload(payload)
        if not normalized["access_token"]:
            raise ValueError("mbapi2020 access_token is required")
        return normalized

    @staticmethod
    def _normalize_region(value: Any) -> str:
        if value in (REGION_EUROPE, REGION_NORAM, REGION_APAC, REGION_CHINA):
            return str(value)
        normalized = str(value or "").strip().lower()
        if normalized in REGION_ALIASES:
            return REGION_ALIASES[normalized]
        raise ValueError("Unsupported mbapi2020 region, expected Europe/North America/Asia-Pacific/China")

    @staticmethod
    def _resolve_rest_base(region: str) -> str:
        if region == REGION_CHINA:
            return REST_API_BASE_CN
        if region == REGION_NORAM:
            return REST_API_BASE_NA
        if region == REGION_APAC:
            return REST_API_BASE_PA
        return REST_API_BASE

    @staticmethod
    def _resolve_login_base(region: str) -> str:
        if region == REGION_CHINA:
            return LOGIN_BASE_URI_CN
        return LOGIN_BASE_URI

    @staticmethod
    def _resolve_websocket_base(region: str) -> str:
        if region == REGION_CHINA:
            return WEBSOCKET_API_BASE_CN
        if region == REGION_NORAM:
            return WEBSOCKET_API_BASE_NA
        if region == REGION_APAC:
            return WEBSOCKET_API_BASE_PA
        return WEBSOCKET_API_BASE

    def _get_region_headers(self) -> dict[str, str]:
        headers = {
            "Ris-Os-Name": RIS_OS_NAME,
            "Ris-Os-Version": RIS_OS_VERSION,
            "Ris-Sdk-Version": RIS_SDK_VERSION,
            "X-Locale": self.payload["locale"],
            "X-Trackingid": str(uuid.uuid4()),
            "X-Sessionid": self._session_id,
            "User-Agent": WEBSOCKET_USER_AGENT,
            "Content-Type": "application/json",
            "Accept-Language": self.payload["locale"],
        }
        region = self.payload["region"]
        if region == REGION_NORAM:
            headers["X-Applicationname"] = X_APPLICATIONNAME_US
            headers["Ris-Application-Version"] = RIS_APPLICATION_VERSION_NA
            headers["User-Agent"] = WEBSOCKET_USER_AGENT_US
        elif region == REGION_APAC:
            headers["X-Applicationname"] = X_APPLICATIONNAME_AP
            headers["Ris-Application-Version"] = RIS_APPLICATION_VERSION_PA
            headers["User-Agent"] = WEBSOCKET_USER_AGENT_PA
        elif region == REGION_CHINA:
            headers["X-Applicationname"] = X_APPLICATIONNAME_CN
            headers["Ris-Application-Version"] = RIS_APPLICATION_VERSION_CN
            headers["User-Agent"] = WEBSOCKET_USER_AGENT_CN
        else:
            headers["X-Applicationname"] = X_APPLICATIONNAME_ECE
            headers["Ris-Application-Version"] = RIS_APPLICATION_VERSION
        return headers

    def _get_websocket_headers(self) -> dict[str, str]:
        headers = {
            "Authorization": self._ensure_access_token(),
            "APP-SESSION-ID": self._session_id,
            "OUTPUT-FORMAT": "PROTO",
            "X-SessionId": self._session_id,
            "X-TrackingId": str(uuid.uuid4()).upper(),
            "ris-os-name": RIS_OS_NAME,
            "ris-os-version": RIS_OS_VERSION,
            "ris-sdk-version": RIS_SDK_VERSION,
            "X-Locale": self.payload["locale"],
            "User-Agent": WEBSOCKET_USER_AGENT,
        }
        region = self.payload["region"]
        if region == REGION_NORAM:
            headers["X-ApplicationName"] = X_APPLICATIONNAME_US
            headers["ris-application-version"] = RIS_APPLICATION_VERSION_NA
            headers["User-Agent"] = WEBSOCKET_USER_AGENT_US
            headers["X-Locale"] = "en-US"
            headers["Accept-Encoding"] = "gzip"
            headers["Sec-WebSocket-Extensions"] = "permessage-deflate"
        elif region == REGION_APAC:
            headers["X-ApplicationName"] = X_APPLICATIONNAME_AP
            headers["ris-application-version"] = RIS_APPLICATION_VERSION_PA
            headers["User-Agent"] = WEBSOCKET_USER_AGENT_PA
        elif region == REGION_CHINA:
            headers["X-ApplicationName"] = X_APPLICATIONNAME_CN
            headers["ris-application-version"] = RIS_APPLICATION_VERSION_CN
            headers["User-Agent"] = WEBSOCKET_USER_AGENT_CN
            headers["ris-sdk-version"] = RIS_SDK_VERSION_CN
        else:
            headers["X-ApplicationName"] = X_APPLICATIONNAME_ECE
            headers["ris-application-version"] = RIS_APPLICATION_VERSION
        return headers

    def export_state(self) -> dict[str, Any]:
        state = {
            "region": self.payload["region"],
            "api_base": self.payload["api_base"],
            "login_base": self.payload["login_base"],
            "locale": self.payload["locale"],
            "access_token": self.payload["access_token"],
        }
        if self.payload.get("refresh_token"):
            state["refresh_token"] = self.payload["refresh_token"]
        if self.payload.get("expires_at") is not None:
            state["expires_at"] = self.payload["expires_at"]
        if self.payload.get("account"):
            state["account"] = self.payload["account"]
        if self.payload.get("device_guid"):
            state["device_guid"] = self.payload["device_guid"]
        return state

    def _publish_token_update(self) -> None:
        if self._on_token_update is None:
            return
        self._on_token_update(self.export_state())

    def _token_is_expired(self) -> bool:
        expires_at = self.payload.get("expires_at")
        if expires_at is None:
            return False
        return int(expires_at) - int(time.time()) < 60

    def _refresh_access_token(self) -> None:
        refresh_token = self.payload.get("refresh_token")
        if not refresh_token:
            raise ValueError("mbapi2020 access token expired and refresh_token is missing")

        preflight_headers = self._get_region_headers()
        self.session.get(
            f"{self.payload['api_base']}/v1/config",
            headers=preflight_headers,
            timeout=self.default_timeout_seconds,
        ).raise_for_status()

        headers = self._get_region_headers()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["X-Request-Id"] = str(uuid.uuid4())
        headers["X-Device-Id"] = self.payload["device_guid"]
        url = f"{self.payload['login_base']}/as/token.oauth2"
        response = self.session.post(
            url,
            data=f"grant_type=refresh_token&refresh_token={refresh_token}",
            headers=headers,
            timeout=self.default_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        access_token = str(data.get("access_token") or "").strip()
        if not access_token:
            raise ValueError("mbapi2020 token refresh response does not contain access_token")

        self.payload["access_token"] = access_token
        if data.get("refresh_token"):
            self.payload["refresh_token"] = str(data["refresh_token"]).strip()
        expires_in = data.get("expires_in")
        if expires_in not in ("", None):
            self.payload["expires_at"] = int(time.time()) + int(expires_in)
        self._publish_token_update()

    def _ensure_access_token(self) -> str:
        if self._token_is_expired():
            self._refresh_access_token()
        access_token = str(self.payload.get("access_token") or "").strip()
        if not access_token:
            raise ValueError("mbapi2020 access_token is required")
        return access_token

    def _request_json(self, method: str, endpoint: str, *, base_url: str | None = None, **kwargs) -> Any:
        token = self._ensure_access_token()
        url = endpoint if endpoint.startswith("http") else f"{(base_url or self.payload['api_base']).rstrip('/')}{endpoint}"
        headers = self._get_region_headers()
        headers["Authorization"] = f"Bearer {token}"
        extra_headers = kwargs.pop("headers", None) or {}
        headers.update(extra_headers)
        response = self.session.request(
            method=method,
            url=url,
            headers=headers,
            timeout=self.default_timeout_seconds,
            **kwargs,
        )
        response.raise_for_status()
        return response.json()

    def _request_bytes(self, method: str, endpoint: str, *, base_url: str | None = None, **kwargs) -> bytes:
        token = self._ensure_access_token()
        url = endpoint if endpoint.startswith("http") else f"{(base_url or self.payload['api_base']).rstrip('/')}{endpoint}"
        headers = self._get_region_headers()
        headers["Authorization"] = f"Bearer {token}"
        extra_headers = kwargs.pop("headers", None) or {}
        headers.update(extra_headers)
        response = self.session.request(
            method=method,
            url=url,
            headers=headers,
            timeout=self.default_timeout_seconds,
            **kwargs,
        )
        response.raise_for_status()
        return response.content

    @staticmethod
    def _extract_attribute_value(payload: Any) -> Any:
        if not isinstance(payload, dict):
            return payload
        if payload.get("nil_value") is True:
            return None
        for key in (
            "display_value",
            "bool_value",
            "int_value",
            "float_value",
            "double_value",
            "string_value",
            "value",
        ):
            if key in payload and payload.get(key) not in (None, ""):
                value = payload.get(key)
                if isinstance(value, dict):
                    extracted = MbApi2020Client._extract_attribute_value(value)
                    if extracted not in (None, "", {}, []):
                        return extracted
                return value
        if "formatted_value" in payload:
            formatted = payload.get("formatted_value")
            if isinstance(formatted, dict):
                extracted = MbApi2020Client._extract_attribute_value(formatted)
                if extracted not in (None, "", {}, []):
                    return extracted
            return formatted
        if "timestamp" in payload and len(payload) == 1:
            return payload.get("timestamp")
        return payload

    @staticmethod
    def _extract_vehicle_list(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("items", "vehicles", "results", "assignedVehicles"):
                items = payload.get(key)
                if isinstance(items, list):
                    return [item for item in items if isinstance(item, dict)]
        return []

    @staticmethod
    def _normalize_vehicle(vehicle: dict[str, Any]) -> MbApi2020Vehicle:
        sales_related_information = vehicle.get("salesRelatedInformation") or {}
        baumuster = sales_related_information.get("baumuster") if isinstance(sales_related_information, dict) else {}
        baumuster_description = ""
        if isinstance(baumuster, dict):
            baumuster_description = str(baumuster.get("baumusterDescription") or "").strip()
        vin = str(
            vehicle.get("vin")
            or vehicle.get("vehicleVin")
            or vehicle.get("finOrVin")
            or vehicle.get("id")
            or ""
        ).strip()
        model = str(
            vehicle.get("modelName")
            or baumuster_description
            or vehicle.get("model")
            or vehicle.get("carline")
            or ""
        ).strip()
        name = str(
            vehicle.get("name")
            or vehicle.get("vehicleName")
            or vehicle.get("title")
            or model
            or vin
        ).strip()
        fuel_type = str(vehicle.get("fuelType") or vehicle.get("driveType") or "").strip()
        license_plate = str(vehicle.get("licensePlate") or vehicle.get("licenseplate") or "").strip()
        fin = str(vehicle.get("fin") or vehicle.get("finOrVin") or "").strip()
        return MbApi2020Vehicle(
            vin=vin,
            name=name,
            model=model,
            fuel_type=fuel_type,
            license_plate=license_plate,
            fin=fin,
            raw=vehicle,
        )

    def get_account_profile(self) -> dict[str, Any]:
        user = self._request_json("GET", "/v1/user")
        vehicles_payload = self._request_json("GET", "/v2/vehicles")
        vehicles = [self._normalize_vehicle(item).to_dict() for item in self._extract_vehicle_list(vehicles_payload)]
        return {
            "account": str(user.get("email") or user.get("login") or self.payload.get("account") or "").strip(),
            "connected": True,
            "region": self.payload["region"],
            "api_base": self.payload["api_base"],
            "locale": self.payload["locale"],
            "nickname": str(user.get("firstName") or user.get("preferredName") or user.get("name") or "").strip(),
            "vehicles": vehicles,
            "pin_available": str(user.get("userPinStatus") or "").strip().upper() == "SET",
            "auth_state": self.export_state(),
        }

    def list_vehicles(self) -> list[dict[str, Any]]:
        vehicles_payload = self._request_json("GET", "/v2/vehicles")
        return [self._normalize_vehicle(item).to_dict() for item in self._extract_vehicle_list(vehicles_payload)]

    def get_vehicle_capabilities(self, vin: str) -> dict[str, Any]:
        normalized_vin = str(vin or "").strip()
        if not normalized_vin:
            raise ValueError("mbapi2020 vin is required")
        payload = self._request_json("GET", f"/v1/vehicle/{normalized_vin}/capabilities")
        if isinstance(payload, dict):
            return payload
        return {"data": payload}

    def get_vehicle_command_capabilities(self, vin: str) -> dict[str, Any]:
        normalized_vin = str(vin or "").strip()
        if not normalized_vin:
            raise ValueError("mbapi2020 vin is required")
        payload = self._request_json("GET", f"/v1/vehicle/{normalized_vin}/capabilities/commands")
        if isinstance(payload, dict):
            return payload
        return {"data": payload}

    def get_vehicle_status(self, vin: str) -> dict[str, Any]:
        normalized_vin = str(vin or "").strip()
        if not normalized_vin:
            raise ValueError("mbapi2020 vin is required")
        raw = self._request_bytes(
            "GET",
            f"/v1/vehicle/{normalized_vin}/vehicleattributes",
            base_url=self._resolve_widget_base(self.payload["region"]),
        )

        modules = load_proto_modules()
        vehicle_events_pb2 = modules["vehicle_events_pb2"]
        message = vehicle_events_pb2.VEPUpdate()
        message.ParseFromString(raw)
        payload = MessageToDict(message, preserving_proto_field_name=True)
        attributes = payload.get("attributes") or {}
        payload["status_payload"] = {
            key: self._extract_attribute_value(value)
            for key, value in attributes.items()
        }
        return payload

    @staticmethod
    def _resolve_widget_base(region: str) -> str:
        env = "emea"
        if region in (REGION_APAC, REGION_NORAM):
            env = "amap"
        elif region == REGION_CHINA:
            env = "cn"
        return f"https://widget.{env}-prod.mobilesdk.mercedes-benz.com"

    def get_device(self, vehicle_id: str) -> dict[str, Any] | None:
        normalized_vin = str(vehicle_id or "").strip()
        if not normalized_vin:
            return None
        vehicle = next((item for item in self.list_vehicles() if str(item.get("vin")) == normalized_vin), None)
        if vehicle is None:
            return None
        capabilities = self.get_vehicle_capabilities(normalized_vin)
        command_capabilities = self.get_vehicle_command_capabilities(normalized_vin)
        status_payload = self.get_vehicle_status(normalized_vin)
        vehicle["vehicle_information"] = capabilities.get("vehicle", {})
        vehicle["features"] = capabilities.get("features", {})
        vehicle["command_capabilities"] = command_capabilities.get("commands", [])
        vehicle["status_payload"] = status_payload.get("status_payload", {})
        vehicle["status_raw"] = status_payload
        vehicle["region"] = self.payload["region"]
        vehicle["pin_available"] = bool(self.payload.get("pin")) or bool(self.payload.get("pin_available"))
        return vehicle

    def list_devices(self) -> list[dict[str, Any]]:
        devices: list[dict[str, Any]] = []
        for vehicle in self.list_vehicles():
            vin = str(vehicle.get("vin") or "").strip()
            if not vin:
                continue
            capabilities = {}
            command_capabilities = {}
            status_payload = {}
            try:
                capabilities = self.get_vehicle_capabilities(vin)
            except Exception:
                capabilities = {}
            try:
                command_capabilities = self.get_vehicle_command_capabilities(vin)
            except Exception:
                command_capabilities = {}
            try:
                status_payload = self.get_vehicle_status(vin)
            except Exception:
                status_payload = {}

            devices.append(
                {
                    **vehicle,
                    "vehicle_information": capabilities.get("vehicle", {}),
                    "features": capabilities.get("features", {}),
                    "command_capabilities": command_capabilities.get("commands", []),
                    "status_payload": status_payload.get("status_payload", {}),
                    "status_raw": status_payload,
                    "region": self.payload["region"],
                    "pin_available": bool(self.payload.get("pin")) or bool(self.payload.get("pin_available")),
                }
            )
        return devices

    async def _send_command_over_websocket(self, message_bytes: bytes) -> None:
        websocket_url = self._resolve_websocket_base(self.payload["region"])
        headers = self._get_websocket_headers()
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(websocket_url, headers=headers, heartbeat=20) as websocket:
                await websocket.send_bytes(message_bytes)
                await asyncio.sleep(0.2)

    def _build_command_message(self, vin: str, command_name: str, *, pin: str = "") -> bytes:
        modules = load_proto_modules()
        client_pb2 = modules["client_pb2"]
        vehicle_commands_pb2 = modules["vehicle_commands_pb2"]

        message = client_pb2.ClientMessage()
        message.commandRequest.vin = vin
        message.commandRequest.request_id = str(uuid.uuid4())

        normalized = str(command_name or "").strip().upper()
        if normalized == "DOORS_LOCK":
            message.commandRequest.doors_lock.doors.extend([])
        elif normalized == "DOORS_UNLOCK":
            if not pin:
                raise ValueError("奔驰解锁需要 PIN")
            message.commandRequest.doors_unlock.pin = pin
        elif normalized == "ZEV_PRECONDITIONING_START":
            message.commandRequest.zev_preconditioning_start.departure_time = 0
            message.commandRequest.zev_preconditioning_start.type = vehicle_commands_pb2.ZEVPreconditioningType.now
        elif normalized == "ZEV_PRECONDITIONING_STOP":
            message.commandRequest.zev_preconditioning_stop.type = vehicle_commands_pb2.ZEVPreconditioningType.now
        elif normalized == "SIGPOS_START":
            message.commandRequest.sigpos_start.light_type = 1
            message.commandRequest.sigpos_start.sigpos_type = 0
        elif normalized == "HVBATTERY_START_CONDITIONING":
            message.commandRequest.hv_battery_start_conditioning.CopyFrom(vehicle_commands_pb2.HvBatteryStartConditioning())
        elif normalized == "HVBATTERY_STOP_CONDITIONING":
            message.commandRequest.hv_battery_stop_conditioning.CopyFrom(vehicle_commands_pb2.HvBatteryStopConditioning())
        else:
            raise ValueError(f"Unsupported Mercedes command: {command_name}")

        return message.SerializeToString()

    def execute_control(self, *, vehicle_id: str, control: dict[str, Any], value: Any = None) -> None:
        action_params = dict(control.get("action_params") or {})
        command_name = str(action_params.get("command_name") or value or "").strip()
        if not command_name:
            raise ValueError("Mercedes command metadata is incomplete")

        pin = str(action_params.get("pin") or self.payload.get("pin") or "").strip()
        message_bytes = self._build_command_message(str(vehicle_id), command_name, pin=pin)
        asyncio.run(self._send_command_over_websocket(message_bytes))
