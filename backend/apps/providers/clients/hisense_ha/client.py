from __future__ import annotations

from copy import deepcopy
from typing import Any

import requests


class HisenseHAClient:
    login_base = "https://portal-account.hismarttv.com"
    api_base = "https://api-wg.hismarttv.com"
    refresh_base = "https://bas-wg.hismarttv.com"
    default_timeout_seconds = 10

    hvac_mode_lookup = {
        0: "fan_only",
        1: "heat",
        2: "cool",
        3: "dry",
        4: "auto",
    }
    fan_mode_lookup = {
        0: "auto",
        1: "diffuse",
        2: "low",
        3: "medium",
        4: "high",
    }
    swing_mode_lookup = {
        0: "off",
        1: "on",
        2: "horizontal",
        3: "vertical",
    }
    command_definitions = (
        {
            "key": "power",
            "label": "电源",
            "kind": "toggle",
            "writable": True,
            "action": "power",
        },
        {
            "key": "target_temperature",
            "label": "目标温度",
            "kind": "range",
            "writable": True,
            "command_id": 6,
            "range": {"min": 16, "max": 32, "step": 1},
            "unit": "°C",
        },
        {
            "key": "hvac_mode",
            "label": "运行模式",
            "kind": "enum",
            "writable": True,
            "command_id": 3,
            "options": [
                {"label": "送风", "value": "fan_only"},
                {"label": "制热", "value": "heat"},
                {"label": "制冷", "value": "cool"},
                {"label": "除湿", "value": "dry"},
                {"label": "自动", "value": "auto"},
            ],
        },
        {
            "key": "fan_mode",
            "label": "风速",
            "kind": "enum",
            "writable": True,
            "command_id": 1,
            "options": [
                {"label": "自动", "value": "auto"},
                {"label": "柔风", "value": "diffuse"},
                {"label": "低", "value": "low"},
                {"label": "中", "value": "medium"},
                {"label": "高", "value": "high"},
            ],
        },
        {
            "key": "swing_mode",
            "label": "扫风",
            "kind": "enum",
            "writable": True,
            "command_id": 62,
            "options": [
                {"label": "关闭", "value": "off"},
                {"label": "开", "value": "on"},
                {"label": "左右", "value": "horizontal"},
                {"label": "上下", "value": "vertical"},
            ],
        },
        {
            "key": "screen_on",
            "label": "屏显",
            "kind": "toggle",
            "writable": True,
            "command_id": 41,
        },
        {
            "key": "aux_heat",
            "label": "辅助加热",
            "kind": "toggle",
            "writable": True,
            "command_id": 28,
        },
        {
            "key": "refresh",
            "label": "刷新状态",
            "kind": "action",
            "writable": True,
            "action": "refresh_status",
        },
    )

    def __init__(self, payload: dict[str, Any]):
        self.payload = self.validate_payload(payload)
        self.session = requests.Session()
        self.timeout_seconds = max(int(self.payload.get("timeout_seconds") or self.default_timeout_seconds), 1)

    @classmethod
    def validate_payload(cls, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("hisense payload must be a JSON object")

        username = str(payload.get("username") or payload.get("account") or "").strip()
        password = str(payload.get("password") or "").strip()
        refresh_token = str(payload.get("refresh_token") or "").strip()

        if not username:
            raise ValueError("hisense username is required")
        if not password and not refresh_token:
            raise ValueError("hisense password or refresh_token is required")

        next_payload = dict(payload)
        next_payload["username"] = username
        if password:
            next_payload["password"] = password
        if refresh_token:
            next_payload["refresh_token"] = refresh_token

        home_id = str(payload.get("home_id") or "").strip()
        if home_id:
            next_payload["home_id"] = home_id

        device_ids = payload.get("device_ids")
        if device_ids is not None:
            if not isinstance(device_ids, list):
                raise ValueError("hisense device_ids must be a list")
            next_payload["device_ids"] = [str(item).strip() for item in device_ids if str(item).strip()]

        devices = payload.get("devices")
        if devices is not None:
            if not isinstance(devices, list):
                raise ValueError("hisense devices must be a list")
            next_payload["devices"] = [item for item in devices if isinstance(item, dict)]

        return next_payload

    def get_account_profile(self) -> dict[str, Any]:
        auth_state = self._login()
        homes = self.list_homes(access_token=auth_state["access_token"])
        if not homes:
            raise ValueError("Hisense account does not have any homes")

        configured_home_id = str(self.payload.get("home_id") or "").strip()
        home = next((item for item in homes if item["home_id"] == configured_home_id), homes[0])
        devices = self.list_home_devices(access_token=auth_state["access_token"], home_id=home["home_id"])
        selected_devices = self._select_devices(devices)
        self.payload["access_token"] = auth_state["access_token"]
        self.payload["refresh_token"] = auth_state["refresh_token"]
        self.payload["home_id"] = home["home_id"]
        self.payload["devices"] = deepcopy(selected_devices)

        return {
            "account": self.payload["username"],
            "nickname": self.payload["username"],
            "home_id": home["home_id"],
            "home_name": home["home_name"],
            "homes": homes,
            "devices": selected_devices,
            "instance_name": f"Hisense ({home['home_name']})",
            "auth_state": {
                "access_token": auth_state["access_token"],
                "refresh_token": auth_state["refresh_token"],
                "home_id": home["home_id"],
                "devices": selected_devices,
            },
        }

    def list_devices(self) -> list[dict[str, Any]]:
        access_token = self._ensure_access_token()
        devices = self.payload.get("devices")
        if not isinstance(devices, list) or not devices:
            home_id = str(self.payload.get("home_id") or "").strip()
            if not home_id:
                raise ValueError("hisense home_id is required")
            devices = self.list_home_devices(access_token=access_token, home_id=home_id)
        enriched: list[dict[str, Any]] = []
        for item in devices:
            raw = self.get_device_status(item["device_id"], item["wifi_id"], access_token=access_token)
            enriched.append(
                {
                    **item,
                    "brand": "Hisense",
                    "model": item.get("device_type_name") or "Air Conditioner",
                    "category": "climate",
                    "status_payload": raw["status_payload"],
                    "online": raw["power_on"] or raw["indoor_temperature"] is not None,
                    "controls": deepcopy(self.command_definitions),
                    "region": "CN",
                    "pin_available": False,
                }
            )
        return enriched

    def get_device(self, device_id: str) -> dict[str, Any]:
        devices = self.list_devices()
        for item in devices:
            if item.get("device_id") == device_id:
                return item
        raise ValueError(f"Hisense device not found: {device_id}")

    def execute_control(self, *, device_id: str, control_key: str, action: str | None = None, value: Any = None) -> dict[str, Any]:
        access_token = self._ensure_access_token()
        device = self._find_configured_device(device_id)
        wifi_id = device["wifi_id"]

        if control_key == "power":
            desired = bool(value if value is not None else action in {"turn_on", "on", "true", "1"})
            self._send_power(device_id=device_id, wifi_id=wifi_id, access_token=access_token, power_on=desired)
        elif control_key == "refresh":
            self.get_device_status(device_id=device_id, wifi_id=wifi_id, access_token=access_token)
        else:
            definition = next((item for item in self.command_definitions if item["key"] == control_key), None)
            if definition is None or "command_id" not in definition:
                raise ValueError(f"Unsupported Hisense control: {control_key}")
            command_value = self._normalize_command_value(control_key, value)
            self._send_logic_command(
                device_id=device_id,
                wifi_id=wifi_id,
                access_token=access_token,
                command_id=int(definition["command_id"]),
                command_value=command_value,
            )

        return self.get_device(device_id)

    def _login(self) -> dict[str, str]:
        password = str(self.payload.get("password") or "").strip()
        if not password:
            refresh_token = str(self.payload.get("refresh_token") or "").strip()
            if not refresh_token:
                raise ValueError("hisense password is required for first login")
            access_token = self._refresh_access_token(refresh_token)
            return {"access_token": access_token, "refresh_token": refresh_token}

        response = self.session.post(
            f"{self.login_base}/mobile/signon",
            headers={"Content-Type": "application/json;charset=utf-8"},
            json={
                "pdateTime": "0",
                "version": "1.0",
                "deviceType": "1",
                "appType": "100",
                "versionCode": "101",
                "adaptertRank": "3098",
                "distributeId": "2001",
                "loginName": self.payload["username"],
                "serverCode": "9501",
                "signature": password,
            },
            params={
                "lastUpdateTime": "0",
                "version": "1.0",
                "deviceType": "2",
                "appType": "100",
                "versionCode": "101",
                "adaptertRank": "4130",
                "_": str(self._timestamp_ms()),
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json() or {}
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        if data.get("resultCode") != 0:
            raise ValueError("Hisense login failed")
        token_info = data.get("tokenInfo") if isinstance(data.get("tokenInfo"), dict) else {}
        access_token = str(token_info.get("token") or "").strip()
        refresh_token = str(token_info.get("refreshToken") or "").strip()
        if not access_token or not refresh_token:
            raise ValueError("Hisense login response missing token info")
        self.payload["access_token"] = access_token
        self.payload["refresh_token"] = refresh_token
        return {"access_token": access_token, "refresh_token": refresh_token}

    def list_homes(self, *, access_token: str) -> list[dict[str, str]]:
        payload = self._request_json(
            "GET",
            f"{self.api_base}/wg/dm/getHomeList",
            params={
                "sign": "",
                "languageId": "0",
                "version": "8.0",
                "accessToken": access_token,
                "timezone": "28800",
                "format": "1",
                "timeStamp": str(self._timestamp_ms()),
            },
            headers=self._api_headers(),
        )
        response = payload.get("response") if isinstance(payload.get("response"), dict) else {}
        if response.get("resultCode") != 0:
            raise ValueError("Hisense getHomeList failed")
        homes = []
        for item in response.get("homeList") or []:
            if not isinstance(item, dict):
                continue
            home_id = str(item.get("homeId") or "").strip()
            if not home_id:
                continue
            homes.append(
                {
                    "home_id": home_id,
                    "home_name": str(item.get("homeName") or home_id).strip(),
                }
            )
        return homes

    def list_home_devices(self, *, access_token: str, home_id: str) -> list[dict[str, Any]]:
        payload = self._request_json(
            "GET",
            f"{self.api_base}/wg/dm/getHomeDeviceList",
            params={
                "sign": "",
                "languageId": "0",
                "version": "8.0",
                "accessToken": access_token,
                "homeId": home_id,
                "timezone": "28800",
                "format": "1",
                "timeStamp": str(self._timestamp_ms()),
            },
            headers=self._api_headers(),
        )
        response = payload.get("response") if isinstance(payload.get("response"), dict) else {}
        if response.get("resultCode") != 0:
            raise ValueError("Hisense getHomeDeviceList failed")
        devices = []
        for item in response.get("deviceList") or []:
            if not isinstance(item, dict):
                continue
            device_type_name = str(item.get("deviceTypeName") or "").strip()
            if "空调" not in device_type_name:
                continue
            device_id = str(item.get("deviceId") or "").strip()
            wifi_id = str(item.get("wifiId") or "").strip()
            if not device_id or not wifi_id:
                continue
            label = self._device_label(item, device_id)
            devices.append(
                {
                    "device_id": device_id,
                    "wifi_id": wifi_id,
                    "name": label,
                    "device_name": str(item.get("deviceName") or "").strip(),
                    "device_type_name": device_type_name,
                    "room_name": str(item.get("roomName") or "").strip(),
                    "device_nick_name": str(item.get("deviceNickName") or "").strip(),
                }
            )
        return devices

    def get_device_status(self, *, device_id: str, wifi_id: str, access_token: str) -> dict[str, Any]:
        payload = self._request_json(
            "POST",
            f"{self.api_base}/agw/dsg/outer/getDeviceLogicalStatusArray",
            params={"accessToken": access_token},
            headers=self._command_headers(),
            json_body={"deviceList": [{"wifiId": wifi_id, "deviceId": device_id}]},
        )
        response = payload.get("response") if isinstance(payload.get("response"), dict) else {}
        if response.get("resultCode") != 0:
            raise ValueError("Hisense getDeviceLogicalStatusArray failed")
        status_value = ""
        device_status_list = response.get("deviceStatusList")
        if isinstance(device_status_list, list) and device_status_list:
            first = device_status_list[0] if isinstance(device_status_list[0], dict) else {}
            status_value = str(first.get("deviceStatus") or "")
        if not status_value:
            status_value = str(response.get("preStatus") or "")
        status_payload = self._parse_status(status_value)
        return status_payload

    def _send_power(self, *, device_id: str, wifi_id: str, access_token: str, power_on: bool) -> None:
        payload = self._request_json(
            "POST",
            f"{self.api_base}/agw/dsg/outer/sendDeviceModelCmd",
            params={"accessToken": access_token},
            headers=self._command_headers(),
            json_body={
                "wifiId": wifi_id,
                "deviceId": device_id,
                "extendParam": "1",
                "cmdVersion": "0",
                "attributes": '{"onAndOff":"On"}' if power_on else '{"onAndOff":"Off"}',
            },
        )
        response = payload.get("response") if isinstance(payload.get("response"), dict) else {}
        if response.get("resultCode") != 0:
            raise ValueError("Hisense sendDeviceModelCmd failed")

    def _send_logic_command(
        self,
        *,
        device_id: str,
        wifi_id: str,
        access_token: str,
        command_id: int,
        command_value: int,
    ) -> None:
        payload = self._request_json(
            "POST",
            f"{self.api_base}/agw/dsg/outer/uploadRemoteLogicCmd",
            params={"accessToken": access_token},
            headers=self._command_headers(),
            json_body={
                "wifiId": wifi_id,
                "deviceId": device_id,
                "extendParm": "1",
                "cmdVersion": "1684085201",
                "cmdList": [{"cmdId": command_id, "cmdOrder": 0, "cmdParm": command_value, "delayTime": 0}],
            },
        )
        response = payload.get("response") if isinstance(payload.get("response"), dict) else {}
        if response.get("resultCode") != 0:
            raise ValueError("Hisense uploadRemoteLogicCmd failed")

    def _ensure_access_token(self) -> str:
        access_token = str(self.payload.get("access_token") or "").strip()
        if access_token:
            return access_token
        refresh_token = str(self.payload.get("refresh_token") or "").strip()
        if not refresh_token:
            auth_state = self._login()
            return auth_state["access_token"]
        access_token = self._refresh_access_token(refresh_token)
        self.payload["access_token"] = access_token
        return access_token

    def _refresh_access_token(self, refresh_token: str) -> str:
        response = self.session.post(
            f"{self.refresh_base}/aaa/refresh_token2",
            headers=self._refresh_headers(),
            data={
                "refreshToken": refresh_token,
                "appKey": "1234567890",
                "format": "1",
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list) or not payload:
            raise ValueError("Hisense refresh token response is invalid")
        first = payload[0] if isinstance(payload[0], dict) else {}
        access_token = str(first.get("token") or "").strip()
        if not access_token:
            raise ValueError("Hisense refresh token response does not contain token")
        return access_token

    def _find_configured_device(self, device_id: str) -> dict[str, Any]:
        devices = self.payload.get("devices")
        if not isinstance(devices, list):
            raise ValueError("hisense devices are not configured")
        for item in devices:
            if str(item.get("device_id") or "").strip() == device_id:
                return item
        raise ValueError(f"Hisense configured device not found: {device_id}")

    def _select_devices(self, devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
        configured_ids = set(self.payload.get("device_ids") or [])
        if configured_ids:
            selected = [item for item in devices if item["device_id"] in configured_ids]
            if selected:
                return selected
        return devices

    @classmethod
    def _device_label(cls, device: dict[str, Any], device_id: str) -> str:
        room = str(device.get("roomName") or "").strip()
        nick = str(device.get("deviceNickName") or "").strip()
        if room and nick:
            return f"{room}-{nick}"
        if room:
            return room
        if nick:
            return nick
        name = str(device.get("deviceName") or "").strip()
        return name or device_id

    @classmethod
    def _parse_status(cls, status_value: str) -> dict[str, Any]:
        parts = [int(item) for item in status_value.split(",") if str(item).strip()] if status_value else []
        def read(index: int, default: int | None = None):
            return parts[index] if len(parts) > index else default

        hvac_mode_id = read(4, 4)
        fan_mode_id = read(0, 0)
        swing_mode_id = read(209, 0)
        return {
            "power_on": read(5, 0) == 1,
            "desired_temperature": read(9),
            "indoor_temperature": read(10),
            "hvac_mode_id": hvac_mode_id,
            "hvac_mode": cls.hvac_mode_lookup.get(hvac_mode_id, "auto"),
            "fan_mode_id": fan_mode_id,
            "fan_mode": cls.fan_mode_lookup.get(fan_mode_id, "auto"),
            "screen_on": read(58, 1) == 1,
            "aux_heat": read(45, 0) == 1,
            "nature_wind": read(44, 0) == 1,
            "swing_mode_id": swing_mode_id,
            "swing_mode": cls.swing_mode_lookup.get(swing_mode_id, "off"),
            "status_payload": {
                "power_on": read(5, 0) == 1,
                "desired_temperature": read(9),
                "indoor_temperature": read(10),
                "hvac_mode": cls.hvac_mode_lookup.get(hvac_mode_id, "auto"),
                "fan_mode": cls.fan_mode_lookup.get(fan_mode_id, "auto"),
                "screen_on": read(58, 1) == 1,
                "aux_heat": read(45, 0) == 1,
                "nature_wind": read(44, 0) == 1,
                "swing_mode": cls.swing_mode_lookup.get(swing_mode_id, "off"),
            },
        }

    @classmethod
    def _normalize_command_value(cls, control_key: str, value: Any) -> int:
        if control_key in {"screen_on", "aux_heat"}:
            return 1 if bool(value) else 0
        if control_key == "target_temperature":
            numeric = int(value)
            return max(16, min(32, numeric))
        if control_key == "hvac_mode":
            mapping = {mode: index for index, mode in cls.hvac_mode_lookup.items()}
            if str(value) not in mapping:
                raise ValueError(f"Unsupported Hisense hvac_mode: {value}")
            return int(mapping[str(value)])
        if control_key == "fan_mode":
            mapping = {mode: index for index, mode in cls.fan_mode_lookup.items()}
            if str(value) not in mapping:
                raise ValueError(f"Unsupported Hisense fan_mode: {value}")
            return int(mapping[str(value)])
        if control_key == "swing_mode":
            mapping = {mode: index for index, mode in cls.swing_mode_lookup.items()}
            if str(value) not in mapping:
                raise ValueError(f"Unsupported Hisense swing_mode: {value}")
            return int(mapping[str(value)])
        raise ValueError(f"Unsupported Hisense command key: {control_key}")

    @classmethod
    def _timestamp_ms(cls) -> int:
        import time

        return int(time.time() * 1000)

    @classmethod
    def _api_headers(cls) -> dict[str, str]:
        return {
            "Host": "api.wg.hismarttv.com",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": "okhttp/4.10.0",
        }

    @classmethod
    def _command_headers(cls) -> dict[str, str]:
        return {
            "Host": "api-wg.hismarttv.com",
            "Content-Type": "application/json",
            "Connection": "keep-alive",
            "Accept": "*/*",
            "User-Agent": "%E6%B5%B7%E4%BF%A1%E6%99%BA%E6%85%A7%E5%AE%B6/4 CFNetwork/1492.0.1 Darwin/23.3.0",
            "Accept-Language": "zh-CN,zh-Hans;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        }

    @classmethod
    def _refresh_headers(cls) -> dict[str, str]:
        return {
            "Host": "bas-wg.hismarttv.com",
            "Content-Type": "application/x-www-form-urlencoded",
            "Connection": "keep-alive",
            "Accept": "*/*",
            "User-Agent": "%E6%B5%B7%E4%BF%A1%E6%99%BA%E6%85%A7%E5%AE%B6/4 CFNetwork/1492.0.1 Darwin/23.3.0",
            "Accept-Language": "zh-CN,zh-Hans;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        }

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = self.session.request(
            method,
            url,
            params=params,
            headers=headers,
            json=json_body,
            data=data,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) and not isinstance(payload, list):
            raise ValueError("Hisense API returned invalid payload")
        return payload
