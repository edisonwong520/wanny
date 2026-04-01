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

from utils.logger import logger

from .models import PlatformAuth


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
