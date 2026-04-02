from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from secrets import token_hex
from typing import Any

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from .lua_codec import MideaLuaCodec, ensure_lua_support_files, lua_runtime_available
from .mappings import get_device_mapping

logger = logging.getLogger(__name__)


MIDEA_CLOUDS = {
    1: {
        "name": "MSmartHome",
        "app_key": "ac21b9f9cbfe4ca5a88562ef25e2b768",
        "iot_key": bytes.fromhex(format(7882822598523843940, "x")).decode(),
        "hmac_key": bytes.fromhex(format(117390035944627627450677220413733956185864939010425, "x")).decode(),
        "api_url": "https://mp-prod.appsmb.com/mas/v5/app/proxy?alias=",
    },
    2: {
        "name": "美的美居",
        "app_key": "46579c15",
        "login_key": "ad0ee21d48a64bf49f4fb583ab76e799",
        "iot_key": bytes.fromhex(format(9795516279659324117647275084689641883661667, "x")).decode(),
        "hmac_key": bytes.fromhex(format(117390035944627627450677220413733956185864939010425, "x")).decode(),
        "api_url": "https://mp-prod.smartmidea.net/mas/v5/app/proxy?alias=",
    },
}

SERVER_NAME_TO_ID = {
    "msmarthome": 1,
    "midea_meiju": 2,
    "meiju": 2,
    "美的美居": 2,
    "msmarthomecloud": 1,
}


@dataclass
class MideaCloudDevice:
    appliance_code: int
    home_id: str
    home_name: str
    room_name: str
    name: str
    device_type: int
    category: str
    model: str
    model_number: str
    manufacturer_code: str
    smart_product_id: str
    sn: str
    sn8: str
    online: bool
    status_payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.appliance_code),
            "device_id": str(self.appliance_code),
            "appliance_code": self.appliance_code,
            "home_id": self.home_id,
            "home_name": self.home_name,
            "room_name": self.room_name,
            "name": self.name,
            "device_type": self.device_type,
            "device_type_hex": f"0x{self.device_type:02X}",
            "category": self.category,
            "model": self.model,
            "model_number": self.model_number,
            "manufacturer_code": self.manufacturer_code,
            "smart_product_id": self.smart_product_id,
            "sn": self.sn,
            "sn8": self.sn8,
            "online": self.online,
            "status": "online" if self.online else "offline",
            "status_payload": self.status_payload,
        }


class CloudSecurity:
    def __init__(self, login_key: str | None, iot_key: str, hmac_key: str, fixed_key=None, fixed_iv=None):
        self._login_key = login_key or ""
        self._iot_key = iot_key
        self._hmac_key = hmac_key
        self._aes_key = None
        self._aes_iv = None
        self._fixed_key = format(fixed_key, "x").encode("ascii") if fixed_key else None
        self._fixed_iv = format(fixed_iv, "x").encode("ascii") if fixed_iv else None

    def sign(self, data: str, random_value: str) -> str:
        msg = f"{self._iot_key}{data}{random_value}"
        return hmac.new(self._hmac_key.encode("ascii"), msg.encode("ascii"), hashlib.sha256).hexdigest()

    def encrypt_password(self, login_id: str, data: str) -> str:
        password_hash = hashlib.sha256(data.encode("ascii")).hexdigest()
        login_hash = f"{login_id}{password_hash}{self._login_key}"
        return hashlib.sha256(login_hash.encode("ascii")).hexdigest()

    def encrypt_iam_password(self, login_id: str, data: str) -> str:
        raise NotImplementedError

    @staticmethod
    def get_deviceid(username: str) -> str:
        return hashlib.md5(f"Hello, {username}!".encode("ascii")).digest().hex()[:16]

    def set_aes_keys(self, key, iv):
        if isinstance(key, str):
            key = key.encode("ascii")
        if isinstance(iv, str):
            iv = iv.encode("ascii")
        self._aes_key = key
        self._aes_iv = iv

    def aes_encrypt_with_fixed_key(self, data: bytes):
        return self.aes_encrypt(data, self._fixed_key, self._fixed_iv)

    def aes_decrypt_with_fixed_key(self, data):
        return self.aes_decrypt(data, self._fixed_key, self._fixed_iv)

    def aes_encrypt(self, data, key=None, iv=None):
        aes_key = key if key is not None else self._aes_key
        aes_iv = iv if iv is not None else self._aes_iv
        if aes_key is None:
            raise ValueError("Encrypt need a key")
        if isinstance(data, str):
            data = bytes.fromhex(data)
        if aes_iv is None:
            return AES.new(aes_key, AES.MODE_ECB).encrypt(pad(data, 16))
        return AES.new(aes_key, AES.MODE_CBC, iv=aes_iv).encrypt(pad(data, 16))

    def aes_decrypt(self, data, key=None, iv=None):
        aes_key = key if key is not None else self._aes_key
        aes_iv = iv if iv is not None else self._aes_iv
        if aes_key is None:
            raise ValueError("Encrypt need a key")
        if isinstance(data, str):
            data = bytes.fromhex(data)
        if aes_iv is None:
            return unpad(AES.new(aes_key, AES.MODE_ECB).decrypt(data), len(aes_key)).decode()
        return unpad(AES.new(aes_key, AES.MODE_CBC, iv=aes_iv).decrypt(data), len(aes_key)).decode()


class MeijuCloudSecurity(CloudSecurity):
    def __init__(self, login_key: str, iot_key: str, hmac_key: str):
        super().__init__(login_key, iot_key, hmac_key, 10864842703515613082)

    def encrypt_iam_password(self, login_id: str, data: str) -> str:
        first = hashlib.md5(data.encode("ascii")).hexdigest()
        return hashlib.md5(first.encode("ascii")).hexdigest()


class MSmartCloudSecurity(CloudSecurity):
    def __init__(self, login_key: str, iot_key: str, hmac_key: str):
        super().__init__(login_key, iot_key, hmac_key, 13101328926877700970, 16429062708050928556)

    def encrypt_iam_password(self, login_id: str, data: str) -> str:
        first = hashlib.md5(data.encode("ascii")).hexdigest()
        second = hashlib.md5(first.encode("ascii")).hexdigest()
        login_hash = f"{login_id}{second}{self._login_key}"
        return hashlib.sha256(login_hash.encode("ascii")).hexdigest()

    def set_aes_keys(self, encrypted_key, encrypted_iv):
        key_digest = hashlib.sha256(self._login_key.encode("ascii")).hexdigest()
        tmp_key = key_digest[:16].encode("ascii")
        tmp_iv = key_digest[16:32].encode("ascii")
        self._aes_key = self.aes_decrypt(encrypted_key, tmp_key, tmp_iv).encode("ascii")
        self._aes_iv = self.aes_decrypt(encrypted_iv, tmp_key, tmp_iv).encode("ascii")


class BaseCloudApi:
    def __init__(self, payload: dict[str, Any], session: requests.Session):
        self.payload = payload
        self.session = session
        self.server_id = int(payload["server"])
        self.server_meta = MIDEA_CLOUDS[self.server_id]
        self.account = str(payload["account"]).strip()
        self.password = str(payload.get("password") or "").strip()
        self._api_url = str(payload.get("api_base") or self.server_meta["api_url"]).rstrip("/")
        self._access_token = str(payload.get("access_token") or "").strip() or None
        self._uid = str(payload.get("uid") or "").strip()
        self._nickname = str(payload.get("nickname") or self.account).strip()
        self._device_id = str(payload.get("device_id") or CloudSecurity.get_deviceid(self.account))
        self._login_id = str(payload.get("login_id") or "").strip() or None
        self._token_invalid_retry_count = 0
        self._homegroup_id = str(payload.get("homegroup_id") or "").strip() or None
        self._security = self._build_security()

    def _build_security(self) -> CloudSecurity:
        raise NotImplementedError

    @property
    def nickname(self) -> str:
        return self._nickname

    def export_state(self) -> dict[str, Any]:
        state = {
            "server": self.server_id,
            "server_name": self.server_meta["name"],
            "api_base": self._api_url,
            "device_id": self._device_id,
            "login_id": self._login_id or "",
            "access_token": self._access_token or "",
            "nickname": self._nickname,
        }
        if self._uid:
            state["uid"] = self._uid
        if self._homegroup_id:
            state["homegroup_id"] = self._homegroup_id
        return state

    def _make_general_data(self) -> dict[str, Any]:
        return {}

    @staticmethod
    def _is_token_invalid_response(response: dict) -> bool:
        try:
            code = int(response.get("code", -1))
        except Exception:
            code = -1
        if code == 40002:
            return True
        msg = str(response.get("msg") or response.get("message") or "")
        msg_lower = msg.lower()
        return (
            "user token not exist" in msg_lower
            or ("token" in msg_lower and "not exist" in msg_lower)
            or "token校验不通过" in msg
        )

    def _request_headers(self) -> dict[str, str]:
        return {}

    def _api_request(
        self,
        *,
        endpoint: str,
        data: dict[str, Any],
        method: str = "POST",
        _retried_after_login: bool = False,
    ) -> dict[str, Any] | None:
        request_data = dict(data or {})
        if not request_data.get("reqId"):
            request_data["reqId"] = token_hex(16)
        if not request_data.get("stamp"):
            request_data["stamp"] = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        random_value = str(int(time.time()))
        dump_data = json.dumps(request_data, separators=(",", ":"), ensure_ascii=False)
        headers = {
            "content-type": "application/json; charset=utf-8",
            "secretVersion": "1",
            "sign": self._security.sign(dump_data, random_value),
            "random": random_value,
        }
        headers.update(self._request_headers())
        if self._access_token:
            headers["accesstoken"] = self._access_token

        response = self.session.request(
            method=method,
            url=f"{self._api_url}{endpoint}",
            headers=headers,
            data=dump_data.encode("utf-8"),
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()

        if int(payload.get("code", -1)) == 0:
            if _retried_after_login:
                self._token_invalid_retry_count = 0
            return payload.get("data") or {"message": "ok"}

        if not _retried_after_login and self._is_token_invalid_response(payload):
            if self._token_invalid_retry_count >= 3:
                return None
            self._token_invalid_retry_count += 1
            self._access_token = None
            if self.login():
                return self._api_request(
                    endpoint=endpoint,
                    data=request_data,
                    method=method,
                    _retried_after_login=True,
                )
        return None

    def _get_login_id(self) -> str | None:
        data = self._make_general_data()
        data.update({"loginAccount": self.account, "type": "1"})
        response = self._api_request(endpoint="/v1/user/login/id/get", data=data)
        return response.get("loginId") if response else None

    def login(self) -> bool:
        raise NotImplementedError

    def list_homes(self) -> dict[str, str]:
        return {"1": "My home"}

    def list_appliances(self, home_id: str | None = None) -> dict[int, dict[str, Any]] | None:
        raise NotImplementedError

    def get_device_status(self, *, appliance_code: int, appliance_info: dict[str, Any], query: dict[str, Any] | None = None) -> dict[str, Any] | None:
        raise NotImplementedError

    def download_lua(
        self,
        *,
        path: Path,
        appliance_info: dict[str, Any],
    ) -> Path | None:
        raise NotImplementedError

    def send_device_control(
        self,
        *,
        appliance_code: int,
        appliance_info: dict[str, Any],
        control: dict[str, Any] | None = None,
        status: dict[str, Any] | None = None,
    ) -> bool:
        raise NotImplementedError


class MeijuCloudApi(BaseCloudApi):
    APP_ID = "900"

    def _build_security(self) -> CloudSecurity:
        return MeijuCloudSecurity(
            login_key=self.server_meta["login_key"],
            iot_key=self.server_meta["iot_key"],
            hmac_key=self.server_meta["hmac_key"],
        )

    def login(self) -> bool:
        login_id = self._get_login_id()
        if not login_id:
            return False
        self._login_id = login_id
        stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        data = {
            "iotData": {
                "clientType": 1,
                "deviceId": self._device_id,
                "iampwd": self._security.encrypt_iam_password(login_id, self.password),
                "iotAppId": self.APP_ID,
                "loginAccount": self.account,
                "password": self._security.encrypt_password(login_id, self.password),
                "reqId": token_hex(16),
                "stamp": stamp,
            },
            "data": {
                "appKey": self.server_meta["app_key"],
                "deviceId": self._device_id,
                "platform": 2,
            },
            "timestamp": stamp,
            "stamp": stamp,
        }
        response = self._api_request(endpoint="/mj/user/login", data=data)
        if not response:
            return False
        self._access_token = response["mdata"]["accessToken"]
        self._security.set_aes_keys(self._security.aes_decrypt_with_fixed_key(response["key"]), None)
        self._nickname = response.get("userInfo", {}).get("nickName") or self.account
        return True

    def list_homes(self) -> dict[str, str]:
        response = self._api_request(endpoint="/v1/homegroup/list/get", data={})
        homes = {}
        for home in (response or {}).get("homeList", []):
            homes[str(home["homegroupId"])] = home.get("name") or f"家庭 {home['homegroupId']}"
        return homes

    def list_appliances(self, home_id: str | None = None) -> dict[int, dict[str, Any]] | None:
        self._homegroup_id = str(home_id) if home_id is not None else self._homegroup_id
        response = self._api_request(endpoint="/v1/appliance/home/list/get", data={"homegroupId": home_id})
        appliances: dict[int, dict[str, Any]] = {}
        for home in (response or {}).get("homeList", []):
            home_name = home.get("name") or ""
            for room in home.get("roomList") or []:
                room_name = room.get("name") or home_name or "默认房间"
                for appliance in room.get("applianceList") or []:
                    sn = self._security.aes_decrypt(appliance["sn"]) if appliance.get("sn") else ""
                    sn8 = appliance.get("sn8") or "00000000"
                    model = appliance.get("productModel") or sn8
                    appliances[int(appliance["applianceCode"])] = {
                        "name": appliance.get("name"),
                        "type": int(appliance.get("type"), 16),
                        "sn": sn,
                        "sn8": sn8,
                        "category": appliance.get("category"),
                        "smart_product_id": appliance.get("smartProductId", "0"),
                        "model_number": appliance.get("modelNumber", "0"),
                        "manufacturer_code": appliance.get("enterpriseCode", "0000"),
                        "model": model,
                        "online": appliance.get("onlineStatus") == "1",
                        "home_name": home_name,
                        "room_name": room_name,
                        "home_id": str(home_id),
                    }
        return appliances

    def get_device_status(self, *, appliance_code: int, appliance_info: dict[str, Any], query: dict[str, Any] | None = None) -> dict[str, Any] | None:
        response = self._api_request(
            endpoint="/mjl/v1/device/status/lua/get",
            data={
                "applianceCode": str(appliance_code),
                "command": {"query": query or {}},
            },
        )
        return response if isinstance(response, dict) else None

    def send_device_control(
        self,
        *,
        appliance_code: int,
        appliance_info: dict[str, Any],
        control: dict[str, Any] | None = None,
        status: dict[str, Any] | None = None,
    ) -> bool:
        data = {
            "applianceCode": str(appliance_code),
            "command": {"control": control or {}},
        }
        if status and isinstance(status, dict):
            data["command"]["status"] = status
        response = self._api_request(endpoint="/mjl/v1/device/lua/control", data=data)
        return response is not None

    def download_lua(
        self,
        *,
        path: Path,
        appliance_info: dict[str, Any],
    ) -> Path | None:
        data = {
            "applianceSn": appliance_info.get("sn", ""),
            "applianceType": f"0x{appliance_info['type']:02X}",
            "applianceMFCode": appliance_info.get("manufacturer_code", "0000"),
            "version": "0",
            "iotAppId": self.APP_ID,
            "modelNumber": appliance_info.get("model_number"),
        }
        response = self._api_request(endpoint="/v1/appliance/protocol/lua/luaGet", data=data)
        if not response:
            return None
        file_name = response.get("fileName")
        download_url = response.get("url")
        if not file_name or not download_url:
            return None

        path.mkdir(parents=True, exist_ok=True)
        target = path / file_name
        if target.exists():
            return target

        res = self.session.get(download_url, timeout=30)
        res.raise_for_status()
        stream = 'local bit = require "bit"\n' + self._security.aes_decrypt_with_fixed_key(res.text)
        target.write_text(stream.replace("\r\n", "\n"), encoding="utf-8")
        return target


class MSmartHomeCloudApi(BaseCloudApi):
    APP_ID = "1010"
    SRC = "10"
    APP_VERSION = "3.0.2"

    def _build_security(self) -> CloudSecurity:
        return MSmartCloudSecurity(
            login_key=self.server_meta["app_key"],
            iot_key=self.server_meta["iot_key"],
            hmac_key=self.server_meta["hmac_key"],
        )

    def _make_general_data(self) -> dict[str, Any]:
        return {
            "appVersion": self.APP_VERSION,
            "src": self.SRC,
            "format": "2",
            "stamp": datetime.datetime.now().strftime("%Y%m%d%H%M%S"),
            "platformId": "1",
            "deviceId": self._device_id,
            "reqId": token_hex(16),
            "uid": self._uid,
            "clientType": "1",
            "appId": self.APP_ID,
        }

    def _request_headers(self) -> dict[str, str]:
        auth_base = requests.auth._basic_auth_str(self.server_meta["app_key"], self.server_meta["iot_key"])
        headers = {
            "x-recipe-app": self.APP_ID,
            "authorization": auth_base,
        }
        if self._uid:
            headers["uid"] = self._uid
        return headers

    def _re_route(self) -> None:
        data = self._make_general_data()
        data.update({"userName": self.account, "platformId": "1", "userType": "0"})
        response = self._api_request(endpoint="/v1/unitcenter/router/user/name", data=data)
        if response and response.get("masUrl"):
            self._api_url = response["masUrl"]

    def login(self) -> bool:
        self._re_route()
        login_id = self._get_login_id()
        if not login_id:
            return False
        self._login_id = login_id
        iot_data = self._make_general_data()
        iot_data.pop("uid", None)
        stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        iot_data.update(
            {
                "iampwd": self._security.encrypt_iam_password(login_id, self.password),
                "loginAccount": self.account,
                "password": self._security.encrypt_password(login_id, self.password),
                "stamp": stamp,
            }
        )
        data = {
            "iotData": iot_data,
            "data": {
                "appKey": self.server_meta["app_key"],
                "deviceId": self._device_id,
                "platform": "2",
            },
            "stamp": stamp,
        }
        response = self._api_request(endpoint="/mj/user/login", data=data)
        if not response:
            return False
        self._uid = response["uid"]
        self._access_token = response["mdata"]["accessToken"]
        self._security.set_aes_keys(response["accessToken"], response["randomData"])
        self._nickname = response.get("userInfo", {}).get("nickName") or self.account
        return True

    def list_appliances(self, home_id: str | None = None) -> dict[int, dict[str, Any]] | None:
        response = self._api_request(endpoint="/v1/appliance/user/list/get", data=self._make_general_data())
        appliances: dict[int, dict[str, Any]] = {}
        for appliance in (response or {}).get("list", []):
            sn = self._security.aes_decrypt(appliance["sn"]) if appliance.get("sn") else ""
            sn8 = sn[9:17] if len(sn) > 17 else ""
            appliances[int(appliance["id"])] = {
                "name": appliance.get("name"),
                "type": int(appliance.get("type"), 16),
                "sn": sn,
                "sn8": sn8,
                "category": appliance.get("category"),
                "smart_product_id": appliance.get("smartProductId"),
                "model_number": appliance.get("modelNumber", "0"),
                "manufacturer_code": appliance.get("enterpriseCode", "0000"),
                "model": sn8,
                "online": appliance.get("onlineStatus") == "1",
                "home_name": "MSmartHome",
                "room_name": "默认房间",
                "home_id": str(home_id or "default"),
            }
        return appliances

    def get_device_status(self, *, appliance_code: int, appliance_info: dict[str, Any], query: dict[str, Any] | None = None) -> dict[str, Any] | None:
        data = {
            "clientType": "1",
            "appId": self.APP_ID,
            "format": "2",
            "deviceId": self._device_id,
            "iotAppId": self.APP_ID,
            "applianceMFCode": appliance_info.get("manufacturer_code", "0000"),
            "applianceType": f"0x{appliance_info['type']:02X}",
            "modelNumber": appliance_info.get("model_number"),
            "applianceSn": self._security.aes_encrypt_with_fixed_key(appliance_info.get("sn", "").encode("ascii")).hex(),
            "version": "0",
            "encryptedType ": "2",
            "applianceCode": appliance_code,
            "command": {"query": query or {}},
        }
        response = self._api_request(endpoint="/v1/device/status/lua/get", data=data)
        return response if isinstance(response, dict) else None

    def send_device_control(
        self,
        *,
        appliance_code: int,
        appliance_info: dict[str, Any],
        control: dict[str, Any] | None = None,
        status: dict[str, Any] | None = None,
    ) -> bool:
        data = {
            "clientType": "1",
            "appId": self.APP_ID,
            "format": "2",
            "deviceId": self._device_id,
            "iotAppId": self.APP_ID,
            "applianceMFCode": appliance_info.get("manufacturer_code", "0000"),
            "applianceType": f"0x{appliance_info['type']:02X}",
            "modelNumber": appliance_info.get("model_number"),
            "applianceSn": self._security.aes_encrypt_with_fixed_key(appliance_info.get("sn", "").encode("ascii")).hex(),
            "version": "0",
            "encryptedType ": "2",
            "applianceCode": appliance_code,
            "command": {"control": control or {}},
        }
        if status and isinstance(status, dict):
            data["command"]["status"] = status
        response = self._api_request(endpoint="/v1/device/lua/control", data=data)
        return response is not None

    def download_lua(
        self,
        *,
        path: Path,
        appliance_info: dict[str, Any],
    ) -> Path | None:
        data = {
            "clientType": "1",
            "appId": self.APP_ID,
            "format": "2",
            "deviceId": self._device_id,
            "iotAppId": self.APP_ID,
            "applianceMFCode": appliance_info.get("manufacturer_code", "0000"),
            "applianceType": f"0x{appliance_info['type']:02X}",
            "modelNumber": appliance_info.get("model_number"),
            "applianceSn": self._security.aes_encrypt_with_fixed_key(appliance_info.get("sn", "").encode("ascii")).hex(),
            "version": "0",
            "encryptedType ": "2",
        }
        if appliance_info.get("smart_product_id"):
            data["smartProductId"] = appliance_info.get("smart_product_id")
        response = self._api_request(endpoint="/v2/luaEncryption/luaGet", data=data)
        if not response:
            return None
        file_name = response.get("fileName")
        download_url = response.get("url")
        if not file_name or not download_url:
            return None

        path.mkdir(parents=True, exist_ok=True)
        target = path / file_name
        if target.exists():
            return target

        res = self.session.get(download_url, timeout=30)
        res.raise_for_status()
        stream = 'local bit = require "bit"\n' + self._security.aes_decrypt_with_fixed_key(res.text)
        target.write_text(stream.replace("\r\n", "\n"), encoding="utf-8")
        return target


class MideaCloudClient:
    default_timeout_seconds = 15

    def __init__(self, payload: dict[str, Any]):
        self.payload = self.normalize_payload(payload)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Wanny-MideaCloud/0.2",
                "Accept": "application/json",
            }
        )
        self.cloud_api = self._build_cloud_api()
        self.lua_storage_path = self._resolve_lua_storage_path()

    @classmethod
    def normalize_payload(cls, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Midea Cloud payload must be a JSON object")

        normalized = dict(payload)
        for source_key, target_key in (
            ("username", "account"),
            ("user", "account"),
            ("email", "account"),
            ("token", "access_token"),
            ("base_url", "api_base"),
        ):
            value = normalized.get(source_key)
            if value and not normalized.get(target_key):
                normalized[target_key] = value

        server_value = normalized.get("server") or normalized.get("server_id") or normalized.get("provider")
        if server_value is None:
            server_value = 2
        normalized["server"] = cls._normalize_server(server_value)

        if normalized.get("api_base"):
            normalized["api_base"] = str(normalized["api_base"]).strip().rstrip("/")

        selected_homes = normalized.get("selected_homes") or normalized.get("home_ids") or []
        if isinstance(selected_homes, (str, int)):
            selected_homes = [selected_homes]
        normalized["selected_homes"] = [str(item) for item in selected_homes if str(item).strip()]
        normalized["enable_lua_cache"] = bool(normalized.get("enable_lua_cache", True))

        return normalized

    @staticmethod
    def _resolve_lua_storage_path() -> Path:
        return Path(__file__).resolve().parents[4] / "credentials" / "midea_cloud" / "lua"

    @staticmethod
    def _normalize_server(value: Any) -> int:
        if isinstance(value, int):
            if value in MIDEA_CLOUDS:
                return value
        normalized = str(value or "").strip().lower()
        if normalized.isdigit() and int(normalized) in MIDEA_CLOUDS:
            return int(normalized)
        if normalized in SERVER_NAME_TO_ID:
            return SERVER_NAME_TO_ID[normalized]
        for server_id, meta in MIDEA_CLOUDS.items():
            if meta["name"].lower() == normalized:
                return server_id
        raise ValueError("Unsupported Midea Cloud server, expected 1/2 or known server name")

    @classmethod
    def validate_payload(cls, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = cls.normalize_payload(payload)
        account = str(normalized.get("account") or "").strip()
        password = str(normalized.get("password") or "").strip()
        access_token = str(normalized.get("access_token") or "").strip()
        if not account:
            raise ValueError("Midea Cloud account is required")
        if not access_token and not password:
            raise ValueError("Midea Cloud password is required when access_token is absent")
        return normalized

    def _build_cloud_api(self) -> BaseCloudApi:
        if self.payload["server"] == 1:
            return MSmartHomeCloudApi(self.payload, self.session)
        return MeijuCloudApi(self.payload, self.session)

    def login(self) -> bool:
        if self.cloud_api.export_state().get("access_token"):
            return True
        return self.cloud_api.login()

    def get_account_profile(self) -> dict[str, Any]:
        if not self.login():
            raise ValueError("Unable to login to Midea Cloud")
        homes = self.cloud_api.list_homes()
        return {
            "account": self.payload["account"],
            "connected": True,
            "server": self.payload["server"],
            "server_name": MIDEA_CLOUDS[self.payload["server"]]["name"],
            "api_base": self.cloud_api.export_state()["api_base"],
            "nickname": self.cloud_api.nickname,
            "homes": [{"id": home_id, "name": home_name} for home_id, home_name in homes.items()],
            "auth_state": self.cloud_api.export_state(),
        }

    def list_devices(self) -> list[dict[str, Any]]:
        logger.info("[MideaCloud] list_devices: starting device sync")
        if not self.login():
            logger.error("[MideaCloud] list_devices: login failed")
            raise ValueError("Unable to login to Midea Cloud")

        logger.info("[MideaCloud] list_devices: login successful, server=%s, account=%s",
                    self.payload.get("server"), self.payload.get("account"))

        lua_runtime_ready = False
        if self.payload.get("enable_lua_cache", True):
            try:
                ensure_lua_support_files(self.lua_storage_path)
                lua_runtime_ready = lua_runtime_available()
                logger.debug("[MideaCloud] list_devices: lua_runtime_ready=%s", lua_runtime_ready)
            except Exception as e:
                logger.warning("[MideaCloud] list_devices: lua setup failed: %s", e)
                lua_runtime_ready = False

        homes = self.cloud_api.list_homes()
        logger.info("[MideaCloud] list_devices: found %d homes: %s", len(homes), list(homes.keys()))

        selected_homes = self.payload.get("selected_homes") or []
        home_ids = selected_homes or list(homes.keys()) or ["default"]
        logger.info("[MideaCloud] list_devices: will sync homes: %s", home_ids)

        devices: list[dict[str, Any]] = []
        for home_id in home_ids:
            home_name = homes.get(str(home_id)) or f"家庭 {home_id}"
            logger.debug("[MideaCloud] list_devices: fetching appliances for home_id=%s, name=%s", home_id, home_name)

            try:
                appliances = self.cloud_api.list_appliances(str(home_id)) or {}
                logger.info("[MideaCloud] list_devices: home_id=%s has %d appliances", home_id, len(appliances))
            except Exception as e:
                logger.error("[MideaCloud] list_devices: failed to list appliances for home_id=%s: %s", home_id, e)
                continue

            for appliance_code, appliance_info in appliances.items():
                logger.debug("[MideaCloud] list_devices: processing appliance_code=%s, type=%s, name=%s",
                            appliance_code, appliance_info.get("type"), appliance_info.get("name"))

                mapping = get_device_mapping(
                    int(appliance_info.get("type") or 0),
                    sn8=str(appliance_info.get("sn8") or ""),
                    subtype=appliance_info.get("model_number"),
                    category=str(appliance_info.get("category") or ""),
                )
                logger.debug("[MideaCloud] list_devices: appliance_code=%s mapping=%s", appliance_code, mapping.get("name", "unknown"))

                status_payload: dict[str, Any] = {}
                for query in mapping.get("queries") or [{}]:
                    if not isinstance(query, dict):
                        continue
                    try:
                        chunk = self.cloud_api.get_device_status(
                            appliance_code=appliance_code,
                            appliance_info=appliance_info,
                            query=query,
                        ) or {}
                        logger.debug("[MideaCloud] list_devices: status query for %s returned keys: %s",
                                    appliance_code, list(chunk.keys()) if isinstance(chunk, dict) else "none")
                    except Exception as e:
                        logger.warning("[MideaCloud] list_devices: status query failed for %s: %s", appliance_code, e)
                        chunk = {}
                    if isinstance(chunk, dict):
                        status_payload.update(chunk)

                lua_file = None
                lua_codec_ready = False
                try:
                    if self.payload.get("enable_lua_cache", True):
                        lua_file = self.cloud_api.download_lua(path=self.lua_storage_path, appliance_info=appliance_info)
                except Exception as e:
                    logger.debug("[MideaCloud] list_devices: lua download failed for %s: %s", appliance_code, e)
                    lua_file = None
                if lua_file and lua_runtime_ready:
                    try:
                        MideaLuaCodec(
                            lua_file,
                            device_type=f"T0x{int(appliance_info.get('type') or 0):02X}",
                            sn=str(appliance_info.get("sn") or ""),
                            subtype=str(appliance_info.get("model_number") or ""),
                        )
                        lua_codec_ready = True
                    except Exception as e:
                        logger.debug("[MideaCloud] list_devices: lua codec init failed for %s: %s", appliance_code, e)
                        lua_codec_ready = False

                device = MideaCloudDevice(
                    appliance_code=appliance_code,
                    home_id=str(appliance_info.get("home_id") or home_id),
                    home_name=str(appliance_info.get("home_name") or home_name),
                    room_name=str(appliance_info.get("room_name") or home_name),
                    name=str(appliance_info.get("name") or f"美的设备 {appliance_code}"),
                    device_type=int(appliance_info.get("type") or 0),
                    category=str(appliance_info.get("category") or "美的设备"),
                    model=str(appliance_info.get("model") or appliance_info.get("sn8") or ""),
                    model_number=str(appliance_info.get("model_number") or "0"),
                    manufacturer_code=str(appliance_info.get("manufacturer_code") or "0000"),
                    smart_product_id=str(appliance_info.get("smart_product_id") or "0"),
                    sn=str(appliance_info.get("sn") or ""),
                    sn8=str(appliance_info.get("sn8") or ""),
                    online=bool(appliance_info.get("online")),
                    status_payload={
                        **(status_payload if isinstance(status_payload, dict) else {}),
                        "_meta": {
                            "lua_file": str(lua_file) if lua_file else "",
                            "lua_runtime_available": lua_runtime_ready,
                            "lua_codec_ready": lua_codec_ready,
                            "queries": mapping.get("queries") or [],
                        },
                    },
                )
                devices.append(device.to_dict())
                logger.debug("[MideaCloud] list_devices: added device %s (online=%s)", device.name, device.online)

        logger.info("[MideaCloud] list_devices: completed, total devices=%d", len(devices))
        return devices

    def execute_control(self, *, device_id: str, control: dict[str, Any], value: Any = None) -> None:
        if not self.login():
            raise ValueError("Unable to login to Midea Cloud")

        raw_devices = self.list_devices()
        target = next((device for device in raw_devices if str(device.get("id")) == str(device_id)), None)
        if target is None:
            raise ValueError(f"Midea Cloud device not found: {device_id}")

        action_params = control.get("action_params") or {}
        command_control = action_params.get("control")
        command_status = action_params.get("status")
        control_template = action_params.get("control_template")
        value_transform = action_params.get("value_transform")
        if not isinstance(command_control, dict) and isinstance(control_template, dict):
            if value is None:
                raise ValueError(f"Missing control value for {control.get('key')}")
            command_control = self._resolve_control_template(
                control_template,
                value,
                value_transform=value_transform if isinstance(value_transform, dict) else None,
            )
        if not isinstance(command_control, dict):
            command_control = self._build_generic_control_payload(control, value)
        if not isinstance(command_control, dict):
            raise NotImplementedError(
                f"Midea Cloud control mapping is not available yet for {control.get('key')}"
            )

        current_status = target.get("status_payload") if isinstance(target.get("status_payload"), dict) else {}
        merged_status = dict(current_status)
        merged_status.pop("_meta", None)
        if isinstance(command_status, dict):
            merged_status.update(command_status)
        mapping = get_device_mapping(
            int(target.get("device_type") or 0),
            sn8=str(target.get("sn8") or ""),
            subtype=target.get("model_number"),
            category=str(target.get("category") or ""),
        )
        command_control = self._augment_control_with_centralized(
            command_control,
            current_status=merged_status,
            centralized_keys=mapping.get("centralized") or [],
        )

        appliance_info = {
            "type": target.get("device_type"),
            "sn": target.get("sn"),
            "model_number": target.get("model_number"),
            "manufacturer_code": target.get("manufacturer_code"),
        }
        ok = self.cloud_api.send_device_control(
            appliance_code=int(target["appliance_code"]),
            appliance_info=appliance_info,
            control=command_control,
            status=merged_status if merged_status else None,
        )
        if not ok:
            raise ValueError(f"Midea Cloud control failed for device {device_id}")

    @staticmethod
    def _resolve_control_template(
        template: dict[str, Any],
        value: Any,
        *,
        value_transform: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if isinstance(value_transform, dict):
            transformed = MideaCloudClient._apply_value_transform(value, value_transform)
            if isinstance(transformed, dict):
                return transformed
        resolved: dict[str, Any] = {}
        for key, item in template.items():
            if item == "{value}":
                resolved[key] = value
            elif isinstance(item, dict):
                resolved[key] = MideaCloudClient._resolve_control_template(item, value)
            else:
                resolved[key] = item
        return resolved

    @staticmethod
    def _apply_value_transform(value: Any, transform: dict[str, Any]) -> dict[str, Any] | None:
        transform_type = str(transform.get("type") or "").strip()
        if transform_type != "temperature_halves":
            return None
        integer_key = str(transform.get("integer_key") or "").strip()
        fraction_key = str(transform.get("fraction_key") or "").strip()
        if not integer_key or not fraction_key:
            return None
        numeric_value = float(value)
        integer_part = int(numeric_value)
        fraction_part = numeric_value - integer_part
        half_flag = 5 if abs(fraction_part) >= 0.49 else 0
        return {
            integer_key: integer_part,
            fraction_key: half_flag,
        }

    @staticmethod
    def _build_generic_control_payload(control: dict[str, Any], value: Any) -> dict[str, Any] | None:
        if value is None:
            return None
        control_key = str(
            (control.get("action_params") or {}).get("control_key")
            or control.get("key")
            or ""
        ).strip()
        if not control_key:
            return None
        return MideaCloudClient._nest_control_value(control_key, value)

    @staticmethod
    def _nest_control_value(control_key: str, value: Any) -> dict[str, Any]:
        parts = [part for part in str(control_key).split(".") if part]
        if not parts:
            return {}
        nested: Any = value
        for part in reversed(parts):
            nested = {part: nested}
        return nested

    @staticmethod
    def _augment_control_with_centralized(
        control: dict[str, Any],
        *,
        current_status: dict[str, Any],
        centralized_keys: list[Any],
    ) -> dict[str, Any]:
        merged = dict(control or {})
        for key in centralized_keys or []:
            key_str = str(key).strip()
            if not key_str or key_str in merged:
                continue
            if key_str in current_status:
                merged[key_str] = current_status[key_str]
        return merged
