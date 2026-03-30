import os
import json
import threading
import time

from django.core.management.base import BaseCommand

from utils.logger import logger
from providers.models import PlatformAuth


class Command(BaseCommand):
    help = "启动微信消息监听代理守护进程"
    auth_poll_interval_seconds = 5
    auth_wait_log_interval_seconds = 60
    credential_sync_interval_seconds = 5

    def _get_active_wechat_auth(self):
        return PlatformAuth.objects.filter(platform_name="wechat", is_active=True).first()

    def _extract_auth_payload(self, auth_obj):
        payload = getattr(auth_obj, "auth_payload", None)
        return payload if isinstance(payload, dict) else {}

    def _write_credentials_file(self, cred_file, payload):
        with open(cred_file, "w", encoding="utf-8") as f:
            json.dump(payload, f)

    def _clear_credentials_file(self, cred_file):
        if os.path.exists(cred_file):
            os.remove(cred_file)
            logger.info("[WeChat Bot] 当前没有启用中的微信授权，已清理本地旧凭证文件。")

    def _wait_for_active_wechat_auth(self):
        last_wait_log_at = 0.0

        while True:
            try:
                wechat_auth = self._get_active_wechat_auth()
                if self._extract_auth_payload(wechat_auth):
                    return wechat_auth
            except Exception as e:
                logger.error(f"[WeChat Bot] 轮询微信授权状态时出错: {e}")

            now = time.monotonic()
            if last_wait_log_at == 0.0 or now - last_wait_log_at >= self.auth_wait_log_interval_seconds:
                logger.debug("[WeChat Bot] 尚未检测到启用中的微信授权，继续待命，不初始化 SDK。")
                last_wait_log_at = now

            time.sleep(self.auth_poll_interval_seconds)

    def _prepare_wechat_credentials(self, cred_file):
        try:
            wechat_auth = self._get_active_wechat_auth()
        except Exception as e:
            logger.error(f"[WeChat Bot] 从数据库读取微信凭证时出错: {e}")
            wechat_auth = None

        payload = self._extract_auth_payload(wechat_auth)
        if payload:
            self._write_credentials_file(cred_file, payload)
            logger.info("[WeChat Bot] 已从 PlatformAuth 数据库加载微信授权凭证到本地。")
            return

        self._clear_credentials_file(cred_file)

        wechat_auth = self._wait_for_active_wechat_auth()
        payload = self._extract_auth_payload(wechat_auth)
        self._write_credentials_file(cred_file, payload)
        logger.info("[WeChat Bot] 已检测到微信授权，开始初始化底层 SDK。")

    def _start_credentials_sync_thread(self, cred_file):
        def sync_credentials_to_db():
            last_mtime = 0
            while True:
                time.sleep(self.credential_sync_interval_seconds)
                if os.path.exists(cred_file):
                    try:
                        mtime = os.path.getmtime(cred_file)
                        if mtime > last_mtime:
                            last_mtime = mtime
                            with open(cred_file, "r", encoding="utf-8") as f:
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

    def _cleanup_zombie_pending_commands(self):
        from comms.models import PendingCommand

        zombie_count = PendingCommand.objects.filter(
            is_approved=False, is_executed=False, is_cancelled=False
        ).update(is_cancelled=True)
        if zombie_count:
            logger.info(f"[WeChat Bot] 启动清理：已软删除 {zombie_count} 条残留僵尸工单 (is_cancelled=True)")

    def _run_bot(self, cred_file):
        import asyncio

        from wechatbot import WeChatBot
        from brain.monitor import MonitorService
        from comms.services import WeChatService
        from memory.review import ReviewEngine

        logger.info("[WeChat Bot] 正在初始化底层的 wechatbot-sdk...")

        # 初始化 wechatbot-sdk 实例并应用凭证路径
        bot = WeChatBot(cred_path=cred_file)

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

        logger.info("[WeChat Bot] 启动事件循环并接管 WebSocket...")

        async def main():
            # 开启大脑心跳监测并行协程
            asyncio.create_task(MonitorService.loop_start(bot))
            # 开启每日复盘引擎并行协程
            asyncio.create_task(ReviewEngine.loop_start(bot))
            # 配合 asyncio，调用真实的底层异步入口
            await bot._run_sync()

        asyncio.run(main())

    def handle(self, *args, **options):
        logger.info("========== Wanny WeChat Bot Agent 启动 ==========")

        cred_file = os.path.join("credentials", "wechat_credentials.json")

        try:
            self._prepare_wechat_credentials(cred_file)
            self._start_credentials_sync_thread(cred_file)
            self._cleanup_zombie_pending_commands()
            self._run_bot(cred_file)
        except KeyboardInterrupt:
            logger.info("[WeChat Bot] 用户主动停止了机器人服务。")
        except Exception as e:
            logger.error(f"[WeChat Bot] 运行期间遇到异常退出: {str(e)}")
