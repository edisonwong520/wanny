from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from accounts.models import Account

import requests
import websockets
from mijiaAPI import mijiaAPI
from wechatbot.auth import save_credentials
from wechatbot.types import Credentials

from utils.crypto import encrypt_value, decrypt_value
from utils.logger import logger

from .models import PlatformAuth
from .clients.mbapi2020 import MbApi2020Client
from .clients.midea_cloud import MideaCloudClient


class WeChatAuthService:
    platform_name = "wechat"
    cred_file_name = "credentials/wechat_credentials.json"

    @classmethod
    def resolve_cred_file_path(cls, cred_file_path=None, account: Account | None = None) -> Path:
        if cred_file_path:
            path = Path(cred_file_path)
        else:
            path = Path(__file__).resolve().parents[2] / cls.cred_file_name

        # 如果提供了账户且未指定路径，则使用账户专属文件名
        if account and not cred_file_path:
            path = path.parent / f"wechat_credentials_{account.id}.json"

        if path.is_dir():
            return path / "credentials.json"
        return path

    @classmethod
    def get_auth_record(cls, account: Account, active_only: bool = False) -> PlatformAuth | None:
        queryset = PlatformAuth.objects.filter(account=account, platform_name=cls.platform_name)
        if active_only:
            queryset = queryset.filter(is_active=True)
        return queryset.first()

    @classmethod
    def _extract_payload(cls, auth_obj: PlatformAuth | None) -> dict:
        payload = getattr(auth_obj, "auth_payload", None)
        return payload if isinstance(payload, dict) else {}

    @classmethod
    def write_cred_file_from_db(cls, account: Account, cred_file_path=None) -> Path:
        path = cls.resolve_cred_file_path(cred_file_path, account=account)
        auth_obj = cls.get_auth_record(account=account, active_only=True)
        payload = cls._extract_payload(auth_obj)

        if payload:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            logger.info("[WeChat Auth] 已从 PlatformAuth 数据库加载微信授权凭证到本地。")
        elif path.exists():
            path.unlink()
            logger.info("[WeChat Auth] 当前没有启用中的微信授权，已清理本地旧凭证文件。")

        return path

    @classmethod
    def clear_cred_file(cls, account: Account | None = None, cred_file_path=None):
        path = cls.resolve_cred_file_path(cred_file_path, account=account)
        if path.exists():
            path.unlink()
            logger.info("[WeChat Auth] 已清理本地微信凭证文件。")
        return path

    @classmethod
    def sync_cred_file_to_db(cls, account: Account, cred_file_path=None, fallback_payload=None) -> PlatformAuth:
        path = cls.resolve_cred_file_path(cred_file_path, account=account)

        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        else:
            payload = fallback_payload or {}

        if not isinstance(payload, dict) or not payload:
            raise ValueError("WeChat auth payload is empty or invalid")

        auth_obj, _ = PlatformAuth.objects.update_or_create(
            account=account,
            platform_name=cls.platform_name,
            defaults={
                "auth_payload": payload,
                "is_active": True,
            },
        )
        logger.info("[WeChat Auth] 已将微信授权凭证同步入库至 PlatformAuth。")
        return auth_obj

    @classmethod
    def save_credentials_to_file(cls, account: Account, creds: Credentials, cred_file_path=None) -> Path:
        path = cls.resolve_cred_file_path(cred_file_path, account=account)
        asyncio.run(save_credentials(creds, path))
        return path


class MijiaAuthService:
    platform_name = "mijia"
    platform_aliases = ("mijia", "xiaomi")
    auth_file_name = "credentials/mijia_auth.json"

    @classmethod
    def resolve_auth_file_path(cls, auth_file_path=None, account: Account | None = None) -> Path:
        if auth_file_path:
            path = Path(auth_file_path)
        else:
            path = Path(__file__).resolve().parents[2] / cls.auth_file_name

        # 如果提供了账户且未指定路径，则使用账户专属文件名
        if account and not auth_file_path:
            path = path.parent / f"mijia_auth_{account.id}.json"

        if path.is_dir():
            return path / "auth.json"
        return path

    @classmethod
    def get_auth_record(cls, account: Account, active_only: bool = False) -> PlatformAuth | None:
        queryset = PlatformAuth.objects.filter(account=account, platform_name__in=cls.platform_aliases)
        if active_only:
            queryset = queryset.filter(is_active=True)

        records = list(queryset.order_by("platform_name"))
        for record in records:
            if record.platform_name == cls.platform_name:
                return record
        return records[0] if records else None

    @classmethod
    def _extract_payload(cls, auth_obj: PlatformAuth | None) -> dict:
        payload = getattr(auth_obj, "auth_payload", None)
        return payload if isinstance(payload, dict) else {}

    @classmethod
    def write_auth_file_from_db(cls, account: Account, auth_file_path=None) -> Path:
        # 始终解析为账户专属路径
        path = cls.resolve_auth_file_path(auth_file_path, account=account)
        
        auth_obj = cls.get_auth_record(account=account, active_only=True)
        payload = cls._extract_payload(auth_obj)

        if payload:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            logger.info("[Mijia Auth] 已从 PlatformAuth 数据库加载米家授权凭证到本地。")
        elif path.exists():
            path.unlink()
            logger.info("[Mijia Auth] 当前没有启用中的米家授权，已清理本地旧凭证文件。")

        return path

    @classmethod
    def sync_auth_file_to_db(cls, account: Account, auth_file_path=None, fallback_payload=None) -> PlatformAuth:
        path = cls.resolve_auth_file_path(auth_file_path, account=account)

        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        else:
            payload = fallback_payload or {}

        if not isinstance(payload, dict) or not payload:
            raise ValueError("Mijia auth payload is empty or invalid")

        auth_obj, _ = PlatformAuth.objects.update_or_create(
            account=account,
            platform_name=cls.platform_name,
            defaults={
                "auth_payload": payload,
                "is_active": True,
            },
        )
        logger.info(f"[Mijia Auth] 已将账户 {account.email} 的米家授权凭证同步入库。")
        return auth_obj

    @classmethod
    def get_authenticated_api(cls, account: Account, auth_file_path=None, require_login: bool = False) -> mijiaAPI:
        path = cls.write_auth_file_from_db(account=account, auth_file_path=auth_file_path)
        api = mijiaAPI(auth_data_path=str(path))

        if require_login:
            auth_data = api.login()
            cls.sync_auth_file_to_db(account=account, auth_file_path=path, fallback_payload=auth_data)

        return api

    @classmethod
    def login_and_store(cls, account: Account, auth_file_path=None) -> PlatformAuth:
        path = cls.resolve_auth_file_path(auth_file_path, account=account)
        api = cls.get_authenticated_api(account=account, auth_file_path=path, require_login=True)
        return cls.sync_auth_file_to_db(
            account=account,
            auth_file_path=path,
            fallback_payload=getattr(api, "auth_data", {}),
        )


class HomeAssistantAuthService:
    platform_name = "home_assistant"
    platform_aliases = ("home_assistant", "homeassistant", "ha")
    default_timeout_seconds = 10

    @classmethod
    def get_auth_record(cls, account: Account, active_only: bool = False) -> PlatformAuth | None:
        queryset = PlatformAuth.objects.filter(account=account, platform_name__in=cls.platform_aliases)
        if active_only:
            queryset = queryset.filter(is_active=True)

        records = list(queryset.order_by("platform_name"))
        for record in records:
            if record.platform_name == cls.platform_name:
                return record
        return records[0] if records else None

    @classmethod
    def _extract_payload(cls, auth_obj: PlatformAuth | None) -> dict:
        payload = getattr(auth_obj, "auth_payload", None)
        return payload if isinstance(payload, dict) else {}

    @classmethod
    def _normalize_base_url(cls, base_url: str) -> str:
        normalized = str(base_url or "").strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("Home Assistant base_url must start with http:// or https://")
        return normalized

    @classmethod
    def _build_headers(cls, access_token: str) -> dict[str, str]:
        token = str(access_token or "").strip()
        if not token:
            raise ValueError("Home Assistant access_token is required")
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    @classmethod
    def _build_websocket_url(cls, base_url: str) -> str:
        normalized = cls._normalize_base_url(base_url)
        if normalized.startswith("https://"):
            return f"wss://{normalized[len('https://'):]}/api/websocket"
        return f"ws://{normalized[len('http://'):]}/api/websocket"

    @classmethod
    def validate_payload(cls, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("Home Assistant payload must be a JSON object")

        base_url = cls._normalize_base_url(payload.get("base_url", ""))
        access_token = str(payload.get("access_token", "")).strip()
        headers = cls._build_headers(access_token)

        response = requests.get(
            f"{base_url}/api/",
            headers=headers,
            timeout=cls.default_timeout_seconds,
        )
        response.raise_for_status()
        api_status = response.json()
        if api_status.get("message") != "API running.":
            raise ValueError("Home Assistant API did not return the expected health response")

        config_response = requests.get(
            f"{base_url}/api/config",
            headers=headers,
            timeout=cls.default_timeout_seconds,
        )
        config_response.raise_for_status()
        config_payload = config_response.json() or {}

        return {
            "base_url": base_url,
            "access_token": access_token,
            "instance_name": config_payload.get("location_name") or config_payload.get("location") or "Home Assistant",
            "unit_system": config_payload.get("unit_system", {}),
            "time_zone": config_payload.get("time_zone", ""),
            "version": response.headers.get("X-HA-Version", ""),
        }

    @classmethod
    def validate_and_store(cls, account: Account, payload: dict) -> PlatformAuth:
        validated_payload = cls.validate_payload(payload)
        auth_obj, _ = PlatformAuth.objects.update_or_create(
            account=account,
            platform_name=cls.platform_name,
            defaults={
                "auth_payload": validated_payload,
                "is_active": True,
            },
        )
        logger.info(f"[Home Assistant Auth] 已校验并保存账户 {account.email} 的授权配置。")
        return auth_obj

    @classmethod
    def get_states(cls, account: Account) -> tuple[dict, list[dict]]:
        auth_obj = cls.get_auth_record(account=account, active_only=True)
        payload = cls._extract_payload(auth_obj)
        if not payload:
            raise ValueError("No active Home Assistant authorization found")

        base_url = cls._normalize_base_url(payload.get("base_url", ""))
        headers = cls._build_headers(payload.get("access_token", ""))

        config_response = requests.get(
            f"{base_url}/api/config",
            headers=headers,
            timeout=cls.default_timeout_seconds,
        )
        config_response.raise_for_status()

        states_response = requests.get(
            f"{base_url}/api/states",
            headers=headers,
            timeout=cls.default_timeout_seconds,
        )
        states_response.raise_for_status()

        states_payload = states_response.json()
        if not isinstance(states_payload, list):
            raise ValueError("Home Assistant states response is invalid")

        return (config_response.json() or {}), states_payload

    @classmethod
    def get_entity_states(cls, account: Account, entity_ids: list[str]) -> tuple[dict, list[dict]]:
        auth_obj = cls.get_auth_record(account=account, active_only=True)
        payload = cls._extract_payload(auth_obj)
        if not payload:
            raise ValueError("No active Home Assistant authorization found")

        base_url = cls._normalize_base_url(payload.get("base_url", ""))
        headers = cls._build_headers(payload.get("access_token", ""))

        config_response = requests.get(
            f"{base_url}/api/config",
            headers=headers,
            timeout=cls.default_timeout_seconds,
        )
        config_response.raise_for_status()

        states: list[dict] = []
        for entity_id in entity_ids:
            normalized_entity_id = str(entity_id or "").strip()
            if not normalized_entity_id:
                continue
            state_response = requests.get(
                f"{base_url}/api/states/{normalized_entity_id}",
                headers=headers,
                timeout=cls.default_timeout_seconds,
            )
            state_response.raise_for_status()
            state_payload = state_response.json() or {}
            if isinstance(state_payload, dict) and state_payload.get("entity_id"):
                states.append(state_payload)

        return (config_response.json() or {}), states

    @classmethod
    async def _fetch_registry_via_websocket(cls, *, base_url: str, access_token: str) -> dict:
        ws_url = cls._build_websocket_url(base_url)
        async with websockets.connect(ws_url) as websocket:
            auth_required = json.loads(await websocket.recv())
            if auth_required.get("type") != "auth_required":
                raise ValueError("Home Assistant websocket did not request authentication")

            await websocket.send(json.dumps({"type": "auth", "access_token": access_token}))
            auth_response = json.loads(await websocket.recv())
            if auth_response.get("type") != "auth_ok":
                raise ValueError("Home Assistant websocket authentication failed")

            commands = {
                1: "config/area_registry/list",
                2: "config/device_registry/list",
                3: "config/entity_registry/list",
            }
            results: dict[int, list[dict]] = {}
            for command_id, command_type in commands.items():
                await websocket.send(json.dumps({"id": command_id, "type": command_type}))

            while len(results) < len(commands):
                message = json.loads(await websocket.recv())
                if message.get("type") != "result":
                    continue
                command_id = message.get("id")
                if command_id not in commands:
                    continue
                if not message.get("success"):
                    raise ValueError(f"Home Assistant websocket command failed: {commands[command_id]}")
                results[command_id] = message.get("result") or []

        return {
            "areas": results.get(1, []),
            "devices": results.get(2, []),
            "entities": results.get(3, []),
        }

    @classmethod
    def get_graph(cls, account: Account) -> tuple[dict, list[dict], dict]:
        auth_obj = cls.get_auth_record(account=account, active_only=True)
        payload = cls._extract_payload(auth_obj)
        if not payload:
            raise ValueError("No active Home Assistant authorization found")

        config, states = cls.get_states(account=account)
        try:
            registry = asyncio.run(
                cls._fetch_registry_via_websocket(
                    base_url=payload.get("base_url", ""),
                    access_token=payload.get("access_token", ""),
                )
            )
        except Exception as error:
            logger.warning(f"[Home Assistant Auth] Failed to load registry via websocket, fallback to state-only grouping: {error}")
            registry = {
                "areas": [],
                "devices": [],
                "entities": [],
            }

        return config, states, registry


class MideaCloudAuthService:
    platform_name = "midea_cloud"
    platform_aliases = ("midea_cloud", "midea", "midea-cloud")

    @classmethod
    def get_auth_record(cls, account: Account, active_only: bool = False) -> PlatformAuth | None:
        queryset = PlatformAuth.objects.filter(account=account, platform_name__in=cls.platform_aliases)
        if active_only:
            queryset = queryset.filter(is_active=True)

        records = list(queryset.order_by("platform_name"))
        for record in records:
            if record.platform_name == cls.platform_name:
                return record
        return records[0] if records else None

    @classmethod
    def _extract_payload(cls, auth_obj: PlatformAuth | None) -> dict:
        payload = getattr(auth_obj, "auth_payload", None)
        return payload if isinstance(payload, dict) else {}

    @classmethod
    def validate_payload(cls, payload: dict) -> dict:
        return MideaCloudClient.validate_payload(payload)

    @classmethod
    def validate_and_store(cls, account: Account, payload: dict) -> PlatformAuth:
        logger.info(f"[Midea Auth] validate_and_store called for account_id={account.id}, email={account.email}")
        logger.debug(f"[Midea Auth] Incoming payload server={payload.get('server')}, account={payload.get('account')}")

        validated_payload = cls.validate_payload(payload)
        logger.info(f"[Midea Auth] Payload validated, server={validated_payload.get('server')}")

        logger.info(f"[Midea Auth] Creating MideaCloudClient and fetching profile...")
        client = MideaCloudClient(validated_payload)
        profile = client.get_account_profile()
        logger.info(f"[Midea Auth] Profile fetched: account={profile.get('account')}, server_name={profile.get('server_name')}, homes={len(profile.get('homes', []))}")

        auth_state = profile.get("auth_state", {})
        validated_payload.update(auth_state)
        validated_payload["account"] = profile.get("account", "")
        validated_payload["api_base"] = profile.get("api_base", "")
        validated_payload["server_name"] = profile.get("server_name", "")
        validated_payload["nickname"] = profile.get("nickname", "")
        validated_payload["homes"] = profile.get("homes", [])
        validated_payload["instance_name"] = f"Midea ({profile.get('server_name', '')})".strip()

        # 安全：加密存储密码，便于后续重新登录
        if validated_payload.get("password"):
            logger.debug(f"[Midea Auth] Encrypting password before storage")
            validated_payload["password"] = encrypt_value(validated_payload["password"])

        auth_obj, _ = PlatformAuth.objects.update_or_create(
            account=account,
            platform_name=cls.platform_name,
            defaults={
                "auth_payload": validated_payload,
                "is_active": True,
            },
        )
        logger.info(f"[Midea Auth] 已保存账户 {account.email} 的美的配置。")
        return auth_obj

    @classmethod
    def get_client(cls, account: Account) -> MideaCloudClient:
        logger.debug(f"[Midea Auth] get_client called for account_id={account.id}, email={account.email}")
        auth_obj = cls.get_auth_record(account=account, active_only=True)

        if auth_obj is None:
            logger.warning(f"[Midea Auth] No auth record found for account_id={account.id}")
            raise ValueError("No active Midea authorization found")

        payload = cls._extract_payload(auth_obj)
        if not payload:
            logger.warning(f"[Midea Auth] Empty payload for account_id={account.id}")
            raise ValueError("No active Midea authorization found")

        logger.info(f"[Midea Auth] Found auth record for account_id={account.id}, server={payload.get('server')}, account={payload.get('account')}")

        # 解密密码（如果存在加密存储的密码）
        if payload.get("password"):
            logger.debug(f"[Midea Auth] Decrypting password for account_id={account.id}")
            try:
                payload["password"] = decrypt_value(payload["password"])
                logger.debug(f"[Midea Auth] Password decrypted successfully for account_id={account.id}")
            except Exception as e:
                logger.warning(f"[Midea Auth] Password decryption failed for account_id={account.id}: {e}")
                pass

        validated_payload = cls.validate_payload(payload)
        logger.info(f"[Midea Auth] Creating MideaCloudClient for account_id={account.id}")
        return MideaCloudClient(validated_payload)


class MbApi2020AuthService:
    platform_name = "mbapi2020"
    platform_aliases = ("mbapi2020", "mercedes", "mercedes-benz", "mercedes_benz")

    @classmethod
    def get_auth_record(cls, account: Account, active_only: bool = False) -> PlatformAuth | None:
        queryset = PlatformAuth.objects.filter(account=account, platform_name__in=cls.platform_aliases)
        if active_only:
            queryset = queryset.filter(is_active=True)

        records = list(queryset.order_by("platform_name"))
        for record in records:
            if record.platform_name == cls.platform_name:
                return record
        return records[0] if records else None

    @classmethod
    def _extract_payload(cls, auth_obj: PlatformAuth | None) -> dict:
        payload = getattr(auth_obj, "auth_payload", None)
        return payload if isinstance(payload, dict) else {}

    @classmethod
    def validate_payload(cls, payload: dict) -> dict:
        return MbApi2020Client.validate_payload(payload)

    @classmethod
    def validate_and_store(cls, account: Account, payload: dict) -> PlatformAuth:
        logger.info(f"[MbApi2020 Auth] validate_and_store called for account_id={account.id}, email={account.email}")

        validated_payload = cls.validate_payload(payload)
        client = MbApi2020Client(validated_payload)
        profile = client.get_account_profile()

        auth_state = profile.get("auth_state", {})
        validated_payload.update(auth_state)
        validated_payload["account"] = profile.get("account") or validated_payload.get("account") or account.email
        validated_payload["api_base"] = profile.get("api_base", "")
        validated_payload["locale"] = profile.get("locale", validated_payload.get("locale", "en-GB"))
        validated_payload["region"] = profile.get("region", validated_payload.get("region"))
        validated_payload["nickname"] = profile.get("nickname", "")
        validated_payload["vehicles"] = profile.get("vehicles", [])
        validated_payload["pin_available"] = bool(profile.get("pin_available")) or bool(validated_payload.get("pin"))
        validated_payload["instance_name"] = f"Mercedes-Benz ({validated_payload['region']})"

        auth_obj, _ = PlatformAuth.objects.update_or_create(
            account=account,
            platform_name=cls.platform_name,
            defaults={
                "auth_payload": validated_payload,
                "is_active": True,
            },
        )
        logger.info(f"[MbApi2020 Auth] 已保存账户 {account.email} 的奔驰配置。")
        return auth_obj

    @classmethod
    def get_client(cls, account: Account) -> MbApi2020Client:
        auth_obj = cls.get_auth_record(account=account, active_only=True)
        if auth_obj is None:
            raise ValueError("No active mbapi2020 authorization found")

        payload = cls._extract_payload(auth_obj)
        if not payload:
            raise ValueError("No active mbapi2020 authorization found")

        validated_payload = cls.validate_payload(payload)

        def persist_token_state(next_state: dict[str, object]) -> None:
            merged_payload = dict(payload)
            merged_payload.update(next_state)
            PlatformAuth.objects.filter(pk=auth_obj.pk).update(auth_payload=merged_payload)
            payload.update(next_state)

        return MbApi2020Client(validated_payload, on_token_update=persist_token_state)
