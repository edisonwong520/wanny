import asyncio
import re
from django.db.models import Q
from asgiref.sync import sync_to_async
from utils.logger import logger
from comms.models import Mission
from brain.models import HabitPolicy, ObservationCounter
from comms.ai import analyze_intent
from comms.executor import ShellExecutor
from memory.services import MemoryService
from accounts.models import Account
from providers.models import PlatformAuth


class WeChatService:
    """
    负责封装与 WeChat Bot 相关的业务逻辑：
    结合主动防御、大模型意图切分以及代理操作。
    """

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
        # SDK 的 IncomingMessage 字段是 .text 而不是 .content
        content = getattr(message, "text", "") or ""
        content = content.strip()
        wechat_user_id = getattr(message, "user_id", "unknown_user")

        if not content:
            logger.debug(
                f"[WeChat Service] 收到空消息，已忽略。user_id={wechat_user_id}"
            )
            return

        logger.info(
            f"[WeChat Service] 收到消息: user_id={wechat_user_id}, 内容='{content[:50]}'"
        )

        # 尝试查找关联的系统账户
        account = await cls.get_account_by_wechat_id(wechat_user_id)
        if not account:
            logger.warning(
                f"[WeChat Service] ⚠️ 收到未分配账户的消息: wechat_user_id={wechat_user_id}。将以受限模式运行。"
            )

        # ✨ 记忆引擎：将用户消息写入向量库（仅当账户存在时）
        if account:
            await MemoryService.record_conversation(
                account, "user", content, platform_user_id=wechat_user_id
            )

        try:
            # ✨ 检索与当前消息相关的历史记忆，作为上下文注入 AI
            memory_context = ""
            if account:
                memory_context = await MemoryService.get_context_for_chat(
                    account, content
                )

            # 无论什么话，一律送入超级大脑进行分类理解
            intent_data = await analyze_intent(content, memory_context=memory_context)
            logger.info(f"[Intent Result] {intent_data.get('type')}")
            intent_type = intent_data.get("type")

            # 1. 处理 CHAT 闲聊 或 意图不明 的兜底
            if intent_type == "CHAT" or not intent_type:
                reply_text = intent_data.get(
                    "response", "系统分析您的指令时遇到了一点困惑。"
                )
                await bot.reply(message, reply_text)
                # ✨ 记录 AI 回复
                if account:
                    await MemoryService.record_conversation(
                        account,
                        "assistant",
                        reply_text,
                        platform_user_id=wechat_user_id,
                    )
                return

            # --- 以下意图均与 Manual-Gate （PendingCommand） 强相关 ---

            # 2. 从头发起复杂的底层控制指令
            if intent_type == "COMPLEX_SHELL":
                shell_cmd = intent_data.get("shell_prompt")
                confirm_txt = intent_data.get(
                    "confirm_text", "准备进行 Shell 操作，请指示："
                )

                # 存入数据库排队缓存区待批阅
                new_mission = await sync_to_async(Mission.objects.create)(
                    account=account,
                    user_id=wechat_user_id,
                    original_prompt=content,  # 自己主动发起，不是米家
                    shell_command=shell_cmd,
                    status=Mission.StatusChoices.PENDING,
                    metadata=intent_data.get("metadata", {}),  # 存入丰富元数据
                )
                logger.info(
                    f"[WeChat Service] 挂起一条待审批任务 (ID: {new_mission.id})"
                )

                alert_text = f"⚠️ 注意 \n\n{confirm_txt}\n\n预期底层操作：\n{shell_cmd[:100]}...\n\n(请回复同意/执行/以后直接弄 等确认指令)"
                await bot.reply(message, alert_text)
                if account:
                    await MemoryService.record_conversation(
                        account,
                        "assistant",
                        alert_text,
                        platform_user_id=wechat_user_id,
                    )
                return

            # 3. 针对 CONFIRM, PERMANENT_ALLOW, DENY 处理 (这些必然是对之前的某个任务请求的回复)
            # 抓取当前账户（或 BROADCAST）最近一个还在待审批状态的任务
            mission_filter = Q(status=Mission.StatusChoices.PENDING)
            if account:
                mission_filter &= Q(account=account) | Q(user_id="BROADCAST")
            else:
                mission_filter &= Q(user_id=wechat_user_id)

            mission = await sync_to_async(
                lambda: Mission.objects.filter(mission_filter)
                .select_related("account")
                .order_by("-created_at")
                .first()
            )()

            logger.debug(
                f"[WeChat Service] 查找任务: wechat_user_id={wechat_user_id}, 结果={'找到 ID=' + str(mission.id) if mission else '无'}"
            )

            if not mission:
                # 兜底逻辑：如果找不到挂起的，查查最近一个任务的状态，看是否已完成
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

                await bot.reply(message, reply_txt)
                if account:
                    await MemoryService.record_conversation(
                        account, "assistant", reply_txt, platform_user_id=wechat_user_id
                    )
                return

            # 若任务尚未绑定账户（从 Monitor 广播产生），将其绑定到当前响应的账户
            if not mission.account_id and account:
                mission.account = account
                mission.user_id = wechat_user_id
                await sync_to_async(mission.save)()

            # 4. 用户表示拒绝或不同意
            if intent_type == "DENY":
                mission.status = Mission.StatusChoices.REJECTED  # 标记拒绝
                await sync_to_async(mission.save)()

                reply_txt = intent_data.get("response", "好的，已将此任务作废。")
                await bot.reply(message, reply_txt)
                if account:
                    await MemoryService.record_conversation(
                        account, "assistant", reply_txt, platform_user_id=wechat_user_id
                    )

                # 如果这个指令是后台米家感知器抛出的，还需要重置掉耐心忍让计数器！
                await cls._reset_counter_if_mijia(mission.original_prompt)
                return

            # 5. 用户表示放行
            if intent_type in ["CONFIRM", "PERMANENT_ALLOW"]:
                msg_ack = "🫡 正在全力执行，请稍候..."
                await bot.reply(message, msg_ack)
                if account:
                    await MemoryService.record_conversation(
                        account, "assistant", msg_ack, platform_user_id=wechat_user_id
                    )

                mission.status = Mission.StatusChoices.APPROVED
                await sync_to_async(mission.save)()

                # 区分是不是普通系统操作 还是米家设备修改动作
                try:
                    if mission.shell_command:
                        result_msg = await ShellExecutor.execute_yolo(
                            mission.shell_command
                        )
                    else:
                        # 没有 shell 脚本说明是一次模拟的内部 API 操控
                        # 这通常为内部监视器 (brain/monitor.py) 打好包送过来的
                        result_msg = "✅ 内部代理控制成功完成！(Mijia Hook)"
                except Exception as e:
                    result_msg = f"❌ 执行异常: {str(e)}"
                    mission.status = Mission.StatusChoices.FAILED
                    await sync_to_async(mission.save)()

                # 记录归档（如果没失败，保持为已通过或可以增加 EXECUTED 状态，目前暂以 APPROVED 为终点）
                # 可根据需要细化

                # 特别：如果是感知模式过来的，且用户本次回复是永久放权
                if intent_type == "PERMANENT_ALLOW":
                    await cls._elevate_policy_if_mijia(mission.original_prompt)
                    result_msg += "\n\n💡 已将您针对此情景下的偏好永久化存储，以后将默认自动帮您代劳而不必费心。"

                # 特别：普通授权米家动作时增加其计数器
                elif intent_type == "CONFIRM":
                    await cls._increment_counter_if_mijia(mission.original_prompt)

                await bot.reply(message, result_msg)
                if account:
                    await MemoryService.record_conversation(
                        account,
                        "assistant",
                        result_msg,
                        platform_user_id=wechat_user_id,
                    )
                logger.info(f"[WeChat Target] 任务彻底完成 (ID: {mission.id})")
                return

        except Exception as e:
            logger.error(f"[WeChat Target] 中枢流转发生阻断式故障: {str(e)}")
            try:
                await bot.reply(message, f"❌ 内部调度异常: {str(e)}")
            except:
                pass

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
