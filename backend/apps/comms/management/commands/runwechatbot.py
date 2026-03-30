import os
import json
import threading
import time
from django.core.management.base import BaseCommand
from wechatbot import WeChatBot
from utils.logger import logger
from comms.services import WeChatService
from providers.models import PlatformAuth

class Command(BaseCommand):
    help = "启动微信消息监听代理守护进程"

    def handle(self, *args, **options):
        logger.info("========== Wanny WeChat Bot Agent 启动 ==========")
        
        CRED_FILE = "wechat_credentials.json"
        
        # 1. 启动前，检查数据库里是否有之前存过的 credential，如果有则写入到本地给 SDK 使用
        try:
            wechat_auth = PlatformAuth.objects.filter(platform_name="wechat", is_active=True).first()
            if wechat_auth and wechat_auth.auth_payload:
                with open(CRED_FILE, "w", encoding="utf-8") as f:
                    json.dump(wechat_auth.auth_payload, f)
                logger.info("[WeChat Bot] 已从 PlatformAuth 数据库加载微信授权凭证到本地。")
            elif os.path.exists(CRED_FILE):
                os.remove(CRED_FILE)
                logger.info("[WeChat Bot] 当前没有启用中的微信授权，已清理本地旧凭证文件。")
        except Exception as e:
            logger.error(f"[WeChat Bot] 从数据库读取微信凭证时出错: {e}")

        # 2. 启动一个后台线程，监控文件变化并同步回数据库 (规避阻碍 wechatbot 的 main asyncio eventloop)
        def sync_credentials_to_db():
            last_mtime = 0
            while True:
                time.sleep(5)
                if os.path.exists(CRED_FILE):
                    try:
                        mtime = os.path.getmtime(CRED_FILE)
                        if mtime > last_mtime:
                            last_mtime = mtime
                            with open(CRED_FILE, "r", encoding="utf-8") as f:
                                data = json.load(f)
                            # 如果为空，可能当时还在写入，尝试规避
                            if data:
                                existing_auth = PlatformAuth.objects.filter(platform_name="wechat").first()
                                if existing_auth and not existing_auth.is_active:
                                    logger.info("[WeChat Bot] 微信授权当前处于停用状态，跳过凭证回写。")
                                    continue
                                PlatformAuth.objects.update_or_create(
                                    platform_name="wechat",
                                    defaults={"auth_payload": data, "is_active": True}
                                )
                                logger.info("[WeChat Bot] SDK 更新了 Token，已同步入库至 PlatformAuth。")
                    except Exception as e:
                        logger.error(f"[WeChat Bot] 同步凭证到数据库发生错误: {e}")

        sync_thread = threading.Thread(target=sync_credentials_to_db, daemon=True)
        sync_thread.start()

        # 3. 启动前软删除残留的僵尸工单（未审批、未执行、未取消的）
        from comms.models import PendingCommand
        zombie_count = PendingCommand.objects.filter(
            is_approved=False, is_executed=False, is_cancelled=False
        ).update(is_cancelled=True)
        if zombie_count:
            logger.info(f"[WeChat Bot] 启动清理：已软删除 {zombie_count} 条残留僵尸工单 (is_cancelled=True)")

        logger.info("[WeChat Bot] 正在初始化底层的 wechatbot-sdk...")
        
        # 初始化 wechatbot-sdk 实例并应用凭证路径
        bot = WeChatBot(cred_path=CRED_FILE)

        from brain.monitor import MonitorService
        from memory.review import ReviewEngine
        import asyncio
        
        @bot.on_message
        async def handle_message(message):
            """
            收到微信信息时的入口 Handler，必须是异步 (Async/Await)
            """
            logger.info("========== 收到新的微信信息 ==========")
            try:
                # 转交给统一的业务服务中心，便于后期解耦、记录和分发意图
                await WeChatService.process_incoming_message(message, bot)

            except Exception as e:
                logger.error(f"[WeChat Bot] 代理层抛出严重拦截错误: {str(e)}")

        logger.info("[WeChat Bot] 启动事件循环并接管 WebSocket，请按提示扫码...")
        
        async def main():
            # 开启大脑心跳监测并行协程
            asyncio.create_task(MonitorService.loop_start(bot))
            # 开启每日复盘引擎并行协程
            asyncio.create_task(ReviewEngine.loop_start(bot))
            # 配合 asyncio，调用真实的底层异步入口
            await bot._run_sync()

        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.info("[WeChat Bot] 用户主动停止了机器人服务。")
        except Exception as e:
            logger.error(f"[WeChat Bot] 运行期间遇到异常退出: {str(e)}")
