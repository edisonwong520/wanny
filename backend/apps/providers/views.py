import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from utils.logger import logger

from .auth_sessions import (
    AuthorizationSessionStore,
    WeChatAuthorizationService,
    MijiaAuthorizationService,
)
from .models import PlatformAuth
from .services import MijiaAuthService, WeChatAuthService
from .services import HomeAssistantAuthService


PLATFORM_CATALOG = {
    "wechat": {
        "display_name": "WeChat",
        "display_name_zh": "微信",
        "category": "messaging",
        "auth_mode": "link",
    },
    "mijia": {
        "display_name": "Mijia",
        "display_name_zh": "米家",
        "category": "iot",
        "auth_mode": "qr",
    },
    "home_assistant": {
        "display_name": "Home Assistant",
        "display_name_zh": "Home Assistant",
        "category": "iot",
        "auth_mode": "form",
    },
}

PLATFORM_ALIASES = {
    "xiaomi": MijiaAuthService.platform_name,
    "ha": HomeAssistantAuthService.platform_name,
    "homeassistant": HomeAssistantAuthService.platform_name,
}

SENSITIVE_KEYWORDS = (
    "token",
    "secret",
    "password",
    "cookie",
    "session",
    "credential",
    "cred",
    "authorization",
    "auth_code",
)


def _normalize_platform_name(value) -> str:
    normalized_name = str(value or "").strip().lower()
    return PLATFORM_ALIASES.get(normalized_name, normalized_name)


def _get_platform_lookup_names(platform_name: str) -> tuple[str, ...]:
    if platform_name == MijiaAuthService.platform_name:
        return MijiaAuthService.platform_aliases
    return (platform_name,)


def _get_platform_auth(request, platform_name: str) -> PlatformAuth | None:
    account = getattr(request, 'account', None)
    if not account:
        return None
    normalized_name = _normalize_platform_name(platform_name)
    if normalized_name == MijiaAuthService.platform_name:
        return MijiaAuthService.get_auth_record(account=account)

    return PlatformAuth.objects.filter(account=account, platform_name=normalized_name).first()


def _get_platform_auth_queryset(request, platform_name: str):
    account = getattr(request, 'account', None)
    normalized_name = _normalize_platform_name(platform_name)
    return PlatformAuth.objects.filter(account=account, platform_name__in=_get_platform_lookup_names(normalized_name))


def _is_sensitive_key(key: str) -> bool:
    key = str(key or "").strip().lower()
    return any(keyword in key for keyword in SENSITIVE_KEYWORDS)


def _mask_string(value: str) -> str:
    if len(value) <= 4:
        return "*" * len(value)
    return f"{value[:2]}***{value[-2:]}"


def _mask_sensitive_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        return _mask_string(value.strip())
    if isinstance(value, list):
        return ["***" for _ in value]
    if isinstance(value, dict):
        return {key: "***" for key in value.keys()}
    return "***"


def _mask_payload(payload):
    if isinstance(payload, dict):
        masked = {}
        for key, value in payload.items():
            if _is_sensitive_key(key):
                masked[key] = _mask_sensitive_value(value)
            else:
                masked[key] = _mask_payload(value)
        return masked

    if isinstance(payload, list):
        return [_mask_payload(item) for item in payload]

    return payload


def _serialize_platform_auth(obj: PlatformAuth | None, platform_name: str | None = None) -> dict:
    normalized_name = _normalize_platform_name(platform_name or getattr(obj, "platform_name", ""))
    catalog_meta = PLATFORM_CATALOG.get(normalized_name, {})
    payload = getattr(obj, "auth_payload", {}) or {}
    payload_keys = sorted(payload.keys()) if isinstance(payload, dict) else []
    has_credentials = bool(payload_keys)
    is_active = bool(getattr(obj, "is_active", False))

    if obj is None:
        status = "not_connected"
    elif not is_active:
        status = "disabled"
    elif has_credentials:
        status = "connected"
    else:
        status = "pending"

    return {
        "platform": normalized_name,
        "display_name": catalog_meta.get("display_name", normalized_name.title()),
        "display_name_zh": catalog_meta.get("display_name_zh", normalized_name),
        "category": catalog_meta.get("category", "custom"),
        "auth_mode": catalog_meta.get("auth_mode", "custom"),
        "configured": obj is not None,
        "status": status,
        "is_active": is_active,
        "has_credentials": has_credentials,
        "payload_keys": payload_keys,
        "payload_preview": _mask_payload(payload) if isinstance(payload, dict) else {},
        "created_at": obj.created_at.isoformat() if obj else None,
        "updated_at": obj.updated_at.isoformat() if obj else None,
    }


def _load_request_json(request):
    try:
        return json.loads(request.body or "{}"), None
    except json.JSONDecodeError:
        return None, JsonResponse({"error": "Invalid JSON mapping"}, status=400)


def _serialize_authorization_session(request, platform_name: str):
    session = AuthorizationSessionStore.get_latest(platform_name)
    if session is None:
        return None
    # 只在过期或失败且没有授权记录时返回 null
    if session.status in ("expired", "failed") and _get_platform_auth(request, platform_name) is None:
        return None
    return session.to_dict()


@csrf_exempt
def handle_platform_auth(request):
    if request.method == "GET":
        account = getattr(request, 'account', None)
        if not account:
             return JsonResponse({"error": "Unauthorized"}, status=401)
             
        stored_records = {
            _normalize_platform_name(obj.platform_name): obj
            for obj in PlatformAuth.objects.filter(account=account).order_by("platform_name")
        }
        platform_names = list(PLATFORM_CATALOG.keys())
        for name in stored_records.keys():
            if name not in platform_names:
                platform_names.append(name)

        providers = [
            _serialize_platform_auth(stored_records.get(name), platform_name=name)
            for name in platform_names
        ]
        return JsonResponse({"status": "success", "providers": providers}, status=200)

    if request.method != "POST":
        return JsonResponse({"error": "Method must be GET or POST"}, status=405)

    data, error_response = _load_request_json(request)
    if error_response:
        return error_response

    try:
        platform_name = _normalize_platform_name(data.get("platform"))
        auth_payload = data.get("payload", {})

        if not platform_name:
            return JsonResponse({"error": "Missing 'platform' in request"}, status=400)
        if auth_payload is None:
            auth_payload = {}
        if not isinstance(auth_payload, dict):
            return JsonResponse({"error": "'payload' must be a JSON object"}, status=400)

        account = getattr(request, 'account', None)
        if not account:
            return JsonResponse({"error": "Unauthorized"}, status=401)

        # 始终通过平台名称做到单一更新，避免数据库重复创建多条该平台的有效记录
        obj, created = PlatformAuth.objects.update_or_create(
            account=account,
            platform_name=platform_name,
            defaults={
                "auth_payload": auth_payload,
                "is_active": bool(data.get("is_active", True)),
            }
        )
        logger.info(f"Platform auth updated for {platform_name}. Created: {created}")

        return JsonResponse({
            "status": "success",
            "message": f"Authorization applied for {platform_name}",
            "provider": _serialize_platform_auth(obj),
        }, status=200)
    except Exception as e:
        logger.error(f"Error handling platform auth: {str(e)}")
        return JsonResponse({"error": "Server inner error, please check backend logs."}, status=500)


@csrf_exempt
def handle_platform_auth_authorize(request, platform_name: str):
    """
    平台交互式授权入口：
    - GET /api/providers/auth/<platform>/authorize/
    - POST /api/providers/auth/<platform>/authorize/
    """
    normalized_name = _normalize_platform_name(platform_name)
    if normalized_name not in PLATFORM_CATALOG:
        return JsonResponse({"error": f"Unknown platform: {normalized_name}"}, status=404)

    account = getattr(request, 'account', None)
    if not account:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    if request.method == "GET":
        return JsonResponse(
            {
                "status": "success",
                "provider": _serialize_platform_auth(_get_platform_auth(request, normalized_name), platform_name=normalized_name),
                "session": _serialize_authorization_session(request, normalized_name),
            },
            status=200,
        )

    if request.method != "POST":
        return JsonResponse({"error": "Method must be GET or POST"}, status=405)

    data, error_response = _load_request_json(request)
    if error_response:
        return error_response

    force = bool(data.get("force", False))

    try:
        if normalized_name == WeChatAuthorizationService.platform_name:
            session = WeChatAuthorizationService.start_session(account=account, force=force)
        elif normalized_name == MijiaAuthorizationService.platform_name:
            session = MijiaAuthorizationService.start_session(account=account, force=force)
        elif normalized_name == HomeAssistantAuthService.platform_name:
            auth_payload = data.get("payload", {})
            auth_obj = HomeAssistantAuthService.validate_and_store(account=account, payload=auth_payload)
            session = AuthorizationSessionStore.create(
                platform=normalized_name,
                auth_kind="form",
                status="completed",
                title="Home Assistant 已连接",
                instruction="已完成 Home Assistant 服务校验并保存授权信息。",
                detail=f"实例 {auth_obj.auth_payload.get('instance_name') or 'Home Assistant'} 已可用于设备同步。",
            )
        else:
            return JsonResponse({"error": f"Interactive login is not supported for {normalized_name}"}, status=400)

        return JsonResponse(
            {
                "status": "success",
                "provider": _serialize_platform_auth(_get_platform_auth(request, normalized_name), platform_name=normalized_name),
                "session": session.to_dict(),
            },
            status=200,
        )
    except Exception as e:
        logger.error(f"Error handling platform authorization for {normalized_name}: {str(e)}")
        return JsonResponse({"error": "Platform authorization failed, please check backend logs."}, status=500)


@csrf_exempt
def handle_platform_auth_detail(request, platform_name: str):
    """
    单个平台授权管理：
    - GET /api/providers/auth/<platform>/
    - PATCH /api/providers/auth/<platform>/
    - DELETE /api/providers/auth/<platform>/
    """
    normalized_name = _normalize_platform_name(platform_name)
    account = getattr(request, 'account', None)
    if not account:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    auth_obj = _get_platform_auth(request, normalized_name)

    if request.method == "GET":
        if auth_obj is None and normalized_name not in PLATFORM_CATALOG:
            return JsonResponse({"error": f"Unknown platform: {normalized_name}"}, status=404)
        return JsonResponse(
            {"status": "success", "provider": _serialize_platform_auth(auth_obj, platform_name=normalized_name)},
            status=200,
        )

    if request.method == "PATCH":
        if auth_obj is None:
            return JsonResponse({"error": f"Platform auth not found: {normalized_name}"}, status=404)

        data, error_response = _load_request_json(request)
        if error_response:
            return error_response

        updates = {}
        if "payload" in data:
            incoming_payload = data.get("payload") or {}
            if not isinstance(incoming_payload, dict):
                return JsonResponse({"error": "'payload' must be a JSON object"}, status=400)

            replace_payload = bool(data.get("replace_payload", False))
            merged_payload = incoming_payload if replace_payload else {**(auth_obj.auth_payload or {}), **incoming_payload}
            updates["auth_payload"] = merged_payload

        if "is_active" in data:
            updates["is_active"] = bool(data.get("is_active"))

        if not updates:
            return JsonResponse({"error": "Nothing to update"}, status=400)

        merged_payload = updates.get("auth_payload", auth_obj.auth_payload)
        is_active = updates.get("is_active", auth_obj.is_active)
        account = getattr(request, 'account', None)
        auth_obj, _ = PlatformAuth.objects.update_or_create(
            account=account,
            platform_name=normalized_name,
            defaults={
                "auth_payload": merged_payload,
                "is_active": is_active,
            },
        )

        logger.info(f"Platform auth patched for {normalized_name}. Fields: {sorted(updates.keys())}")
        return JsonResponse(
            {"status": "success", "provider": _serialize_platform_auth(auth_obj)},
            status=200,
        )

    if request.method == "DELETE":
        if auth_obj is None:
            return JsonResponse({"error": f"Platform auth not found: {normalized_name}"}, status=404)

        _get_platform_auth_queryset(request, normalized_name).delete()
        AuthorizationSessionStore.clear_latest(normalized_name)

        # 触发各平台本地与业务业务数据清理
        if normalized_name == MijiaAuthService.platform_name:
            MijiaAuthService.write_auth_file_from_db(account)
            from devices.services import DeviceDashboardService
            DeviceDashboardService.sync_after_provider_change(account, trigger="disconnect_mijia")
        elif normalized_name == HomeAssistantAuthService.platform_name:
            from devices.services import DeviceDashboardService
            DeviceDashboardService.sync_after_provider_change(account, trigger="disconnect_home_assistant")
        elif normalized_name == WeChatAuthService.platform_name:
            WeChatAuthService.clear_cred_file(account=account)

        logger.info(f"Platform auth and related data records deleted for {normalized_name}")
        return JsonResponse(
            {"status": "success", "message": f"Authorization and related data removed for {normalized_name}"},
            status=200,
        )

    return JsonResponse({"error": "Method must be GET, PATCH or DELETE"}, status=405)


@csrf_exempt
def handle_platform_auth_login(request, platform_name: str):
    """
    触发特定平台的交互式授权流程：
    - POST /api/providers/auth/<platform>/login/
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method must be POST"}, status=405)

    normalized_name = _normalize_platform_name(platform_name)
    if normalized_name != MijiaAuthService.platform_name:
        return JsonResponse({"error": f"Interactive login is not supported for {normalized_name}"}, status=400)

    try:
        account = getattr(request, 'account', None)
        if not account:
            return JsonResponse({"error": "Unauthorized"}, status=401)
            
        auth_obj = MijiaAuthService.login_and_store(account)
        return JsonResponse(
            {
                "status": "success",
                "message": "Mijia authorization completed",
                "provider": _serialize_platform_auth(auth_obj),
            },
            status=200,
        )
    except Exception as e:
        logger.error(f"Error handling platform login for {normalized_name}: {str(e)}")
        return JsonResponse({"error": "Platform login failed, please check backend logs."}, status=500)
