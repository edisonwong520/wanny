from comms.models import Mission

class MissionSerializer:
    @classmethod
    def serialize(cls, obj: Mission):
        """
        Manually serialize a Mission object to match the frontend expectations.
        """
        metadata = obj.metadata or {}
        
        # Determine source
        source = "Manual WeChat Command"
        if "[MIJIA:" in obj.original_prompt:
            source = "Mijia Automation"
        
        # Mapping statuses for frontend compatibility if needed, 
        # though our StatusChoices match the frontend's original expectations.
        frontend_status = obj.status
        if obj.status in [Mission.StatusChoices.REJECTED, Mission.StatusChoices.CANCELLED]:
            frontend_status = "failed" # Frontend currently only has pending, approved, failed chips

        return {
            "id": str(obj.id),
            "status": frontend_status,
            "risk": metadata.get("risk", "medium"),
            "createdAt": obj.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "title": metadata.get("title", f"系统任务 #{obj.id}"),
            "source": source,
            "summary": metadata.get("summary", obj.original_prompt),
            "rawMessage": obj.original_prompt,
            "intent": metadata.get("intent", "执行系统底层指令"),
            "commandPreview": obj.shell_command,
            "plan": metadata.get("plan", ["分析指令安全提示", "等待人工审批", "执行 Shell 脚本"]),
            "context": metadata.get("context", []),
            "suggestedReply": metadata.get("suggested_reply", "指令已成功执行。"),
            "timeline": cls._generate_timeline(obj)
        }

    @classmethod
    def _generate_timeline(cls, obj: Mission):
        # Generate a basic timeline based on current status
        events = [
            {
                "id": f"evt-1-{obj.id}",
                "time": obj.created_at.strftime("%H:%M"),
                "message": "任务已由 AI 决策引擎创建，等待进入管线。"
            }
        ]
        
        if obj.status != Mission.StatusChoices.PENDING:
            msg = "流程已启动并流转为: " + obj.get_status_display()
            events.append({
                "id": f"evt-2-{obj.id}",
                "time": obj.updated_at.strftime("%H:%M"),
                "message": msg
            })
            
        return events[::-1] # Newest first
