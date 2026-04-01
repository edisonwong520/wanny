import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from utils.logger import logger

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
