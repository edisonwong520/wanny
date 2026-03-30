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
    - GET /api/memory/profiles/?user_id=xxx
    - POST /api/memory/profiles/
      {
        "user_id": "wxid_xxx",
        "key": "preferred_temp",
        "value": "26",
        "category": "Environment"
      }
    """
    if request.method == "GET":
        user_id = request.GET.get("user_id", "").strip()
        if not user_id:
            return JsonResponse({"error": "Missing 'user_id' in query string"}, status=400)

        profiles = async_to_sync(MemoryService.list_profiles)(user_id)
        return JsonResponse({"status": "success", "profiles": profiles}, status=200)

    if request.method != "POST":
        return JsonResponse({"error": "Method must be GET or POST"}, status=405)

    try:
        data = json.loads(request.body)
        user_id = str(data.get("user_id", "")).strip()
        key = str(data.get("key", "")).strip()
        value = str(data.get("value", "")).strip()
        category = str(data.get("category", "Other")).strip() or "Other"

        if not user_id or not key:
            return JsonResponse({"error": "Missing required fields: user_id, key"}, status=400)

        profile = async_to_sync(MemoryService.upsert_manual_profile)(
            user_id=user_id,
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
