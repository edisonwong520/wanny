from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from asgiref.sync import async_to_sync
from comms.models import Mission
from comms.serializers import MissionSerializer
from comms.device_command_service import DeviceCommandService
from comms.executor import ShellExecutor
from comms.services import WeChatService

def _get_mission_or_404(request, pk):
    account = getattr(request, 'account', None)
    if not account:
        return None
    try:
        return Mission.objects.get(pk=pk, account=account)
    except Mission.DoesNotExist:
        return None

@csrf_exempt
def handle_missions(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method must be GET"}, status=405)
    
    account = getattr(request, 'account', None)
    if not account:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    
    # Exclude cancelled missions from the main list, filtered by account
    missions = Mission.objects.filter(account=account).exclude(status=Mission.StatusChoices.CANCELLED)
    data = [MissionSerializer.serialize(m) for m in missions]
    return JsonResponse(data, safe=False)

@csrf_exempt
def handle_mission_approve(request, pk):
    if request.method != "POST":
        return JsonResponse({"error": "Method must be POST"}, status=405)
    
    mission = _get_mission_or_404(request, pk)
    if not mission:
        return JsonResponse({"error": "Mission not found or unauthorized"}, status=404)
        
    if mission.status != Mission.StatusChoices.PENDING:
        return JsonResponse({"error": f"Mission is already in {mission.status} state"}, status=400)
    
    # Mark as approved
    mission.status = Mission.StatusChoices.APPROVED
    mission.save()

    if mission.source_type == Mission.SourceTypeChoices.DEVICE_CLARIFICATION:
        mission.status = Mission.StatusChoices.PENDING
        mission.save(update_fields=["status", "updated_at"])
        return JsonResponse(
            {"error": "Clarification mission requires user device selection before approval."},
            status=400,
        )

    # Execute
    result = "✅ 指令已通过 web 控制台审核并执行成功。"
    if mission.source_type == Mission.SourceTypeChoices.DEVICE_CONTROL:
        try:
            payload = async_to_sync(DeviceCommandService.execute_device_operation)(
                mission.account,
                control_id=mission.control_id,
                operation_action=mission.operation_action,
                operation_value=mission.operation_value,
            )
        except Exception as e:
            payload = {"success": False, "message": f"❌ 执行异常: {str(e)}"}

        result = payload.get("message", "设备控制已执行。")
        if not payload.get("success"):
            mission.status = Mission.StatusChoices.FAILED
            mission.metadata = {
                **(mission.metadata or {}),
                "execution_result": payload,
            }
            mission.save()
            return JsonResponse({"status": "failed", "result": result})
        WeChatService._record_device_context_from_mission(
            mission,
            wechat_user_id=mission.user_id,
            content=mission.original_prompt,
            normalized_content=(mission.metadata or {}).get("normalized_msg", mission.original_prompt),
            voice_transcript=(mission.metadata or {}).get("voice_transcript", ""),
            execution_result=payload,
        )
        mission.metadata = {
            **(mission.metadata or {}),
            "execution_result": payload,
        }
    elif mission.shell_command:
        try:
            result = async_to_sync(ShellExecutor.execute_yolo)(mission.shell_command)
        except Exception as e:
            result = f"❌ 执行异常: {str(e)}"
            mission.status = Mission.StatusChoices.FAILED
            mission.metadata = {
                **(mission.metadata or {}),
                "execution_result": {
                    "success": False,
                    "message": result,
                },
            }
            mission.save()
            return JsonResponse({"status": "failed", "result": result})
        mission.metadata = {
            **(mission.metadata or {}),
            "execution_result": {
                "success": True,
                "message": result,
            },
        }

    # Mark as completed/approved (currently frontend uses 'approved' as terminal success state)
    mission.save()
    return JsonResponse({"status": "approved", "result": result})

@csrf_exempt
def handle_mission_reject(request, pk):
    if request.method != "POST":
        return JsonResponse({"error": "Method must be POST"}, status=405)
    
    mission = _get_mission_or_404(request, pk)
    if not mission:
        return JsonResponse({"error": "Mission not found or unauthorized"}, status=404)
        
    if mission.status != Mission.StatusChoices.PENDING:
        return JsonResponse({"error": "Mission cannot be rejected in current state"}, status=400)
    
    mission.status = Mission.StatusChoices.REJECTED
    mission.metadata = {
        **(mission.metadata or {}),
        "review_message": "任务已被 Web 控制台拒绝。",
    }
    mission.save()
    return JsonResponse({"status": "rejected"})
