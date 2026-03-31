import os
import time

from django.core.management.base import BaseCommand

from accounts.models import Account
from devices.services import DeviceDashboardService
from utils.logger import logger


class Command(BaseCommand):
    help = "Run the background worker for scheduled device snapshot refresh jobs."

    def handle(self, *args, **options):
        loop_interval = int(os.getenv("WORKER_LOOP_INTERVAL", "10"))
        sync_interval = int(os.getenv("DEVICE_SYNC_INTERVAL", "300"))

        logger.info(
            f"[Worker] 启动后台 Worker。loop_interval={loop_interval}s device_sync_interval={sync_interval}s"
        )

        while True:
            try:
                from django import db
                db.close_old_connections()
                
                refreshed_accounts = 0
                for account in Account.objects.all():
                    refreshed = DeviceDashboardService.run_pending_refresh(
                        account=account,
                        sync_interval_seconds=sync_interval,
                    )
                    if refreshed:
                        refreshed_accounts += 1

                if refreshed_accounts:
                    logger.info(f"[Worker] 已完成一轮设备快照刷新。accounts={refreshed_accounts}")
            except KeyboardInterrupt:
                logger.info("[Worker] 收到停止信号，准备退出。")
                return
            except Exception as error:
                logger.error(f"[Worker] 执行定时任务失败: {error}")

            time.sleep(loop_interval)
