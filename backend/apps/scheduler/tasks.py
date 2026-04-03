"""
Example scheduled tasks for Wanny.

This module demonstrates how to define and register scheduled tasks.
Add your own tasks here and register them in the ready() method of apps.py.
"""

import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


async def daily_memory_review():
    """
    Daily task for memory review and user profile update.

    This task is mentioned in the project README as part of Jarvis's
    proactive care capabilities - "Jarvis 每天凌晨会自动复盘当天的交互".
    """
    logger.info(f"[Scheduled Task] Daily memory review started at {datetime.now()}")
    # TODO: Implement actual memory review logic
    # Example: analyze yesterday's conversations, update user preferences
    logger.info("[Scheduled Task] Daily memory review completed")


async def device_status_check():
    """
    Periodic device status check.

    Monitors device states and triggers proactive suggestions based on
    environmental changes.
    """
    logger.info(f"[Scheduled Task] Device status check at {datetime.now()}")
    # TODO: Implement device status polling and anomaly detection
    logger.info("[Scheduled Task] Device status check completed")


async def cleanup_expired_sessions():
    """
    Clean up expired sessions and stale data.
    """
    logger.info(f"[Scheduled Task] Session cleanup at {datetime.now()}")
    # TODO: Implement session cleanup logic
    logger.info("[Scheduled Task] Session cleanup completed")


async def refresh_global_keyword_cache_task():
    """
    Refresh the in-memory global keyword cache so newly learned or seeded
    keywords become visible without waiting for on-demand reloads.
    """
    from comms.tasks import refresh_global_keyword_cache

    logger.info(f"[Scheduled Task] Global keyword cache refresh started at {datetime.now()}")
    await refresh_global_keyword_cache()
    logger.info("[Scheduled Task] Global keyword cache refresh completed")


async def run_user_keyword_learning_task():
    """
    Periodic per-account learning sweep.
    """
    from comms.tasks import run_periodic_user_keyword_learning

    logger.info(f"[Scheduled Task] User keyword learning started at {datetime.now()}")
    learned = await run_periodic_user_keyword_learning()
    logger.info("[Scheduled Task] User keyword learning completed: learned=%s", learned)


async def run_global_keyword_learning_task():
    """
    Lower-frequency global keyword learning sweep.
    """
    from comms.tasks import run_periodic_global_keyword_learning

    logger.info(f"[Scheduled Task] Global keyword learning started at {datetime.now()}")
    learned = await run_periodic_global_keyword_learning()
    logger.info("[Scheduled Task] Global keyword learning completed: learned=%s", learned)


def keyword_refresh_interval_seconds() -> int:
    try:
        return max(int(os.getenv("KEYWORD_REFRESH_INTERVAL", "3600")), 1)
    except ValueError:
        return 3600


def keyword_learning_interval_user_seconds() -> int:
    try:
        return max(int(os.getenv("KEYWORD_LEARNING_INTERVAL_USER", "21600")), 1)
    except ValueError:
        return 21600


def keyword_learning_interval_global_seconds() -> int:
    try:
        return max(int(os.getenv("KEYWORD_LEARNING_INTERVAL_GLOBAL", "86400")), 1)
    except ValueError:
        return 86400
