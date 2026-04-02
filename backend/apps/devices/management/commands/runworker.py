import os
import time

from django.core.management.base import BaseCommand

from accounts.models import Account
from devices.queue import RedisError, dequeue_account_refresh, get_block_timeout, get_queue_backend, redis_queue_enabled
from devices.services import DeviceDashboardService
from utils.logger import logger


class Command(BaseCommand):
    help = "Run the background worker for scheduled device snapshot refresh jobs."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_scan_at = 0.0

    def _should_run_scan(self, *, sync_interval: int) -> bool:
        if not redis_queue_enabled():
            return True
        # Redis mode is event-driven. This scan is only a low-frequency fallback
        # for stale snapshots or requests that were recorded but not enqueued.
        now = time.monotonic()
        if now - self._last_scan_at >= sync_interval:
            self._last_scan_at = now
            return True
        return False

    def run_iteration(self, *, sync_interval: int, block_timeout: int) -> int:
        from django import db

        db.close_old_connections()
        triggered_accounts = set()
        refreshed_accounts = 0
        should_scan = self._should_run_scan(sync_interval=sync_interval)

        if redis_queue_enabled():
            try:
                account_id = dequeue_account_refresh(timeout=block_timeout)
            except RedisError as error:
                logger.error(f"[Worker] Redis queue consume failed: {error}")
                account_id = None
                should_scan = self._should_run_scan(sync_interval=0)

            if account_id is not None:
                account = Account.objects.filter(id=account_id).first()
                if account is not None:
                    logger.debug(f"[Worker] Consuming Redis refresh task for account_id={account.id} email={account.email}")
                    refreshed = DeviceDashboardService.run_pending_refresh(
                        account=account,
                        sync_interval_seconds=sync_interval,
                    )
                    if refreshed:
                        refreshed_accounts += 1
                    triggered_accounts.add(account.id)
                    should_scan = False

        if not should_scan:
            return refreshed_accounts

        logger.debug(f"[Worker] Starting scan iteration, checking all accounts")
        for account in Account.objects.all():
            if account.id in triggered_accounts:
                continue
            logger.debug(f"[Worker] Checking account_id={account.id} email={account.email}")
            refreshed = DeviceDashboardService.run_pending_refresh(
                account=account,
                sync_interval_seconds=sync_interval,
            )
            if refreshed:
                refreshed_accounts += 1

        if refreshed_accounts:
            logger.info(f"[Worker] 已完成一轮设备快照刷新。accounts={refreshed_accounts}")
        return refreshed_accounts

    def handle(self, *args, **options):
        loop_interval = int(os.getenv("WORKER_LOOP_INTERVAL", "10"))
        sync_interval = int(os.getenv("DEVICE_SYNC_INTERVAL", "300"))
        queue_backend = get_queue_backend()
        block_timeout = get_block_timeout()

        logger.info(
            f"[Worker] 启动后台 Worker。backend={queue_backend} "
            f"loop_interval={loop_interval}s device_sync_interval={sync_interval}s"
        )

        while True:
            try:
                self.run_iteration(sync_interval=sync_interval, block_timeout=block_timeout)
            except KeyboardInterrupt:
                logger.info("[Worker] 收到停止信号，准备退出。")
                return
            except Exception as error:
                logger.error(f"[Worker] 执行定时任务失败: {error}")

            if not redis_queue_enabled():
                time.sleep(loop_interval)
