import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from comms.models import PendingCommand
from comms.serializers import MissionSerializer
from comms.executor import ShellExecutor

def _get_mission_or_404(pk):
    try:
        return PendingCommand.objects.get(pk=pk, is_cancelled=False)
    except PendingCommand.DoesNotExist:
        return None

@csrf_exempt
def handle_missions(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method must be GET"}, status=405)
    
    missions = PendingCommand.objects.exclude(is_cancelled=True)
    data = [MissionSerializer.serialize(m) for m in missions]
    return JsonResponse(data, safe=False)

@csrf_exempt
def handle_mission_approve(request, pk):
    if request.method != "POST":
        return JsonResponse({"error": "Method must be POST"}, status=405)
    
    mission = _get_mission_or_404(pk)
    if not mission:
        return JsonResponse({"error": "Mission not found"}, status=404)
        
    if mission.is_executed:
        return JsonResponse({"error": "Mission already executed"}, status=400)
    
    # Mark as approved
    mission.is_approved = True
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

    # Mark as executed
    mission.is_executed = True
    mission.save()

    return JsonResponse({"status": "approved", "result": result})

@csrf_exempt
def handle_mission_reject(request, pk):
    if request.method != "POST":
        return JsonResponse({"error": "Method must be POST"}, status=405)
    
    mission = _get_mission_or_404(pk)
    if not mission:
        return JsonResponse({"error": "Mission not found"}, status=404)
        
    if mission.is_executed:
        return JsonResponse({"error": "Mission already executed"}, status=400)
    
    mission.is_executed = True # Marking as "failed/handled"
    mission.save()
    return JsonResponse({"status": "rejected"})
