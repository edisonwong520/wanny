import json
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from utils.logger import logger
from .models import PlatformAuth

@csrf_exempt
def handle_platform_auth(request):
    """
    通用代理与授权接入点:
    POST /api/providers/auth/
    接收 {
      "platform": "mijia",      # 必须带平台名称
      "payload": { ... }        # 需要存放的全部鉴权信息（例如 token、uid 等）
    }
    """
    if request.method != 'POST':
        return JsonResponse({"error": "Method must be POST"}, status=405)

    try:
        data = json.loads(request.body)
        platform_name = data.get("platform")
        auth_payload = data.get("payload", {})
        
        if not platform_name:
            return JsonResponse({"error": "Missing 'platform' in request"}, status=400)

        # 始终通过平台名称做到单一更新，避免数据库重复创建多条该平台的有效记录
        obj, created = PlatformAuth.objects.update_or_create(
            platform_name=platform_name,
            defaults={
                "auth_payload": auth_payload,
                "is_active": True
            }
        )
        logger.info(f"Platform auth updated for {platform_name}. Created: {created}")

        return JsonResponse({
            "status": "success", 
            "message": f"Authorization applied for {platform_name}"
        }, status=200)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON mapping"}, status=400)
    except Exception as e:
        logger.error(f"Error handling platform auth: {str(e)}")
        return JsonResponse({"error": "Server inner error, please check backend logs."}, status=500)
