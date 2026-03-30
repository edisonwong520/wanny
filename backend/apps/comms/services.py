import asyncio
import re
from django.db.models import Q
from asgiref.sync import sync_to_async
from utils.logger import logger
from comms.models import PendingCommand
from brain.models import HabitPolicy, ObservationCounter
from comms.ai import analyze_intent
from comms.executor import ShellExecutor
from memory.services import MemoryService

class WeChatService:
    """
    负责封装与 WeChat Bot 相关的业务逻辑：
    结合主动防御、大模型意图切分以及代理操作。
    """
    
    @classmethod
    async def process_incoming_message(cls, message, bot):
        # SDK 的 IncomingMessage 字段是 .text 而不是 .content
        content = getattr(message, "text", "") or ""
        content = content.strip()
        user_id = getattr(message, "user_id", "unknown_user")
        
        if not content:
            logger.debug(f"[WeChat Service] 收到空消息，已忽略。user_id={user_id}")
            return

        logger.info(f"[WeChat Service] 收到消息: user_id={user_id}, 内容='{content[:50]}'")

        # ✨ 记忆引擎：先将用户消息写入向量库
        await MemoryService.record_conversation(user_id, "user", content)

        try:
            # ✨ 检索与当前消息相关的历史记忆，作为上下文注入 AI
            memory_context = await MemoryService.get_context_for_chat(user_id, content)

            # 无论什么话，一律送入超级大脑进行分类理解
            intent_data = await analyze_intent(content, memory_context=memory_context)
            logger.info(f"[Intent Result] {intent_data.get('type')}")
            intent_type = intent_data.get("type")

            # 1. 处理 CHAT 闲聊 或 意图不明 的兜底
            if intent_type == "CHAT" or not intent_type:
                reply_text = intent_data.get("response", "Sir, 系统分析您的指令时遇到了一点困惑。")
                await bot.reply(message, reply_text)
                # ✨ 记录 AI 回复
                await MemoryService.record_conversation(user_id, "assistant", reply_text)
                return
            
            # --- 以下意图均与 Manual-Gate （PendingCommand） 强相关 ---
            
            # 2. 从头发起复杂的底层控制指令
            if intent_type == "COMPLEX_SHELL":
                shell_cmd = intent_data.get("shell_prompt")
                confirm_txt = intent_data.get("confirm_text", "Sir, 准备进行该底壳操作，请指示：")
                
                # 存入数据库排队缓存区待批阅
                new_pending = await sync_to_async(PendingCommand.objects.create)(
                    user_id=user_id,
                    original_prompt=content, # 自己主动发起，不是米家
                    shell_command=shell_cmd,
                    metadata=intent_data.get("metadata", {})  # 存入丰富元数据
                )
                logger.info(f"[WeChat Service] 挂起一条待审批系统指令 (ID: {new_pending.id})")
                
                alert_text = f"🛡【系统核心拦截】🛡\n\n{confirm_txt}\n\n预期底层操作：\n{shell_cmd[:100]}...\n\n(请回复同意/执行/以后都直接弄 等确认指令)"
                await bot.reply(message, alert_text)
                return
            
            # 3. 针对 CONFIRM, PERMANENT_ALLOW, DENY 处理 (这些必然是对之前的某个拦截请求的回复)
            # 抓取用户最近一条还未批准的积压订单
            # 注意：Monitor 创建时 user_id 可能是 "BROADCAST"（还未来得及绑定），所以需要同时匹配
            pending_cmd = await sync_to_async(
                PendingCommand.objects.filter(
                    Q(user_id=user_id) | Q(user_id="BROADCAST"),
                    is_approved=False,
                    is_executed=False,
                    is_cancelled=False
                ).order_by('-created_at').first
            )()
            
            logger.debug(f"[WeChat Service] 查找 PendingCommand: user_id={user_id}, 结果={'找到 ID=' + str(pending_cmd.id) if pending_cmd else '无'}")

            if not pending_cmd:
                # 找不到任何积压的请求，但模型识别为了确认或拒绝 (大概率是上下文理解误区)
                await bot.reply(message, intent_data.get("response", "Sir, 目前并没有找到需要您授权操作的挂起任务。"))
                return
            
            # 如果是 BROADCAST 的，绑定到当前操作者
            if pending_cmd.user_id == "BROADCAST":
                pending_cmd.user_id = user_id
                await sync_to_async(pending_cmd.save)()
                
            # 4. 用户表示拒绝或不同意
            if intent_type == "DENY":
                pending_cmd.is_executed = True # 标记假意执行结束封存
                await sync_to_async(pending_cmd.save)()
                
                reply_txt = intent_data.get("response", "好的 Sir，已将此操作作废废弃。")
                await bot.reply(message, reply_txt)
                
                # 如果这个指令是后台米家感知器抛出的，还需要重置掉耐心忍让计数器！
                await cls._reset_counter_if_mijia(pending_cmd.original_prompt)
                return

            # 5. 用户表示放行
            if intent_type in ["CONFIRM", "PERMANENT_ALLOW"]:
                await bot.reply(message, "🫡  Sir, 系统锁已被你解除，正在全力执行，请稍候...")
                
                pending_cmd.is_approved = True
                await sync_to_async(pending_cmd.save)()

                # 区分是不是普通系统操作 还是米家设备修改动作
                if pending_cmd.shell_command:
                    result_msg = await ShellExecutor.execute_yolo(pending_cmd.shell_command)
                else:
                    # 没有 shell 脚本说明是一次模拟的内部 API 操控
                    # 这通常为内部监视器 (brain/monitor.py) 打好包送过来的
                    result_msg = "✅ 内部代理控制成功完成！(Mijia Hook)"

                # 记录完结
                pending_cmd.is_executed = True
                await sync_to_async(pending_cmd.save)()
                
                # 特别：如果是感知模式过来的，且用户本次回复是永久放权
                if intent_type == "PERMANENT_ALLOW":
                    await cls._elevate_policy_if_mijia(pending_cmd.original_prompt)
                    result_msg += "\n\n💡 Sir, 已将您针对此情景下的偏好永久化存储 [HabitPolicy->ALWAYS]，以后将默认自动帮您代劳而不必费心。"
                
                # 特别：普通授权米家动作时增加其计数器
                elif intent_type == "CONFIRM":
                    await cls._increment_counter_if_mijia(pending_cmd.original_prompt)

                await bot.reply(message, result_msg)
                logger.info(f"[WeChat Target] 手动拦截任务彻底完成 (ID: {pending_cmd.id})")
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
                obs = await sync_to_async(ObservationCounter.objects.get)(policy__device_did=did)
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
                obs, _ = await sync_to_async(ObservationCounter.objects.get_or_create)(policy__device_did=did)
                obs.success_count += 1
                await sync_to_async(obs.save)()
                logger.info(f"[Brain] {did} 操作被允许，当前容忍成功度涨为 {obs.success_count}。")
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
