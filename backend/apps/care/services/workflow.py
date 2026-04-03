from __future__ import annotations

from datetime import datetime

from asgiref.sync import async_to_sync

from care.models import CareSuggestion
from care.services.learner import FeedbackLearner
from comms.device_command_service import DeviceCommandService
from comms.models import Mission
from memory.models import ProactiveLog


class CareWorkflowService:
    @classmethod
    def _action_target(cls, suggestion: CareSuggestion, key: str, fallback: str = "") -> str:
        action_spec = suggestion.action_spec or {}
        value = action_spec.get(key)
        if value not in (None, ""):
            return str(value)
        if key == "device_id" and suggestion.device:
            return suggestion.device.external_id
        if key == "control_id" and suggestion.control_target:
            return suggestion.control_target.external_id
        if key == "control_key" and suggestion.control_target:
            return suggestion.control_target.key
        return fallback

    @classmethod
    def create_mission_for_suggestion(cls, suggestion: CareSuggestion) -> Mission:
        if suggestion.mission_id:
            return suggestion.mission
        action_spec = suggestion.action_spec or {}
        mission = Mission.objects.create(
            account=suggestion.account,
            user_id=f"care:{suggestion.account.email}",
            status=Mission.StatusChoices.PENDING,
            original_prompt=suggestion.body,
            source_type=Mission.SourceTypeChoices.DEVICE_CONTROL,
            device_id=cls._action_target(suggestion, "device_id"),
            control_id=cls._action_target(suggestion, "control_id"),
            control_key=cls._action_target(suggestion, "control_key"),
            operation_action=str(action_spec.get("action") or ""),
            operation_value={"value": action_spec.get("value")} if "value" in action_spec else {},
            metadata={
                "title": suggestion.title,
                "summary": suggestion.body,
                "source_label": "Proactive Care Suggestion",
                "risk": "medium",
                "confirm_message": "这是主动关怀建议触发的设备操作，请确认后执行。",
                "care_suggestion_id": suggestion.id,
            },
        )
        suggestion.mission = mission
        suggestion.status = CareSuggestion.StatusChoices.APPROVED
        suggestion.feedback_collected_at = datetime.now()
        suggestion.user_feedback = {**(suggestion.user_feedback or {}), "action": "approve"}
        suggestion.save(update_fields=["mission", "status", "feedback_collected_at", "user_feedback", "updated_at"])
        cls._record_feedback(suggestion, "APPROVED")
        FeedbackLearner.apply_feedback(suggestion, action="approve")
        return mission

    @classmethod
    def execute_suggestion(cls, suggestion: CareSuggestion) -> dict:
        if suggestion.control_target is None and not suggestion.action_spec.get("control_id"):
            raise ValueError("This suggestion has no executable control target.")
        mission = cls.create_mission_for_suggestion(suggestion)
        payload = async_to_sync(DeviceCommandService.execute_device_operation)(
            suggestion.account,
            control_id=mission.control_id,
            operation_action=mission.operation_action,
            operation_value=mission.operation_value,
        )
        mission.metadata = {**(mission.metadata or {}), "execution_result": payload}
        if payload.get("success"):
            mission.status = Mission.StatusChoices.APPROVED
            suggestion.status = CareSuggestion.StatusChoices.EXECUTED
        else:
            mission.status = Mission.StatusChoices.FAILED
            suggestion.status = CareSuggestion.StatusChoices.FAILED
        mission.save(update_fields=["status", "metadata", "updated_at"])
        suggestion.feedback_collected_at = datetime.now()
        suggestion.user_feedback = {
            **(suggestion.user_feedback or {}),
            "executed": bool(payload.get("success")),
            "result": payload.get("message", ""),
        }
        suggestion.save(update_fields=["status", "feedback_collected_at", "user_feedback", "updated_at"])
        cls._record_feedback(
            suggestion,
            "APPROVED" if payload.get("success") else "DENIED",
        )
        FeedbackLearner.apply_feedback(suggestion, action="execute" if payload.get("success") else "failed")
        return payload

    @classmethod
    def reject_suggestion(cls, suggestion: CareSuggestion, reason: str = ""):
        suggestion.status = CareSuggestion.StatusChoices.REJECTED
        suggestion.feedback_collected_at = datetime.now()
        suggestion.user_feedback = {**(suggestion.user_feedback or {}), "action": "reject", "reason": reason}
        suggestion.save(update_fields=["status", "feedback_collected_at", "user_feedback", "updated_at"])
        cls._record_feedback(suggestion, "DENIED")
        FeedbackLearner.apply_feedback(suggestion, action="reject")

    @classmethod
    def ignore_suggestion(cls, suggestion: CareSuggestion, reason: str = ""):
        suggestion.status = CareSuggestion.StatusChoices.IGNORED
        suggestion.feedback_collected_at = datetime.now()
        suggestion.user_feedback = {**(suggestion.user_feedback or {}), "action": "ignore", "reason": reason}
        suggestion.save(update_fields=["status", "feedback_collected_at", "user_feedback", "updated_at"])
        cls._record_feedback(suggestion, "IGNORED")
        FeedbackLearner.apply_feedback(suggestion, action="ignore")

    @classmethod
    def _record_feedback(cls, suggestion: CareSuggestion, feedback: str):
        topic_key = FeedbackLearner.build_topic_key(suggestion=suggestion)
        ProactiveLog.objects.create(
            account=suggestion.account,
            message=suggestion.title,
            feedback=feedback,
            score=suggestion.priority,
            source=topic_key,
        )
