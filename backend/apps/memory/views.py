import json

from asgiref.sync import async_to_sync
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from utils.logger import logger
from memory.services import MemoryService


@csrf_exempt
def handle_profiles(request):
    """
    用户画像接口：
    - GET /api/memory/profiles/
    - POST /api/memory/profiles/
      {
        "key": "preferred_temp",
        "value": "26",
        "category": "Environment"
      }
    """
    account = getattr(request, "account", None)
    if not account:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    if request.method == "GET":
        profiles = async_to_sync(MemoryService.list_profiles)(account)
        return JsonResponse({"status": "success", "profiles": profiles}, status=200)

    if request.method != "POST":
        return JsonResponse({"error": "Method must be GET or POST"}, status=405)

    try:
        data = json.loads(request.body)
        key = str(data.get("key", "")).strip()
        value = str(data.get("value", "")).strip()
        category = str(data.get("category", "Other")).strip() or "Other"

        if not key:
            return JsonResponse({"error": "Missing required field: key"}, status=400)

        profile = async_to_sync(MemoryService.upsert_manual_profile)(
            account=account,
            key=key,
            value=value,
            category=category,
        )
        if not profile:
            return JsonResponse({"error": "Failed to update profile"}, status=500)

        return JsonResponse({"status": "success", "profile": profile}, status=200)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    except Exception as e:
        logger.error(f"[MemoryView] 处理画像请求失败: {e}")
        return JsonResponse({"error": "Server inner error, please check backend logs."}, status=500)
