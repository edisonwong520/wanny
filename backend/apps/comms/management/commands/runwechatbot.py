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
            wechat_auth = PlatformAuth.objects.filter(platform_name="wechat").first()
            if wechat_auth and wechat_auth.auth_payload:
                with open(CRED_FILE, "w", encoding="utf-8") as f:
                    json.dump(wechat_auth.auth_payload, f)
                logger.info("[WeChat Bot] 已从 PlatformAuth 数据库加载微信授权凭证到本地。")
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
                                PlatformAuth.objects.update_or_create(
                                    platform_name="wechat",
                                    defaults={"auth_payload": data, "is_active": True}
                                )
                                logger.info("[WeChat Bot] SDK 更新了 Token，已同步入库至 PlatformAuth。")
                    except Exception as e:
                        logger.error(f"[WeChat Bot] 同步凭证到数据库发生错误: {e}")

        sync_thread = threading.Thread(target=sync_credentials_to_db, daemon=True)
        sync_thread.start()

        logger.info("[WeChat Bot] 正在初始化底层的 wechatbot-sdk...")
        
        # 初始化 wechatbot-sdk 实例并应用凭证路径
        bot = WeChatBot(cred_path=CRED_FILE)

        from brain.monitor import MonitorService
        
        # 为了兼容跨线程调用 bot.send()，我们捕获 bot_loop。
        # 这里最安全的做法是在新线程中自己维持监控死循环，发消息时交由安全方法处理。
        monitor_thread = threading.Thread(target=MonitorService.start_polling, daemon=True, args=(bot,))
        monitor_thread.start()
        
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
        # 接管该主线程，使用 bot.run() 
        try:
            bot.run()
        except KeyboardInterrupt:
            logger.info("[WeChat Bot] 用户主动停止了机器人服务。")
        except Exception as e:
            logger.error(f"[WeChat Bot] 运行期间遇到异常退出: {str(e)}")
