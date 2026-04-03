"""
Scheduler app for APScheduler integration.
Provides centralized task scheduling with MySQL persistence.
"""

from logging import getLogger

logger = getLogger(__name__)

# Flag to track if default tasks have been registered
_default_tasks_registered = False


async def register_default_schedules(scheduler):
    """
    Register default scheduled tasks.

    This should be called during scheduler startup to ensure tasks
    are registered with the 'replace' conflict policy.

    Args:
        scheduler: AsyncScheduler instance
    """
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    from scheduler.tasks import (
        daily_memory_review,
        device_status_check,
        cleanup_expired_sessions,
        refresh_global_keyword_cache_task,
        run_user_keyword_learning_task,
        run_global_keyword_learning_task,
        keyword_refresh_interval_seconds,
        keyword_learning_interval_user_seconds,
        keyword_learning_interval_global_seconds,
    )

    # Daily memory review at 2 AM Beijing time
    await scheduler.add_schedule(
        daily_memory_review,
        CronTrigger(hour=2, minute=0),
        id="daily_memory_review",
        conflict_policy="replace",
    )
    logger.info("Registered schedule: daily_memory_review (cron: 02:00)")

    # Device status check every 30 minutes
    await scheduler.add_schedule(
        device_status_check,
        IntervalTrigger(minutes=30),
        id="device_status_check",
        conflict_policy="replace",
    )
    logger.info("Registered schedule: device_status_check (interval: 30min)")

    # Session cleanup every hour
    await scheduler.add_schedule(
        cleanup_expired_sessions,
        IntervalTrigger(hours=1),
        id="cleanup_expired_sessions",
        conflict_policy="replace",
    )
    logger.info("Registered schedule: cleanup_expired_sessions (interval: 1h)")

    await scheduler.add_schedule(
        refresh_global_keyword_cache_task,
        IntervalTrigger(seconds=keyword_refresh_interval_seconds()),
        id="refresh_global_keyword_cache",
        conflict_policy="replace",
    )
    logger.info("Registered schedule: refresh_global_keyword_cache")

    await scheduler.add_schedule(
        run_user_keyword_learning_task,
        IntervalTrigger(seconds=keyword_learning_interval_user_seconds()),
        id="run_user_keyword_learning",
        conflict_policy="replace",
    )
    logger.info("Registered schedule: run_user_keyword_learning")

    await scheduler.add_schedule(
        run_global_keyword_learning_task,
        IntervalTrigger(seconds=keyword_learning_interval_global_seconds()),
        id="run_global_keyword_learning",
        conflict_policy="replace",
    )
    logger.info("Registered schedule: run_global_keyword_learning")


def register_default_tasks():
    """
    Mark default tasks as ready for registration.

    This is called from apps.py ready() method. Actual registration
    happens asynchronously during scheduler startup.
    """
    global _default_tasks_registered
    _default_tasks_registered = True
    logger.debug("Default tasks marked for registration")


def are_default_tasks_registered() -> bool:
    """Check if default tasks have been marked for registration."""
    return _default_tasks_registered


__all__ = [
    "register_default_schedules",
    "register_default_tasks",
    "are_default_tasks_registered",
]
