import json

from django.db.models import Case, Exists, IntegerField, OuterRef, Q, Value, When
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from utils.logger import logger

from .models import DeviceControl, DeviceSnapshot
from .services import DeviceDashboardService


@csrf_exempt
def handle_device_dashboard(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method must be GET"}, status=405)

    account = getattr(request, 'account', None)
    if not account:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    try:
        return JsonResponse(DeviceDashboardService.get_dashboard(account), status=200)
    except Exception as error:
        logger.error(f"Failed to load device dashboard: {error}")
        return JsonResponse({"error": "Unable to load device dashboard."}, status=500)


@csrf_exempt
def handle_device_list(request):
    """设备列表API，支持分页、搜索、房间筛选"""
    if request.method != "GET":
        return JsonResponse({"error": "Method must be GET"}, status=405)

    account = getattr(request, 'account', None)
    if not account:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    try:
        # 获取查询参数
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 10))
        search = request.GET.get("search", "").strip()
        room_id = request.GET.get("room_id", "").strip()
        raw_platforms = request.GET.getlist("platforms")
        if not raw_platforms:
            comma_separated_platforms = request.GET.get("platforms", "").strip()
            if comma_separated_platforms:
                raw_platforms = comma_separated_platforms.split(",")
        platforms = {
            str(platform).strip().lower()
            for platform in raw_platforms
            if str(platform).strip()
        }

        # 限制page_size范围
        page_size = min(max(page_size, 1), 50)

        # 构建查询
        queryset = DeviceSnapshot.objects.filter(account=account).select_related("room")

        if search:
            queryset = queryset.filter(name__icontains=search)

        if room_id and room_id != "all":
            queryset = queryset.filter(room__slug=room_id)

        if platforms:
            platform_query = Q()
            for platform in platforms:
                platform_query |= Q(external_id__startswith=f"{platform}:")
            queryset = queryset.filter(platform_query)

        enabled_toggle_subquery = DeviceControl.objects.filter(
            account=account,
            device=OuterRef("pk"),
            kind=DeviceControl.KindChoices.TOGGLE,
        ).filter(
            Q(value="on") | Q(value=True) | Q(value=1) | Q(value="true")
        )

        queryset = queryset.annotate(
            status_order=Case(
                When(status=DeviceSnapshot.StatusChoices.ONLINE, then=Value(0)),
                When(status=DeviceSnapshot.StatusChoices.ATTENTION, then=Value(1)),
                When(status=DeviceSnapshot.StatusChoices.OFFLINE, then=Value(2)),
                default=Value(9),
                output_field=IntegerField(),
            ),
            platform_order=Case(
                When(external_id__startswith="home_assistant:", then=Value(0)),
                When(external_id__startswith="midea_cloud:", then=Value(1)),
                When(external_id__startswith="mijia:", then=Value(2)),
                When(external_id__startswith="mbapi2020:", then=Value(3)),
                default=Value(9),
                output_field=IntegerField(),
            ),
            enabled_order=Case(
                When(Exists(enabled_toggle_subquery), then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            ),
        )

        # 排序：状态优先，其次启用中设备，再按平台，其余回退到既有权重
        queryset = queryset.order_by("status_order", "enabled_order", "platform_order", "sort_order", "id")

        # 分页
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)

        # 序列化设备数据
        devices = []
        for device in page_obj:
            devices.append({
                "id": device.external_id,
                "room_id": device.room.slug if device.room else None,
                "room_name": device.room.name if device.room else "",
                "name": device.name,
                "category": device.category,
                "status": device.status,
                "telemetry": device.telemetry,
            })

        return JsonResponse({
            "status": "success",
            "devices": devices,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": paginator.count,
                "total_pages": paginator.num_pages,
            },
        }, status=200)
    except Exception as error:
        logger.error(f"Failed to load device list: {error}")
        return JsonResponse({"error": "Unable to load device list."}, status=500)


@csrf_exempt
def handle_device_detail(request, device_id: str):
    """获取单个设备详情"""
    if request.method != "GET":
        return JsonResponse({"error": "Method must be GET"}, status=405)

    account = getattr(request, 'account', None)
    if not account:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    try:
        device = DeviceSnapshot.objects.filter(
            account=account,
            external_id=device_id
        ).select_related("room").prefetch_related("controls").first()

        if not device:
            return JsonResponse({"error": "Device not found"}, status=404)

        controls = [
            DeviceDashboardService._serialize_control(control)
            for control in device.controls.all()
        ]

        return JsonResponse({
            "status": "success",
            "device": {
                "id": device.external_id,
                "room_id": device.room.slug if device.room else None,
                "room_name": device.room.name if device.room else "",
                "name": device.name,
                "category": device.category,
                "status": device.status,
                "telemetry": device.telemetry,
                "note": device.note,
                "capabilities": device.capabilities,
                "last_seen": device.last_seen.isoformat() if device.last_seen else None,
                "controls": controls,
            },
        }, status=200)
    except Exception as error:
        logger.error(f"Failed to load device detail {device_id}: {error}")
        return JsonResponse({"error": "Unable to load device detail."}, status=500)


@csrf_exempt
def handle_device_dashboard_refresh(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method must be POST"}, status=405)

    account = getattr(request, 'account', None)
    if not account:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    try:
        payload = DeviceDashboardService.request_refresh(account, trigger="api")
        payload["status"] = "accepted"
        payload["message"] = "Device dashboard refresh has been queued."
        return JsonResponse(payload, status=202)
    except Exception as error:
        logger.error(f"Failed to refresh device dashboard: {error}")
        return JsonResponse({"error": "Unable to refresh device dashboard."}, status=500)


@csrf_exempt
def handle_device_control(request, device_id: str, control_id: str):
    if request.method != "POST":
        return JsonResponse({"error": "Method must be POST"}, status=405)

    account = getattr(request, 'account', None)
    if not account:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    try:
        action = str(payload.get("action") or "").strip()
        value = payload.get("value")
        result = DeviceDashboardService.execute_control(
            account,
            device_external_id=device_id,
            control_external_id=control_id,
            action=action,
            value=value,
        )
        return JsonResponse(result, status=200)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)
    except Exception as error:
        logger.error(f"Failed to execute device control {device_id}/{control_id}: {error}")
        return JsonResponse({"error": "Unable to execute device control."}, status=500)
