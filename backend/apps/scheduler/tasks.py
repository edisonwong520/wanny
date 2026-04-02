"""
Example scheduled tasks for Wanny.

This module demonstrates how to define and register scheduled tasks.
Add your own tasks here and register them in the ready() method of apps.py.
"""

import logging
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