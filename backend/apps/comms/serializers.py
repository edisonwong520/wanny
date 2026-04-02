from comms.models import Mission

class MissionSerializer:
    @classmethod
    def serialize(cls, obj: Mission):
        """
        Manually serialize a Mission object to match the frontend expectations.
        """
        metadata = obj.metadata or {}
        
        source = cls._get_source_label(obj, metadata)
        command_preview = metadata.get("command_preview") or cls._build_command_preview(obj)
        plan = metadata.get("plan") or cls._default_plan(obj)
        summary = metadata.get("summary") or cls._default_summary(obj)
        intent = metadata.get("intent") or cls._default_intent(obj)
        suggested_reply = metadata.get("suggested_reply") or cls._default_suggested_reply(obj)

        # Mapping statuses for frontend compatibility if needed, 
        # though our StatusChoices match the frontend's original expectations.
        frontend_status = obj.status
        if obj.status in [Mission.StatusChoices.REJECTED, Mission.StatusChoices.CANCELLED]:
            frontend_status = "failed" # Frontend currently only has pending, approved, failed chips

        return {
            "id": str(obj.id),
            "status": frontend_status,
            "sourceType": obj.source_type,
            "risk": metadata.get("risk", "medium"),
            "createdAt": obj.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "title": metadata.get("title", cls._default_title(obj)),
            "source": source,
            "summary": summary,
            "rawMessage": obj.original_prompt,
            "intent": intent,
            "commandPreview": command_preview,
            "plan": plan,
            "context": metadata.get("context", []),
            "suggestedReply": suggested_reply,
            "confirmMessage": metadata.get("confirm_message", ""),
            "resultMessage": cls._build_result_message(obj, metadata),
            "canApprove": obj.status == Mission.StatusChoices.PENDING and obj.source_type != Mission.SourceTypeChoices.DEVICE_CLARIFICATION,
            "canReject": obj.status == Mission.StatusChoices.PENDING,
            "timeline": cls._generate_timeline(obj)
        }

    @classmethod
    def _default_title(cls, obj: Mission) -> str:
        if obj.source_type == Mission.SourceTypeChoices.DEVICE_CONTROL:
            return "设备控制待确认"
        if obj.source_type == Mission.SourceTypeChoices.DEVICE_CLARIFICATION:
            return "设备澄清待处理"
        return f"系统任务 #{obj.id}"

    @classmethod
    def _default_summary(cls, obj: Mission) -> str:
        if obj.source_type == Mission.SourceTypeChoices.DEVICE_CONTROL:
            control_key = obj.control_key or "未知控制"
            value = cls._format_operation_value(obj.operation_value)
            return f"{obj.device_id or '未知设备'} / {control_key} -> {value}"
        if obj.source_type == Mission.SourceTypeChoices.DEVICE_CLARIFICATION:
            return "等待用户确定本次设备控制的目标设备。"
        return obj.original_prompt

    @classmethod
    def _default_intent(cls, obj: Mission) -> str:
        if obj.source_type == Mission.SourceTypeChoices.DEVICE_CONTROL:
            return "执行设备控制"
        if obj.source_type == Mission.SourceTypeChoices.DEVICE_CLARIFICATION:
            return "确定设备控制目标"
        return "执行系统底层指令"

    @classmethod
    def _default_plan(cls, obj: Mission) -> list[str]:
        if obj.source_type == Mission.SourceTypeChoices.DEVICE_CONTROL:
            return ["核对目标设备", "等待人工审批", "执行设备控制"]
        if obj.source_type == Mission.SourceTypeChoices.DEVICE_CLARIFICATION:
            return ["整理候选设备", "等待用户选择", "恢复设备控制任务"]
        return ["分析指令安全提示", "等待人工审批", "执行 Shell 脚本"]

    @classmethod
    def _default_suggested_reply(cls, obj: Mission) -> str:
        if obj.source_type == Mission.SourceTypeChoices.DEVICE_CONTROL:
            return "设备指令已执行完成。"
        if obj.source_type == Mission.SourceTypeChoices.DEVICE_CLARIFICATION:
            return "请先明确要操作的设备。"
        return "指令已成功执行。"

    @classmethod
    def _get_source_label(cls, obj: Mission, metadata: dict) -> str:
        if metadata.get("source_label"):
            return metadata["source_label"]
        if obj.source_type == Mission.SourceTypeChoices.DEVICE_CONTROL:
            return "Manual WeChat Device Command"
        if obj.source_type == Mission.SourceTypeChoices.DEVICE_CLARIFICATION:
            return "Manual WeChat Device Clarification"
        if "[MIJIA:" in obj.original_prompt:
            return "Mijia Automation"
        return "Manual WeChat Command"

    @classmethod
    def _build_command_preview(cls, obj: Mission) -> str:
        if obj.shell_command:
            return obj.shell_command
        if obj.source_type == Mission.SourceTypeChoices.DEVICE_CONTROL:
            value = cls._format_operation_value(obj.operation_value)
            action = obj.operation_action or "set_property"
            return (
                f"device={obj.device_id or 'unknown'} "
                f"control={obj.control_id or obj.control_key or 'unknown'} "
                f"action={action} value={value}"
            )
        if obj.source_type == Mission.SourceTypeChoices.DEVICE_CLARIFICATION:
            return ""
        return ""

    @classmethod
    def _format_operation_value(cls, value):
        if isinstance(value, dict) and "value" in value and len(value) == 1:
            return value["value"]
        return value

    @classmethod
    def _generate_timeline(cls, obj: Mission):
        # Generate a basic timeline based on current status
        metadata = obj.metadata or {}
        events = [
            {
                "id": f"evt-1-{obj.id}",
                "time": obj.created_at.strftime("%H:%M"),
                "message": cls._created_timeline_message(obj),
            }
        ]
        
        if obj.status != Mission.StatusChoices.PENDING:
            msg = cls._status_timeline_message(obj, metadata)
            events.append({
                "id": f"evt-2-{obj.id}",
                "time": obj.updated_at.strftime("%H:%M"),
                "message": msg
            })
            
        return events[::-1] # Newest first

    @classmethod
    def _created_timeline_message(cls, obj: Mission) -> str:
        if obj.source_type == Mission.SourceTypeChoices.DEVICE_CONTROL:
            return "设备控制任务已创建，等待审批后执行。"
        if obj.source_type == Mission.SourceTypeChoices.DEVICE_CLARIFICATION:
            return "设备候选已整理完成，等待用户进一步确认。"
        return "任务已由 AI 决策引擎创建，等待进入管线。"

    @classmethod
    def _status_timeline_message(cls, obj: Mission, metadata: dict) -> str:
        result_message = cls._build_result_message(obj, metadata)
        if obj.status == Mission.StatusChoices.APPROVED:
            return result_message or "任务已审批并执行完成。"
        if obj.status == Mission.StatusChoices.REJECTED:
            return result_message or "任务已被拒绝。"
        if obj.status == Mission.StatusChoices.FAILED:
            return result_message or "任务执行失败。"
        if obj.status == Mission.StatusChoices.CANCELLED:
            return result_message or "任务已作废。"
        return "流程已启动并流转为: " + obj.get_status_display()

    @classmethod
    def _build_result_message(cls, obj: Mission, metadata: dict) -> str:
        execution_result = metadata.get("execution_result") or {}
        if isinstance(execution_result, dict) and execution_result.get("message"):
            return execution_result["message"]
        if obj.status == Mission.StatusChoices.REJECTED:
            return metadata.get("review_message", "任务已被拒绝。")
        if obj.status == Mission.StatusChoices.CANCELLED:
            return metadata.get("review_message", "任务已作废。")
        return ""
