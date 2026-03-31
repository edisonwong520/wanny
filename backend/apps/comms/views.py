from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from comms.models import Mission
from comms.serializers import MissionSerializer
from comms.executor import ShellExecutor

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

    # Execute
    result = "✅ 指令已通过 web 控制台审核并执行成功。"
    if mission.shell_command:
        import asyncio
        from asgiref.sync import async_to_sync
        
        # Use ShellExecutor
        try:
            result = async_to_sync(ShellExecutor.execute_yolo)(mission.shell_command)
        except Exception as e:
            result = f"❌ 执行异常: {str(e)}"
            mission.status = Mission.StatusChoices.FAILED
            mission.save()
            return JsonResponse({"status": "failed", "result": result})

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
    mission.save()
    return JsonResponse({"status": "rejected"})
