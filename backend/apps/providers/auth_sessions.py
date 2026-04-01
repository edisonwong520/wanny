from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal
from urllib import parse
from uuid import uuid4

import requests
from django.db import close_old_connections
from mijiaAPI import mijiaAPI
from wechatbot.auth import QR_POLL_INTERVAL
from wechatbot.protocol import DEFAULT_BASE_URL, ILinkApi
from wechatbot.types import Credentials

from utils.logger import logger

from .services import WeChatAuthService, MijiaAuthService

SessionStatus = Literal["pending", "scanned", "completed", "expired", "failed"]
AuthKind = Literal["link", "qr", "form"]


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


@dataclass
class AuthorizationSession:
    id: str
    platform: str
    auth_kind: AuthKind
    status: SessionStatus
    title: str
    instruction: str
    detail: str
    action_url: str | None = None
    image_url: str | None = None
    verification_url: str | None = None
    error_message: str | None = None
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    completed_at: str | None = None

    @property
    def is_terminal(self) -> bool:
        return self.status in {"completed", "expired", "failed"}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "platform": self.platform,
            "auth_kind": self.auth_kind,
            "status": self.status,
            "title": self.title,
            "instruction": self.instruction,
            "detail": self.detail,
            "action_url": self.action_url,
            "image_url": self.image_url,
            "verification_url": self.verification_url,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "is_terminal": self.is_terminal,
        }


class AuthorizationSessionStore:
    _lock = threading.Lock()
    _sessions: dict[str, AuthorizationSession] = {}
    _latest_session_ids: dict[str, str] = {}

    @classmethod
    def reset(cls):
        with cls._lock:
            cls._sessions = {}
            cls._latest_session_ids = {}

    @classmethod
    def create(
        cls,
        *,
        platform: str,
        auth_kind: AuthKind,
        status: SessionStatus,
        title: str,
        instruction: str,
        detail: str,
        action_url: str | None = None,
        image_url: str | None = None,
        verification_url: str | None = None,
    ) -> AuthorizationSession:
        session = AuthorizationSession(
            id=uuid4().hex,
            platform=platform,
            auth_kind=auth_kind,
            status=status,
            title=title,
            instruction=instruction,
            detail=detail,
            action_url=action_url,
            image_url=image_url,
            verification_url=verification_url,
        )
        with cls._lock:
            cls._sessions[session.id] = session
            cls._latest_session_ids[platform] = session.id
        return session

    @classmethod
    def get(cls, session_id: str) -> AuthorizationSession | None:
        with cls._lock:
            return cls._sessions.get(session_id)

    @classmethod
    def get_latest(cls, platform: str) -> AuthorizationSession | None:
        with cls._lock:
            session_id = cls._latest_session_ids.get(platform)
            if not session_id:
                return None
            return cls._sessions.get(session_id)

    @classmethod
    def clear_latest(cls, platform: str):
        with cls._lock:
            session_id = cls._latest_session_ids.pop(platform, None)
            if session_id:
                cls._sessions.pop(session_id, None)

    @classmethod
    def update(cls, session_id: str, **updates) -> AuthorizationSession | None:
        with cls._lock:
            session = cls._sessions.get(session_id)
            if session is None:
                return None

            for field_name, field_value in updates.items():
                setattr(session, field_name, field_value)
            session.updated_at = _now_iso()
            if session.is_terminal and session.completed_at is None:
                session.completed_at = session.updated_at
            return session


class WeChatAuthorizationService:
    platform_name = "wechat"

    @classmethod
    def start_session(cls, account, *, force: bool = False) -> AuthorizationSession:
        existing = AuthorizationSessionStore.get_latest(cls.platform_name)
        if existing and not existing.is_terminal:
            return existing

        if not force:
            auth_obj = WeChatAuthService.get_auth_record(account=account, active_only=True)
            payload = WeChatAuthService._extract_payload(auth_obj)
            if payload:
                WeChatAuthService.write_cred_file_from_db(account=account)
                return AuthorizationSessionStore.create(
                    platform=cls.platform_name,
                    auth_kind="link",
                    status="completed",
                    title="微信授权已连接",
                    instruction="当前微信授权已经可用，无需重新扫码。",
                    detail="如果你需要更换账号，可以再次点击“重新授权”。",
                )

        WeChatAuthService.clear_cred_file(account=account)

        api = ILinkApi()
        qr_payload = asyncio.run(api.get_qr_code(DEFAULT_BASE_URL))
        qr_url = qr_payload["qrcode_img_content"]
        image_url = qr_url if str(qr_url).startswith(("http://", "https://", "data:image/")) else None

        session = AuthorizationSessionStore.create(
            platform=cls.platform_name,
            auth_kind="link",
            status="pending",
            title="微信授权进行中",
            instruction="请在微信中打开授权链接，完成扫码并在授权完成后回到本页。",
            detail="确认完成后，页面会自动刷新为已连接状态。",
            action_url=qr_url,
            image_url=image_url,
        )

        monitor_thread = threading.Thread(
            target=cls._monitor_qr_status,
            args=(session.id, account, qr_payload["qrcode"], DEFAULT_BASE_URL),
            daemon=True,
        )
        monitor_thread.start()
        return session

    @classmethod
    def _monitor_qr_status(cls, session_id: str, account, qr_code: str, base_url: str):
        close_old_connections()
        api = ILinkApi()

        try:
            while True:
                status = asyncio.run(api.poll_qr_status(base_url, qr_code))
                current = status["status"]

                if current == "scaned":
                    AuthorizationSessionStore.update(
                        session_id,
                        status="scanned",
                        detail="二维码已扫描，请在微信中点确认完成授权。",
                    )
                elif current == "expired":
                    AuthorizationSessionStore.update(
                        session_id,
                        status="expired",
                        error_message="二维码已过期，请重新发起微信授权。",
                        detail="二维码已过期，请点击重新授权。",
                    )
                    return
                elif current == "confirmed":
                    token = status.get("bot_token")
                    account_id = status.get("ilink_bot_id")
                    user_id = status.get("ilink_user_id")
                    if not token or not account_id or not user_id:
                        raise ValueError("WeChat login confirmed but credentials are incomplete")

                    creds = Credentials(
                        token=token,
                        base_url=status.get("baseurl") or base_url,
                        account_id=account_id,
                        user_id=user_id,
                        saved_at=_now_iso(),
                    )
                    cred_path = WeChatAuthService.save_credentials_to_file(account=account, creds=creds)
                    WeChatAuthService.sync_cred_file_to_db(
                        account=account,
                        cred_file_path=cred_path,
                        fallback_payload={
                            "token": creds.token,
                            "baseUrl": creds.base_url,
                            "accountId": creds.account_id,
                            "userId": creds.user_id,
                            "user_id": creds.user_id,
                            "savedAt": creds.saved_at,
                        },
                    )
                    AuthorizationSessionStore.update(
                        session_id,
                        status="completed",
                        detail="微信授权完成，Bot 已可读取这份凭证。",
                    )

                    # 触发后台同步挂图（虽然微信暂时没有对应的 IOT 映射但保持通用逻辑）
                    try:
                        from devices.services import DeviceDashboardService
                        DeviceDashboardService.sync_after_provider_change(account, trigger="connect_wechat")
                    except Exception as e:
                        logger.error(f"[WeChat Auth Sync] Trigger sync failed: {e}")
                    return

                time.sleep(QR_POLL_INTERVAL)
        except Exception as e:
            logger.error(f"[WeChat Auth] 轮询二维码状态失败: {e}")
            AuthorizationSessionStore.update(
                session_id,
                status="failed",
                error_message=str(e),
                detail="微信授权流程失败，请重新发起。",
            )
        finally:
            close_old_connections()


class MijiaAuthorizationService:
    platform_name = MijiaAuthService.platform_name

    @classmethod
    def start_session(cls, account, *, force: bool = False) -> AuthorizationSession:
        existing = AuthorizationSessionStore.get_latest(cls.platform_name)
        if existing and not existing.is_terminal:
            return existing

        if not force:
            auth_obj = MijiaAuthService.get_auth_record(account=account, active_only=True)
            payload = MijiaAuthService._extract_payload(auth_obj)
            if payload:
                MijiaAuthService.write_auth_file_from_db(account=account)
                return AuthorizationSessionStore.create(
                    platform=cls.platform_name,
                    auth_kind="qr",
                    status="completed",
                    title="米家授权已连接",
                    instruction="当前米家账号授权已经可用，无需重新扫码。",
                    detail="如果你需要切换账号，可以再次点击“重新授权”。",
                )

        auth_path = MijiaAuthService.resolve_auth_file_path(account=account)
        if force:
            if auth_path.exists():
                auth_path.unlink()
                logger.info(f"[Mijia Auth] 强制重新授权：已清理账户 {account.email} 的本地凭证文件。")
        else:
            # 尝试从数据库同步回本地
            MijiaAuthService.write_auth_file_from_db(account=account)

        api = mijiaAPI(auth_data_path=str(auth_path))
        location_data = api._get_location()
        if location_data.get("code", -1) == 0 and location_data.get("message", "") == "刷新Token成功":
            api._save_auth_data()
            api._init_session()
            MijiaAuthService.sync_auth_file_to_db(
                account=account,
                auth_file_path=auth_path,
                fallback_payload=api.auth_data,
            )
            return AuthorizationSessionStore.create(
                platform=cls.platform_name,
                auth_kind="qr",
                status="completed",
                title="米家授权已恢复",
                instruction="已有可用的米家授权，已直接恢复连接。",
                detail="如果需要重新扫码绑定新账号，可以点击“重新授权”。",
            )

        location_data.update(
            {
                "theme": "",
                "bizDeviceType": "",
                "_hasLogo": "false",
                "_qrsize": "240",
                "_dc": str(int(time.time() * 1000)),
            }
        )
        headers = {
            "User-Agent": api.user_agent,
            "Accept-Encoding": "gzip",
            "Content-Type": "application/x-www-form-urlencoded",
            "Connection": "keep-alive",
        }
        login_url = api.login_url + "?" + parse.urlencode(location_data)
        login_ret = requests.get(login_url, headers=headers)
        login_data = api._handle_ret(login_ret)

        qr_content = login_data.get("qr")
        if qr_content and not str(qr_content).startswith(("http://", "https://", "data:image/")):
            qr_content = f"data:image/png;base64,{qr_content}"

        session = AuthorizationSessionStore.create(
            platform=cls.platform_name,
            auth_kind="qr",
            status="pending",
            title="米家授权进行中",
            instruction="请使用米家 App 扫描下方二维码并完成确认。",
            detail="确认完成后，页面会自动刷新为已连接状态。",
            image_url=qr_content,
            action_url=login_data.get("loginUrl"),
        )

        monitor_thread = threading.Thread(
            target=cls._wait_for_confirmation,
            args=(session.id, account, api, headers, login_data["lp"], auth_path),
            daemon=True,
        )
        monitor_thread.start()
        return session

    @classmethod
    def _wait_for_confirmation(
        cls,
        session_id: str,
        account,
        api: mijiaAPI,
        headers: dict,
        lp_url: str,
        auth_path,
    ):
        close_old_connections()
        try:
            session = requests.Session()
            lp_ret = session.get(lp_url, headers=headers, timeout=120)
            lp_data = api._handle_ret(lp_ret)

            auth_keys = ["psecurity", "nonce", "ssecurity", "passToken", "userId", "cUserId"]
            for key in auth_keys:
                api.auth_data[key] = lp_data[key]

            callback_url = lp_data["location"]
            session.get(callback_url, headers=headers)
            cookies = session.cookies.get_dict()
            api.auth_data.update(cookies)
            api.auth_data.update(
                {
                    "expireTime": int((datetime.now() + timedelta(days=30)).timestamp() * 1000),
                }
            )
            api._save_auth_data()
            api._init_session()
            MijiaAuthService.sync_auth_file_to_db(
                account=account,
                auth_file_path=auth_path,
                fallback_payload=api.auth_data,
            )
            AuthorizationSessionStore.update(
                session_id,
                status="completed",
                detail="米家授权完成，设备侧接口已可复用这份凭证。",
            )

            # 立即触发后台同步以拉取最新设备数据
            try:
                from devices.services import DeviceDashboardService
                DeviceDashboardService.sync_after_provider_change(account, trigger="connect_mijia")
            except Exception as e:
                logger.error(f"[Mijia Auth Sync] Trigger sync failed: {e}")
        except requests.exceptions.Timeout:
            AuthorizationSessionStore.update(
                session_id,
                status="expired",
                error_message="二维码等待确认超时，请重新发起米家授权。",
                detail="二维码已超时，请重新授权。",
            )
        except Exception as e:
            logger.error(f"[Mijia Auth] 等待扫码确认失败: {e}")
            AuthorizationSessionStore.update(
                session_id,
                status="failed",
                error_message=str(e),
                detail="米家授权流程失败，请重新发起。",
            )
        finally:
            close_old_connections()
