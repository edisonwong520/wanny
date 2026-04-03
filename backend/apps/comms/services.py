import asyncio
import re
import time
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from asgiref.sync import sync_to_async
from utils.logger import logger
from comms.models import Mission
from brain.models import HabitPolicy, ObservationCounter
from comms.ai import analyze_intent
from comms.command_router import route_command
from comms.device_command_service import DeviceCommandService
from comms.device_context_manager import DeviceContextManager
from comms.device_intent import (
    analyze_device_intent,
    detect_command_mode,
    strip_wakeup_prefix,
)
from comms.executor import ShellExecutor
from memory.services import MemoryService
from accounts.models import Account
from providers.models import PlatformAuth
from utils.telemetry import get_tracer


class WeChatService:
    """
    负责封装与 WeChat Bot 相关的业务逻辑：
    结合主动防御、大模型意图切分以及代理操作。
    """
    clarification_expiry = timedelta(minutes=10)
    pending_mission_recency_gap = timedelta(minutes=2)
    _background_tasks: set[asyncio.Task] = set()
    tracer = get_tracer(__name__)

    @classmethod
    async def get_account_by_wechat_id(cls, wechat_user_id: str) -> Account | None:
        """根据微信 OpenID 查找对应的系统账户"""
        try:
            auth = await sync_to_async(
                lambda: PlatformAuth.objects.filter(
                    Q(platform_name="wechat"),
                    Q(is_active=True),
                    Q(account__isnull=False),
                    Q(auth_payload__user_id=wechat_user_id)
                    | Q(auth_payload__userId=wechat_user_id),
                )
                .select_related("account")
                .first()
            )()
            return auth.account if auth else None
        except Exception as e:
            logger.error(f"[WeChat Service] 查找账户失败: {e}")
            return None

    @classmethod
    async def process_incoming_message(cls, message, bot):
        content, voice_transcript, has_voice = cls._extract_message_content(message)
        wechat_user_id = getattr(message, "user_id", "unknown_user")
        typing_started = False

        with cls.tracer.start_as_current_span("wechat.process_message") as span:
            span.set_attribute("wechat.user_id", wechat_user_id)
            span.set_attribute("wechat.has_voice", has_voice)

            if not content:
                if has_voice:
                    await bot.reply(
                        message,
                        "这条语音我没有识别清楚。您可以再说一次，或者直接发文字命令。",
                    )
                logger.debug(
                    f"[WeChat Service] 收到空消息，已忽略。user_id={wechat_user_id}"
                )
                return

            logger.info(
                f"[WeChat Service] 收到消息: user_id={wechat_user_id}, 内容='{content[:50]}'"
            )
            span.set_attribute("wechat.content_preview", content[:80])

            account = await cls.get_account_by_wechat_id(wechat_user_id)
            if not account:
                logger.warning(
                    f"[WeChat Service] ⚠️ 收到未分配账户的消息: wechat_user_id={wechat_user_id}。将以受限模式运行。"
                )
            else:
                span.set_attribute("account.email", account.email)

            if account:
                cls._schedule_background_job(
                    MemoryService.record_conversation(
                        account,
                        "user",
                        content,
                        platform_user_id=wechat_user_id,
                    ),
                    label=f"user-memory:{wechat_user_id}",
                )

            try:
                typing_started = await cls._send_typing(bot, wechat_user_id)

                memory_context = ""
                if account:
                    memory_context = await MemoryService.get_context_for_chat(
                        account, content
                    )

                mode = detect_command_mode(content)
                span.set_attribute("wechat.mode", mode)
                normalized_content = strip_wakeup_prefix(content) if mode == "command" else content

                if has_voice and cls._is_low_signal_voice_text(normalized_content):
                    await cls._reply_and_record(
                        bot,
                        message,
                        "这条语音的识别结果太短了，我怕误操作。请直接说完整一点，或者发文字命令。",
                        account=account,
                        wechat_user_id=wechat_user_id,
                    )
                    return

                if account:
                    clarification_handled = await cls._maybe_handle_device_clarification(
                        account=account,
                        wechat_user_id=wechat_user_id,
                        message=message,
                        bot=bot,
                        content=content,
                        normalized_content=normalized_content,
                        voice_transcript=voice_transcript,
                    )
                    if clarification_handled:
                        return

                router_result = None
                if account:
                    router_result = await route_command(
                        normalized_content,
                        account=account,
                        command_mode=(mode == "command"),
                    )
                    span.set_attribute("device.route", str(router_result.get("route") or ""))
                    span.set_attribute("device.route_reason", str(router_result.get("reason") or ""))
                    route_signals = router_result.get("signals") or {}
                    span.set_attribute("device.route_english_signals", int(route_signals.get("english") or 0))
                    span.set_attribute("device.route_colloquial_signals", int(route_signals.get("colloquial") or 0))
                    span.set_attribute("device.route_multi_intent_signals", int(route_signals.get("multi_intent") or 0))
                    span.set_attribute("device.route_query_signals", int(route_signals.get("query") or 0))
                    span.set_attribute("device.route_length", int(route_signals.get("length") or 0))
                    span.set_attribute("device.route_has_signal", bool(route_signals.get("has_device_signal")))

                if account and router_result and router_result.get("route") != "skip_device":
                    device_intent_started_at = time.perf_counter()
                    device_intent = await analyze_device_intent(
                        normalized_content,
                        account,
                        memory_context=memory_context,
                        command_mode=(mode == "command"),
                        allow_normalize=router_result.get("route") in {"try_heuristic_then_normalize", "needs_normalize"},
                    )
                    logger.info(
                        f"[Device Intent Result] {device_intent.get('type')} (elapsed={time.perf_counter() - device_intent_started_at:.2f}s)"
                    )
                    span.set_attribute("device.intent_type", str(device_intent.get("type") or ""))
                    span.set_attribute("device.path_taken", "device_intent")

                    if device_intent.get("type") in {"DEVICE_CONTROL", "DEVICE_QUERY"}:
                        handled = await cls.handle_device_intent(
                            intent=device_intent,
                            message=message,
                            bot=bot,
                            account=account,
                            wechat_user_id=wechat_user_id,
                            raw_content=content,
                            normalized_content=normalized_content,
                            voice_transcript=voice_transcript,
                        )
                        if handled:
                            span.set_attribute("device.handled", True)
                            return
                    span.set_attribute("device.handled", False)
                elif router_result:
                    span.set_attribute("device.path_taken", "skip_device")

                intent_started_at = time.perf_counter()
                intent_data = await analyze_intent(
                    normalized_content if mode == "command" else content,
                    memory_context=memory_context,
                )
                span.set_attribute("device.general_intent_fallback", True)
                intent_type = intent_data.get("type")
                if intent_type == "simple":
                    raw_response = str(intent_data.get("raw_response") or "").strip()
                    logger.warning(
                        "[WeChat Service] 通用意图解析未返回合规结构，已回退为聊天兜底。"
                    )
                    intent_data = (
                        {
                            "type": "CHAT",
                            "response": raw_response,
                        }
                        if raw_response and mode != "command"
                        else {
                            "type": "CHAT",
                            "response": "我刚才没有理解清楚，您可以换种说法再发一次。",
                        }
                    )
                    intent_type = intent_data["type"]
                logger.info(f"[Intent Result] {intent_type} (elapsed={time.perf_counter() - intent_started_at:.2f}s)")
                span.set_attribute("intent.type", str(intent_type or ""))

                if mode == "command" and (intent_type == "CHAT" or not intent_type):
                    reply_text = "这是命令模式，但我还没理解您希望我执行什么操作。"
                    await cls._reply_and_record(
                        bot,
                        message,
                        reply_text,
                        account=account,
                        wechat_user_id=wechat_user_id,
                    )
                    return

                if intent_type == "CHAT" or not intent_type:
                    reply_text = intent_data.get(
                        "response", "系统分析您的指令时遇到了一点困惑。"
                    )
                    await cls._reply_and_record(
                        bot,
                        message,
                        reply_text,
                        account=account,
                        wechat_user_id=wechat_user_id,
                    )
                    return

                if intent_type == "COMPLEX_SHELL":
                    await cls._reply_progress(bot, message, "收到，稍等，我先整理一下操作计划。")
                    shell_cmd = (
                        intent_data.get("shell_prompt")
                        or intent_data.get("command")
                        or normalized_content
                        or content
                    )
                    confirm_txt = intent_data.get(
                        "confirm_text", "准备进行 Shell 操作，请指示："
                    )
                    mission_metadata = cls._build_shell_mission_metadata(
                        raw_content=content,
                        shell_command=shell_cmd,
                        incoming_metadata=intent_data.get("metadata", {}),
                        confirm_text=confirm_txt,
                    )
                    new_mission = await sync_to_async(cls.create_shell_mission)(
                        account=account,
                        wechat_user_id=wechat_user_id,
                        raw_content=content,
                        shell_command=shell_cmd,
                        metadata=mission_metadata,
                    )
                    logger.info(
                        f"[WeChat Service] 挂起一条待审批任务 (ID: {new_mission.id})"
                    )
                    span.set_attribute("mission.id", new_mission.id)
                    span.set_attribute("mission.source_type", new_mission.source_type)
                    alert_text = mission_metadata.get("confirm_message") or cls._build_shell_confirm_message(
                        confirm_text=confirm_txt,
                        shell_command=shell_cmd,
                    )
                    await cls._reply_and_record(
                        bot,
                        message,
                        alert_text,
                        account=account,
                        wechat_user_id=wechat_user_id,
                    )
                    return

                pending_missions = await cls._find_pending_missions(account, wechat_user_id)
                mission = cls._select_pending_mission(pending_missions, intent_type=intent_type)

                logger.debug(
                    f"[WeChat Service] 查找任务: wechat_user_id={wechat_user_id}, 结果={'找到 ID=' + str(mission.id) if mission else '无'}"
                )
                if mission:
                    span.set_attribute("mission.id", mission.id)
                    span.set_attribute("mission.source_type", mission.source_type)

                if len(pending_missions) > 1 and mission is None:
                    reply_txt = "我这边同时有多条待确认任务。为了避免误执行，请您重新说清楚要确认哪一条。"
                    await cls._reply_and_record(
                        bot,
                        message,
                        reply_txt,
                        account=account,
                        wechat_user_id=wechat_user_id,
                    )
                    return

                if mission is None:
                    base_filter = (
                        Q(account=account) | Q(user_id="BROADCAST")
                        if account
                        else Q(user_id=wechat_user_id)
                    )
                    recent_any = await sync_to_async(
                        lambda: Mission.objects.filter(base_filter)
                        .order_by("-created_at")
                        .first()
                    )()

                    if recent_any and recent_any.status != Mission.StatusChoices.PENDING:
                        reply_txt = f"刚才的任务 (ID: {recent_any.id}) 已经处理过了，当前状态为【{recent_any.get_status_display()}】。"
                    else:
                        reply_txt = (
                            intent_data.get("response")
                            or "目前并没有找到需要您授权操作的任务。"
                        )

                    await cls._reply_and_record(
                        bot,
                        message,
                        reply_txt,
                        account=account,
                        wechat_user_id=wechat_user_id,
                    )
                    return

                if not mission.account_id and account:
                    mission.account = account
                    mission.user_id = wechat_user_id
                    await sync_to_async(mission.save)()

                if intent_type == "DENY":
                    mission.status = Mission.StatusChoices.REJECTED
                    await sync_to_async(mission.save)()

                    reply_txt = intent_data.get("response", "好的，已将此任务作废。")
                    await cls._reply_and_record(
                        bot,
                        message,
                        reply_txt,
                        account=account,
                        wechat_user_id=wechat_user_id,
                    )
                    await cls._reset_counter_if_mijia(mission.original_prompt)
                    return

                if intent_type in ["CONFIRM", "PERMANENT_ALLOW"]:
                    msg_ack = "🫡 正在全力执行，请稍候..."
                    await cls._reply_and_record(
                        bot,
                        message,
                        msg_ack,
                        account=account,
                        wechat_user_id=wechat_user_id,
                    )

                    mission.status = Mission.StatusChoices.APPROVED
                    await sync_to_async(mission.save)()

                    try:
                        if mission.source_type == Mission.SourceTypeChoices.DEVICE_CONTROL:
                            result = await DeviceCommandService.execute_device_operation(
                                account,
                                control_id=mission.control_id,
                                operation_action=mission.operation_action,
                                operation_value=mission.operation_value,
                            )
                            result_msg = cls._build_device_result_reply(
                                intent=(mission.metadata or {}).get("intent_json", {}),
                                result=result,
                            )
                            if result.get("success"):
                                cls._schedule_background_job(
                                    sync_to_async(cls._record_device_context_from_mission)(
                                        mission,
                                        wechat_user_id=wechat_user_id,
                                        content=content,
                                        normalized_content=normalized_content,
                                        voice_transcript=voice_transcript,
                                        execution_result=result,
                                    ),
                                    label=f"device-context-mission:{mission.id}",
                                )
                            else:
                                mission.status = Mission.StatusChoices.FAILED
                                mission.metadata = {
                                    **(mission.metadata or {}),
                                    "execution_result": result,
                                }
                                await sync_to_async(mission.save)()
                        elif mission.shell_command:
                            result_msg = await ShellExecutor.execute_yolo(
                                mission.shell_command
                            )
                        else:
                            result_msg = "✅ 内部代理控制成功完成！(Mijia Hook)"
                    except Exception as e:
                        result_msg = f"❌ 执行异常: {str(e)}"
                        mission.status = Mission.StatusChoices.FAILED
                        await sync_to_async(mission.save)()

                    if intent_type == "PERMANENT_ALLOW":
                        await cls._elevate_policy_if_mijia(mission.original_prompt)
                        result_msg += "\n\n💡 已将您针对此情景下的偏好永久化存储，以后将默认自动帮您代劳而不必费心。"
                    elif intent_type == "CONFIRM":
                        await cls._increment_counter_if_mijia(mission.original_prompt)

                    await cls._reply_and_record(
                        bot,
                        message,
                        result_msg,
                        account=account,
                        wechat_user_id=wechat_user_id,
                    )
                    logger.info(f"[WeChat Target] 任务彻底完成 (ID: {mission.id})")
                    return

            except Exception as e:
                span.set_attribute("wechat.error", str(e))
                logger.error(f"[WeChat Target] 中枢流转发生阻断式故障: {str(e)}")
                try:
                    await bot.reply(message, f"❌ 内部调度异常: {str(e)}")
                except:
                    pass
            finally:
                if typing_started:
                    await cls._stop_typing(bot, wechat_user_id)

    @classmethod
    def _extract_message_content(cls, message) -> tuple[str, str, bool]:
        content = (getattr(message, "text", "") or "").strip()
        voice_transcript = ""
        has_voice = False
        voices = getattr(message, "voices", None) or []
        if voices:
            has_voice = True
            first_voice = voices[0]
            voice_transcript = (getattr(first_voice, "text", "") or "").strip()
            if voice_transcript:
                content = voice_transcript
        return content.strip(), voice_transcript, has_voice

    @classmethod
    async def _reply_and_record(cls, bot, message, reply_text: str, *, account, wechat_user_id: str):
        await bot.reply(message, reply_text)
        if account:
            cls._schedule_background_job(
                MemoryService.record_conversation(
                    account,
                    "assistant",
                    reply_text,
                    platform_user_id=wechat_user_id,
                ),
                label=f"assistant-memory:{wechat_user_id}",
            )

    @classmethod
    def _schedule_background_job(cls, coroutine, *, label: str):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning(f"[WeChat Service] 无法调度后台任务: {label}，当前没有事件循环。")
            return None

        task = loop.create_task(coroutine)
        cls._background_tasks.add(task)

        def _on_done(done_task: asyncio.Task):
            cls._background_tasks.discard(done_task)
            try:
                done_task.result()
            except Exception as error:
                logger.error(f"[WeChat Service] 后台任务失败 ({label}): {error}")

        task.add_done_callback(_on_done)
        return task

    @classmethod
    async def _reply_progress(cls, bot, message, reply_text: str):
        await bot.reply(message, reply_text)

    @classmethod
    async def _send_typing(cls, bot, wechat_user_id: str) -> bool:
        send_typing = getattr(bot, "send_typing", None)
        if send_typing is None:
            return False
        try:
            await send_typing(wechat_user_id)
            return True
        except Exception as error:
            logger.warning(f"[WeChat Service] send_typing 失败: user_id={wechat_user_id}, error={error}")
            return False

    @classmethod
    async def _stop_typing(cls, bot, wechat_user_id: str):
        stop_typing = getattr(bot, "stop_typing", None)
        if stop_typing is None:
            return
        try:
            await stop_typing(wechat_user_id)
        except Exception as error:
            logger.warning(f"[WeChat Service] stop_typing 失败: user_id={wechat_user_id}, error={error}")

    @classmethod
    async def _find_pending_missions(cls, account, wechat_user_id: str) -> list[Mission]:
        mission_filter = Q(status=Mission.StatusChoices.PENDING)
        if account:
            mission_filter &= (Q(account=account) | Q(user_id="BROADCAST"))
        else:
            mission_filter &= Q(user_id=wechat_user_id)
        return await sync_to_async(list)(
            Mission.objects.filter(mission_filter)
            .select_related("account")
            .order_by("-created_at")[:3]
        )

    @classmethod
    def _select_pending_mission(cls, pending_missions: list[Mission], *, intent_type: str) -> Mission | None:
        if not pending_missions:
            return None
        if len(pending_missions) == 1:
            return pending_missions[0]

        sorted_missions = sorted(
            pending_missions,
            key=lambda item: item.created_at or timezone.now(),
            reverse=True,
        )
        non_clarification = [
            item for item in sorted_missions
            if item.source_type != Mission.SourceTypeChoices.DEVICE_CLARIFICATION
        ]
        if len(non_clarification) == 1:
            return non_clarification[0]

        same_type = {item.source_type for item in sorted_missions}
        if len(same_type) == 1:
            return sorted_missions[0]

        latest = sorted_missions[0]
        second = sorted_missions[1]
        latest_at = latest.created_at or timezone.now()
        second_at = second.created_at or timezone.now()
        if latest_at - second_at > cls.pending_mission_recency_gap:
            return latest

        if intent_type in {"CONFIRM", "PERMANENT_ALLOW", "DENY"}:
            device_controls = [
                item for item in non_clarification
                if item.source_type == Mission.SourceTypeChoices.DEVICE_CONTROL
            ]
            shell_missions = [
                item for item in non_clarification
                if item.source_type == Mission.SourceTypeChoices.SHELL
            ]
            if len(device_controls) == 1 and not shell_missions:
                return device_controls[0]
            if len(shell_missions) == 1 and not device_controls:
                return shell_missions[0]

        return None

    @classmethod
    async def handle_device_intent(
        cls,
        *,
        intent: dict,
        message,
        bot,
        account,
        wechat_user_id: str,
        raw_content: str,
        normalized_content: str,
        voice_transcript: str,
    ) -> bool:
        with cls.tracer.start_as_current_span("wechat.handle_device_intent") as span:
            intent_started_at = time.perf_counter()
            span.set_attribute("device.intent_type", str(intent.get("type") or ""))
            span.set_attribute("device.room", str(intent.get("room") or ""))
            span.set_attribute("device.name", str(intent.get("device") or ""))
            span.set_attribute("device.control_key", str(intent.get("control_key") or ""))

            resolved = await DeviceCommandService.resolve_device_target(account, intent)
            control = resolved.get("matched_control")
            device = resolved.get("matched_device")
            if control is None or device is None:
                span.set_attribute("device.resolved", False)
                alternatives = resolved.get("alternatives") or []
                if alternatives:
                    await sync_to_async(cls.create_device_clarification_mission)(
                        account=account,
                        wechat_user_id=wechat_user_id,
                        raw_content=raw_content,
                        normalized_content=normalized_content,
                        voice_transcript=voice_transcript,
                        intent=intent,
                        resolved=resolved,
                    )
                    reply_text = cls._build_clarification_prompt(alternatives)
                    reply_text = cls._prepend_voice_transcript_confirmation(
                        reply_text,
                        voice_transcript=voice_transcript,
                    )
                else:
                    reply_text = intent.get("error_hint") or "我没有找到对应的设备或控制项。"
                await cls._reply_and_record(
                    bot,
                    message,
                    reply_text,
                    account=account,
                    wechat_user_id=wechat_user_id,
                )
                return True

            span.set_attribute("device.resolved", True)
            span.set_attribute("device.external_id", device.external_id)
            span.set_attribute("device.control_label", control.label)

            if intent.get("type") == "DEVICE_QUERY":
                await cls._reply_progress(bot, message, "收到，稍等，我帮您查一下设备状态。")
                result = await DeviceCommandService.execute_device_query(
                    resolved,
                    account=account,
                )
                span.set_attribute("device.query.success", bool(result.get("success")))
                logger.info(
                    f"[Device Query Chain] 完成: room={intent.get('room') or '-'}, device={device.name}, control={control.label}, elapsed={time.perf_counter() - intent_started_at:.2f}s"
                )
                await cls._reply_and_record(
                    bot,
                    message,
                    result.get("message", "查询完成。"),
                    account=account,
                    wechat_user_id=wechat_user_id,
                )
                return True

            auth = await DeviceCommandService.check_authorization(
                account,
                resolved,
                command_mode=(detect_command_mode(raw_content) == "command"),
            )
            span.set_attribute("device.auth.allowed", bool(auth.get("allowed")))
            span.set_attribute("device.auth.need_confirm", bool(auth.get("need_confirm")))
            span.set_attribute("device.auth.policy", str(auth.get("policy") or ""))
            if not auth.get("allowed"):
                await cls._reply_and_record(
                    bot,
                    message,
                    "这条设备指令当前不允许直接执行。",
                    account=account,
                    wechat_user_id=wechat_user_id,
                )
                return True

            if auth.get("need_confirm") or resolved.get("ambiguous"):
                mission = await sync_to_async(cls.create_device_mission)(
                    account=account,
                    wechat_user_id=wechat_user_id,
                    raw_content=raw_content,
                    normalized_content=normalized_content,
                    voice_transcript=voice_transcript,
                    intent=intent,
                    resolved=resolved,
                )
                span.set_attribute("mission.id", mission.id)
                span.set_attribute("mission.source_type", mission.source_type)
                reply_text = (
                    (mission.metadata or {}).get("confirm_message")
                    or cls._build_device_confirm_message(device.name, control.label, intent.get("value"))
                )
                reply_text = cls._prepend_voice_transcript_confirmation(
                    reply_text,
                    voice_transcript=voice_transcript,
                )
                await cls._reply_and_record(
                    bot,
                    message,
                    reply_text,
                    account=account,
                    wechat_user_id=wechat_user_id,
                )
                return True

            await cls._reply_progress(bot, message, "收到，稍等，我正在处理设备操作。")
            result = await DeviceCommandService.execute_device_operation(
                account,
                control_id=control.external_id,
                operation_action=str(intent.get("action") or ""),
                operation_value=intent.get("value"),
            )
            span.set_attribute("device.control.success", bool(result.get("success")))
            span.set_attribute("device.control.error", str(result.get("error") or ""))
            logger.info(
                f"[Device Control Chain] 完成: room={intent.get('room') or '-'}, device={device.name}, control={control.label}, elapsed={time.perf_counter() - intent_started_at:.2f}s"
            )
            if result.get("success"):
                cls._schedule_background_job(
                    sync_to_async(DeviceContextManager.record_operation)(
                        account=account,
                        platform_user_id=wechat_user_id,
                        device=device,
                        control_id=control.external_id,
                        control_key=control.key,
                        operation_type=str(intent.get("action") or "set_property"),
                        value=intent.get("value"),
                        raw_user_msg=raw_content,
                        normalized_msg=normalized_content,
                        voice_transcript=voice_transcript,
                        intent_json=intent,
                        resolver_result=cls._serialize_resolved_target(resolved),
                        execution_result=result,
                    ),
                    label=f"device-context-direct:{wechat_user_id}",
                )
            await cls._reply_and_record(
                bot,
                message,
                cls._build_device_result_reply(intent=intent, result=result),
                account=account,
                wechat_user_id=wechat_user_id,
            )
            return True

    @classmethod
    def create_device_mission(
        cls,
        *,
        account,
        wechat_user_id: str,
        raw_content: str,
        normalized_content: str,
        voice_transcript: str,
        intent: dict,
        resolved: dict,
    ) -> Mission:
        control = resolved["matched_control"]
        device = resolved["matched_device"]
        metadata = {
            "intent_type": intent.get("type"),
            "provider": control.source_type,
            "device_external_id": device.external_id,
            "control_external_id": control.external_id,
            "control_key": control.key,
            "action": intent.get("action"),
            "value": intent.get("value"),
            "unit": intent.get("unit"),
            "resolved_from_context": resolved.get("resolved_from_context", False),
            "alternatives_snapshot": resolved.get("alternatives", []),
            "raw_user_msg": raw_content,
            "normalized_msg": normalized_content,
            "voice_transcript": voice_transcript,
            "intent_json": intent,
            "resolver_result": cls._serialize_resolved_target(resolved),
        }
        metadata = {
            **metadata,
            **cls._build_device_mission_metadata(
                device_name=device.name,
                control_label=control.label,
                operation_value=intent.get("value"),
                source_type=Mission.SourceTypeChoices.DEVICE_CONTROL,
            ),
        }
        mission, created = Mission.objects.get_or_create(
            account=account,
            user_id=wechat_user_id,
            source_type=Mission.SourceTypeChoices.DEVICE_CONTROL,
            status=Mission.StatusChoices.PENDING,
            original_prompt=raw_content,
            defaults={
                "device_id": device.external_id,
                "control_id": control.external_id,
                "control_key": control.key,
                "operation_action": str(intent.get("action") or ""),
                "operation_value": {"value": intent.get("value")},
                "metadata": metadata,
            },
        )
        if not created:
            mission.device_id = device.external_id
            mission.control_id = control.external_id
            mission.control_key = control.key
            mission.operation_action = str(intent.get("action") or "")
            mission.operation_value = {"value": intent.get("value")}
            mission.metadata = metadata
            mission.save()
        return mission

    @classmethod
    def create_shell_mission(
        cls,
        *,
        account,
        wechat_user_id: str,
        raw_content: str,
        shell_command: str,
        metadata: dict | None = None,
    ) -> Mission:
        mission, created = Mission.objects.get_or_create(
            account=account,
            user_id=wechat_user_id,
            source_type=Mission.SourceTypeChoices.SHELL,
            status=Mission.StatusChoices.PENDING,
            original_prompt=raw_content,
            defaults={
                "shell_command": shell_command,
                "metadata": metadata or {},
            },
        )
        if not created:
            mission.shell_command = shell_command
            mission.metadata = metadata or {}
            mission.save()
        return mission

    @classmethod
    def create_device_clarification_mission(
        cls,
        *,
        account,
        wechat_user_id: str,
        raw_content: str,
        normalized_content: str,
        voice_transcript: str,
        intent: dict,
        resolved: dict,
    ) -> Mission:
        metadata = {
            "intent_type": intent.get("type"),
            "raw_user_msg": raw_content,
            "normalized_msg": normalized_content,
            "voice_transcript": voice_transcript,
            "intent_json": intent,
            "resolver_result": cls._serialize_resolved_target(resolved),
            "alternatives_snapshot": resolved.get("alternatives", []),
        }
        metadata = {
            **metadata,
            **cls._build_clarification_mission_metadata(resolved.get("alternatives", [])),
        }
        mission, created = Mission.objects.get_or_create(
            account=account,
            user_id=wechat_user_id,
            source_type=Mission.SourceTypeChoices.DEVICE_CLARIFICATION,
            status=Mission.StatusChoices.PENDING,
            original_prompt=raw_content,
            defaults={
                "control_key": str(intent.get("control_key") or ""),
                "operation_action": str(intent.get("action") or ""),
                "operation_value": {"value": intent.get("value")},
                "metadata": metadata,
            },
        )
        if not created:
            mission.control_key = str(intent.get("control_key") or "")
            mission.operation_action = str(intent.get("action") or "")
            mission.operation_value = {"value": intent.get("value")}
            mission.metadata = metadata
            mission.save()
        return mission

    @classmethod
    async def _maybe_handle_device_clarification(
        cls,
        *,
        account,
        wechat_user_id: str,
        message,
        bot,
        content: str,
        normalized_content: str,
        voice_transcript: str,
    ) -> bool:
        mission = await cls._find_pending_clarification_mission(account, wechat_user_id)
        if mission is None:
            return False
        if cls._is_clarification_cancel_reply(normalized_content):
            mission.status = Mission.StatusChoices.REJECTED
            mission.metadata = {
                **(mission.metadata or {}),
                "clarification_reply": normalized_content,
                "clarification_cancelled": True,
            }
            await sync_to_async(mission.save)()
            await cls._reply_and_record(
                bot,
                message,
                "好的，这次设备选择我先取消了。您可以直接重新说更具体一点，比如“客厅主灯”或“卧室主灯”。",
                account=account,
                wechat_user_id=wechat_user_id,
            )
            return True
        resolved = await DeviceCommandService.resolve_clarification_choice(account, mission, normalized_content)
        if resolved is None:
            await cls._reply_and_record(
                bot,
                message,
                "我还是没确定您指的是哪一个。您可以回复编号、房间名，或者直接说“取消”。",
                account=account,
                wechat_user_id=wechat_user_id,
            )
            return True

        auth = await DeviceCommandService.check_authorization(account, resolved, command_mode=True)
        mission.status = Mission.StatusChoices.APPROVED
        mission.metadata = {
            **(mission.metadata or {}),
            "clarification_reply": normalized_content,
            "selected_resolver_result": cls._serialize_resolved_target(resolved),
        }
        await sync_to_async(mission.save)()

        control = resolved["matched_control"]
        device = resolved["matched_device"]
        intent_json = (mission.metadata or {}).get("intent_json", {})
        if auth.get("need_confirm"):
            await sync_to_async(cls.create_device_mission)(
                account=account,
                wechat_user_id=wechat_user_id,
                raw_content=mission.original_prompt,
                normalized_content=(mission.metadata or {}).get("normalized_msg", mission.original_prompt),
                voice_transcript=(mission.metadata or {}).get("voice_transcript", voice_transcript),
                intent={
                    **intent_json,
                    "action": mission.operation_action,
                    "control_key": mission.control_key or intent_json.get("control_key"),
                    "value": (mission.operation_value or {}).get("value"),
                },
                resolved=resolved,
            )
            reply_text = (
                f"收到，目标已确定为 {device.name} / {control.label}。"
                f" 请确认是否执行 -> {(mission.operation_value or {}).get('value')}。回复“好的”即可执行。"
            )
            await cls._reply_and_record(
                bot,
                message,
                reply_text,
                account=account,
                wechat_user_id=wechat_user_id,
            )
            return True

        result = await DeviceCommandService.execute_device_operation(
            account,
            control_id=control.external_id,
            operation_action=mission.operation_action,
            operation_value=mission.operation_value,
        )
        if result.get("success"):
            cls._schedule_background_job(
                sync_to_async(DeviceContextManager.record_operation)(
                    account=account,
                    platform_user_id=wechat_user_id,
                    device=device,
                    control_id=control.external_id,
                    control_key=control.key,
                    operation_type=mission.operation_action or "set_property",
                    value=(mission.operation_value or {}).get("value"),
                    raw_user_msg=mission.original_prompt,
                    normalized_msg=normalized_content,
                    voice_transcript=voice_transcript,
                    intent_json=intent_json,
                    resolver_result=cls._serialize_resolved_target(resolved),
                    execution_result=result,
                ),
                label=f"device-context-clarification:{mission.id}",
            )
        await cls._reply_and_record(
            bot,
            message,
            cls._build_device_result_reply(intent=intent_json, result=result),
            account=account,
            wechat_user_id=wechat_user_id,
        )
        return True

    @classmethod
    async def _find_pending_clarification_mission(cls, account, wechat_user_id: str) -> Mission | None:
        if not account:
            return None
        mission = await sync_to_async(
            lambda: Mission.objects.filter(
                status=Mission.StatusChoices.PENDING,
                source_type=Mission.SourceTypeChoices.DEVICE_CLARIFICATION,
            )
            .filter(Q(account=account) | Q(user_id=wechat_user_id))
            .order_by("-created_at")
            .first()
        )()
        if mission and cls._is_expired_clarification_mission(mission):
            mission.status = Mission.StatusChoices.CANCELLED
            await sync_to_async(mission.save)()
            return None
        return mission

    @classmethod
    def _build_clarification_prompt(cls, alternatives: list[dict]) -> str:
        lines = ["我还不能唯一确定要操作哪个设备，请直接回复编号或设备名："]
        for index, item in enumerate(alternatives[:5], start=1):
            room = item.get("room") or "未分组"
            device = item.get("device") or "未知设备"
            control = item.get("control") or "默认控制"
            lines.append(f"{index}. {room} / {device} / {control}")
        return "\n".join(lines)

    @classmethod
    def _build_shell_confirm_message(cls, *, confirm_text: str, shell_command: str) -> str:
        return (
            f"⚠️ 注意 \n\n{confirm_text}\n\n预期底层操作：\n{shell_command[:100]}...\n\n"
            "(请回复同意/执行/以后直接弄 等确认指令)"
        )

    @classmethod
    def _build_device_confirm_message(cls, device_name: str, control_label: str, value) -> str:
        return f"请确认是否执行：{device_name} / {control_label} -> {value}。回复“好的”即可执行。"

    @classmethod
    def _prepend_voice_transcript_confirmation(cls, reply_text: str, *, voice_transcript: str) -> str:
        transcript = (voice_transcript or "").strip()
        if not transcript:
            return reply_text
        return f"我听到的是：\"{transcript}\"。\n\n{reply_text}"

    @classmethod
    def _build_device_result_reply(cls, *, intent: dict | None, result: dict) -> str:
        intent = intent or {}
        if result.get("success"):
            return intent.get("suggested_reply") or result.get("message", "设备操作已完成。")

        base_message = result.get("message") or "设备操作失败，请稍后重试。"
        suggestion = result.get("suggestion")
        if suggestion:
            return f"{base_message}\n\n可选方案：{suggestion}"
        return base_message

    @classmethod
    def _build_shell_mission_metadata(
        cls,
        *,
        raw_content: str,
        shell_command: str,
        incoming_metadata: dict | None,
        confirm_text: str,
    ) -> dict:
        shell_command = str(shell_command or "").strip() or raw_content
        metadata = dict(incoming_metadata or {})
        metadata.setdefault("title", "Shell 指令待审批")
        metadata.setdefault("summary", raw_content)
        metadata.setdefault("intent", "执行 Shell 指令")
        metadata.setdefault("suggested_reply", "Shell 指令已完成。")
        metadata.setdefault("source_label", "Manual WeChat Command")
        metadata["confirm_message"] = cls._build_shell_confirm_message(
            confirm_text=confirm_text,
            shell_command=shell_command,
        )
        metadata["command_preview"] = shell_command[:100]
        return metadata

    @classmethod
    def _build_device_mission_metadata(
        cls,
        *,
        device_name: str,
        control_label: str,
        operation_value,
        source_type: str,
    ) -> dict:
        title = "设备控制待确认" if source_type == Mission.SourceTypeChoices.DEVICE_CONTROL else "设备澄清待处理"
        summary = f"{device_name} / {control_label} -> {operation_value}"
        return {
            "title": title,
            "summary": summary,
            "intent": f"控制设备 {device_name}",
            "suggested_reply": f"{device_name} 的 {control_label} 已处理。",
            "confirm_message": cls._build_device_confirm_message(device_name, control_label, operation_value),
            "source_label": "Manual WeChat Device Command",
            "command_preview": f"{device_name} / {control_label} -> {operation_value}",
            "plan": ["核对目标设备", "等待人工审批", "执行设备控制"],
        }

    @classmethod
    def _build_clarification_mission_metadata(cls, alternatives: list[dict]) -> dict:
        preview = " / ".join(
            f"{item.get('room') or '未分组'}:{item.get('device') or '未知设备'}"
            for item in alternatives[:3]
        )
        return {
            "title": "设备澄清待处理",
            "summary": preview or "等待用户确定设备目标",
            "intent": "确定本次设备控制的目标设备",
            "suggested_reply": "设备目标已确定。",
            "confirm_message": cls._build_clarification_prompt(alternatives),
            "source_label": "Manual WeChat Device Clarification",
            "plan": ["整理候选设备", "等待用户选择", "恢复设备控制任务"],
        }

    @classmethod
    def _is_clarification_cancel_reply(cls, content: str) -> bool:
        normalized = (content or "").strip()
        deny_tokens = (
            "取消",
            "算了",
            "不用了",
            "都不是",
            "不是这个",
            "不是这两个",
            "先别",
        )
        return any(token in normalized for token in deny_tokens)

    @classmethod
    def _is_low_signal_voice_text(cls, content: str) -> bool:
        normalized = (content or "").strip()
        if not normalized:
            return True
        low_signal_tokens = {
            "嗯",
            "嗯嗯",
            "啊",
            "哦",
            "额",
            "呃",
            "好",
            "好的",
        }
        return normalized in low_signal_tokens or len(normalized) <= 1

    @classmethod
    def _is_expired_clarification_mission(cls, mission: Mission) -> bool:
        if mission.source_type != Mission.SourceTypeChoices.DEVICE_CLARIFICATION:
            return False
        created_at = getattr(mission, "created_at", None)
        if created_at is None:
            return False
        return timezone.now() - created_at > cls.clarification_expiry

    @classmethod
    def _serialize_resolved_target(cls, resolved: dict) -> dict:
        device = resolved.get("matched_device")
        control = resolved.get("matched_control")
        return {
            "confidence": resolved.get("confidence"),
            "ambiguous": resolved.get("ambiguous"),
            "resolved_from_context": resolved.get("resolved_from_context", False),
            "alternatives": resolved.get("alternatives", []),
            "device_id": device.external_id if device else "",
            "device_name": device.name if device else "",
            "control_id": control.external_id if control else "",
            "control_key": control.key if control else "",
        }

    @classmethod
    def _record_device_context_from_mission(
        cls,
        mission: Mission,
        *,
        wechat_user_id: str,
        content: str,
        normalized_content: str,
        voice_transcript: str,
        execution_result: dict,
    ):
        if not mission.account_id or not mission.device_id or not mission.control_id:
            return
        from devices.models import DeviceControl

        control = DeviceControl.objects.select_related("device").filter(
            account=mission.account,
            external_id=mission.control_id,
        ).first()
        if control is None:
            return
        DeviceContextManager.record_operation(
            account=mission.account,
            platform_user_id=wechat_user_id,
            device=control.device,
            control_id=control.external_id,
            control_key=mission.control_key or control.key,
            operation_type=mission.operation_action or "set_property",
            value=(mission.operation_value or {}).get("value"),
            raw_user_msg=mission.original_prompt,
            normalized_msg=normalized_content,
            voice_transcript=voice_transcript,
            intent_json=(mission.metadata or {}).get("intent_json", {}),
            resolver_result=(mission.metadata or {}).get("resolver_result", {}),
            execution_result=execution_result,
        )

    # ------------------ 以下为处理后台定时轮询过来的附带标志的请求的特化方法 --------------------

    @classmethod
    async def _reset_counter_if_mijia(cls, prompt_text: str):
        match = re.search(r"\[MIJIA:(\w+)\]", prompt_text)
        if match:
            did = match.group(1)
            try:
                obs = await sync_to_async(ObservationCounter.objects.get)(
                    policy__device_did=did
                )
                obs.success_count = 0
                await sync_to_async(obs.save)()
                logger.info(f"[Brain] 已重置打回设备 {did} 的尝试计数器。")
            except Exception:
                pass

    @classmethod
    async def _increment_counter_if_mijia(cls, prompt_text: str):
        match = re.search(r"\[MIJIA:(\w+)\]", prompt_text)
        if match:
            did = match.group(1)
            try:
                obs, _ = await sync_to_async(ObservationCounter.objects.get_or_create)(
                    policy__device_did=did
                )
                obs.success_count += 1
                await sync_to_async(obs.save)()
                logger.info(
                    f"[Brain] {did} 操作被允许，当前容忍成功度涨为 {obs.success_count}。"
                )
            except Exception:
                pass

    @classmethod
    async def _elevate_policy_if_mijia(cls, prompt_text: str):
        match = re.search(r"\[MIJIA:(\w+)\]", prompt_text)
        if match:
            did = match.group(1)
            try:
                # 把 policy 提拔为 ALWAYS
                policy = await sync_to_async(HabitPolicy.objects.get)(device_did=did)
                policy.policy = HabitPolicy.PolicyChoices.ALWAYS
                await sync_to_async(policy.save)()
                logger.info(f"[Brain] 设备 {did} 的执行权限已被破格提拔为 ALWAYS！")
            except Exception:
                pass
