class MissionSerializer:
    @classmethod
    def serialize(cls, obj):
        """
        Manually serialize a PendingCommand object to match the frontend expectations.
        """
        metadata = obj.metadata or {}
        
        # Determine status
        status = "pending"
        if obj.is_approved:
            status = "approved"
        elif obj.is_executed:
            status = "failed"
            
        # Determine source
        source = "Manual WeChat Command"
        if "[MIJIA:" in obj.original_prompt:
            source = "Mijia Automation"

        return {
            "id": str(obj.id),
            "status": status,
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
    def _generate_timeline(cls, obj):
        # Generate a basic timeline based on current status
        events = [
            {
                "id": f"evt-1-{obj.id}",
                "time": obj.created_at.strftime("%H:%M"),
                "message": "任务已由 AI 决策引擎创建，等待系统分析。"
            }
        ]
        
        if obj.is_approved:
            events.append({
                "id": f"evt-2-{obj.id}",
                "time": obj.created_at.strftime("%H:%M"), # Simplification, could use auto_now field
                "message": "人工审核已通过，正在进入执行管线。"
            })
            
        if obj.is_executed:
            msg = "执行成功并已归档。" if obj.is_approved else "任务已被否决或执行失败。"
            events.append({
                "id": f"evt-3-{obj.id}",
                "time": obj.created_at.strftime("%H:%M"),
                "message": msg
            })
            
        return events[::-1] # Newest first
