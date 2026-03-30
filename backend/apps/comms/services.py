import asyncio
from asgiref.sync import sync_to_async
from utils.logger import logger
from comms.models import PendingCommand
from comms.ai import analyze_intent
from comms.executor import ShellExecutor

class WeChatService:
    """
    负责封装与 WeChat Bot 相关的业务逻辑：
    - 普通闲聊回复（Simple Query）
    - Manual-Gate 请求分配与拦截执行（Complex Tasks）
    """
    
    # 手动放闸触发词库
    APPROVE_WORDS = ["批准", "yes", "ok", "执行", "同意"]

    @classmethod
    async def process_incoming_message(cls, message, bot):
        content = getattr(message, "content", "").strip()
        user_id = getattr(message, "user_id", "unknown_user")
        
        if not content:
            return

        logger.info(f"[WeChat Target] {user_id} - {content[:20]}")

        # ==========================================
        # 门禁一：拦截放闸短词 (Manual-Gate Approve Check)
        # ==========================================
        if content.lower() in cls.APPROVE_WORDS:
            # 查找此用户的未批准命令（需转换为全异步查询方式）
            pending_cmd = await sync_to_async(
                PendingCommand.objects.filter(
                    user_id=user_id, 
                    is_approved=False
                ).order_by('-created_at').first
            )()

            if pending_cmd:
                try:
                    await bot.reply(message, "🫡  Sir, 正在授权执行底层容器操作，请稍候...")
                    
                    # 标记已批准避免并发或重复消费
                    pending_cmd.is_approved = True
                    await sync_to_async(pending_cmd.save)()

                    # 执行底层 Yolo 任务 (Blocking but running to thread pool internally)
                    result_msg = await ShellExecutor.execute_yolo(pending_cmd.shell_command)
                    
                    # 标记完结
                    pending_cmd.is_executed = True
                    await sync_to_async(pending_cmd.save)()

                    await bot.reply(message, result_msg)
                    logger.info(f"YOLO 审批流水线完成执行并答复：{pending_cmd.id}")
                    return

                except Exception as e:
                    logger.error(f"[Execute Route] 落地触发失败：{e}")
                    await bot.reply(message, f"❌ 底层指令拉起时崩溃: {str(e)}")
                    return

        # ==========================================
        # 主逻辑二：AI 大脑意图分解切片
        # ==========================================
        try:
            # 进入大模型意图分析
            intent_data = await analyze_intent(content)
            logger.info(f"[Intent Result] {intent_data}")

            # 1. 如果模型判定是直接闲聊
            if intent_data.get("type") == "simple":
                # 直接通过微信回发
                reply_text = intent_data.get("response", "系统在分析中遇到了阻碍。")
                await bot.reply(message, reply_text)
                
            # 2. 如果模型判定是涉及代理操作和深层搜索的系统指令
            elif intent_data.get("type") == "complex":
                shell_cmd = intent_data.get("shell_prompt")
                confirm_txt = intent_data.get("confirm_text", "Sir, 执行该任务需要调用底层 Agent 外壳，请同意：")
                
                # 存入数据库排队缓存区 Manual-Gate
                new_pending = await sync_to_async(PendingCommand.objects.create)(
                    user_id=user_id,
                    original_prompt=content,
                    shell_command=shell_cmd,
                )
                logger.info(f"[WeChat Service] 创建了一项等待排查的审批记录 (ID: {new_pending.id})")
                
                # 等待用户确认
                # 回帖包括确认提示和执行内容预览
                alert_text = f"🛡【系统拦截锁】🛡\n\n{confirm_txt}\n\n将执行任务：{shell_cmd[:100]}...\n\n(回复 [ 执行 / 批准 / YES ] 来通过放行此操作)"
                await bot.reply(message, alert_text)

        except Exception as e:
            logger.error(f"[AI Pipeline Error] 大模型通道阻塞崩溃: {str(e)}")
            try:
                await bot.reply(message, f"❌ Ai Agent 通道故障: {str(e)}")
            except:
                pass
