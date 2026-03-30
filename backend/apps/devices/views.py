from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from utils.logger import logger

from .services import DeviceDashboardService


@csrf_exempt
def handle_device_dashboard(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method must be GET"}, status=405)

    try:
        return JsonResponse(DeviceDashboardService.get_dashboard(), status=200)
    except Exception as error:
        logger.error(f"Failed to load device dashboard: {error}")
        return JsonResponse({"error": "Unable to load device dashboard."}, status=500)


@csrf_exempt
def handle_device_dashboard_refresh(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method must be POST"}, status=405)

    try:
        payload = DeviceDashboardService.request_refresh(trigger="api")
        payload["status"] = "accepted"
        payload["message"] = "Device dashboard refresh has been queued."
        return JsonResponse(payload, status=202)
    except Exception as error:
        logger.error(f"Failed to refresh device dashboard: {error}")
        return JsonResponse({"error": "Unable to refresh device dashboard."}, status=500)
