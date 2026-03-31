from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from accounts.models import Account

from mijiaAPI import mijiaAPI
from wechatbot.auth import save_credentials
from wechatbot.types import Credentials

from utils.logger import logger

from .models import PlatformAuth


class WeChatAuthService:
    platform_name = "wechat"
    cred_file_name = "credentials/wechat_credentials.json"

    @classmethod
    def resolve_cred_file_path(cls, cred_file_path=None) -> Path:
        if cred_file_path:
            path = Path(cred_file_path)
        else:
            path = Path(__file__).resolve().parents[2] / cls.cred_file_name

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
        path = cls.resolve_cred_file_path(cred_file_path)
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
    def clear_cred_file(cls, cred_file_path=None):
        path = cls.resolve_cred_file_path(cred_file_path)
        if path.exists():
            path.unlink()
            logger.info("[WeChat Auth] 已清理本地微信凭证文件。")
        return path

    @classmethod
    def sync_cred_file_to_db(cls, account: Account, cred_file_path=None, fallback_payload=None) -> PlatformAuth:
        path = cls.resolve_cred_file_path(cred_file_path)

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
    def save_credentials_to_file(cls, creds: Credentials, cred_file_path=None) -> Path:
        path = cls.resolve_cred_file_path(cred_file_path)
        asyncio.run(save_credentials(creds, path))
        return path


class MijiaAuthService:
    platform_name = "mijia"
    platform_aliases = ("mijia", "xiaomi")
    auth_file_name = "credentials/mijia_auth.json"

    @classmethod
    def resolve_auth_file_path(cls, auth_file_path=None) -> Path:
        if auth_file_path:
            path = Path(auth_file_path)
        else:
            path = Path(__file__).resolve().parents[2] / cls.auth_file_name

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
        # 为不同用户使用不同的文件名，以防冲突
        path = cls.resolve_auth_file_path(auth_file_path)
        if not auth_file_path:
             path = path.parent / f"mijia_auth_{account.id}.json"
        
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
        path = cls.resolve_auth_file_path(auth_file_path)

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
        path = cls.resolve_auth_file_path(auth_file_path)
        api = cls.get_authenticated_api(account=account, auth_file_path=path, require_login=True)
        return cls.sync_auth_file_to_db(
            account=account,
            auth_file_path=path,
            fallback_payload=getattr(api, "auth_data", {}),
        )
