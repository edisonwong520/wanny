"""
APScheduler configuration and singleton instance.
Provides MySQL-backed persistent job store for task scheduling.
"""

import os
from logging import getLogger

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from apscheduler import AsyncScheduler
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
from apscheduler.serializers.json import JSONSerializer

logger = getLogger(__name__)

# Global instances (lazy initialized)
_scheduler: AsyncScheduler | None = None
_data_store: SQLAlchemyDataStore | None = None
_engine: AsyncEngine | None = None


def _get_mysql_url() -> str:
    """Build MySQL connection URL from environment variables."""
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = os.getenv("DB_PORT", "3306")
    database = os.getenv("DB_NAME", "wanny")

    # Use asyncmy for async MySQL driver
    return f"mysql+asyncmy://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"


def get_data_store() -> SQLAlchemyDataStore:
    """Get or create the SQLAlchemy data store for MySQL persistence."""
    global _data_store, _engine
    if _data_store is None:
        mysql_url = _get_mysql_url()
        host = os.getenv("DB_HOST", "127.0.0.1")
        port = os.getenv("DB_PORT", "3306")
        database = os.getenv("DB_NAME", "wanny")
        _engine = create_async_engine(mysql_url, echo=False)
        # Use JSON serializer for safety (pickle is vulnerable to injection)
        _data_store = SQLAlchemyDataStore(_engine, serializer=JSONSerializer())
        logger.info(f"Created SQLAlchemyDataStore with MySQL: {host}:{port}/{database}")
    return _data_store


async def get_scheduler() -> AsyncScheduler:
    """Get or create the async scheduler instance."""
    global _scheduler
    if _scheduler is None:
        data_store = get_data_store()
        _scheduler = AsyncScheduler(data_store=data_store)
        logger.info("Created AsyncScheduler instance")
    return _scheduler


async def start_scheduler() -> AsyncScheduler:
    """Start the scheduler and register default tasks."""
    scheduler = await get_scheduler()
    await scheduler.__aenter__()
    logger.info("Scheduler started")

    # Register default schedules from the scheduler app
    from scheduler import register_default_schedules
    await register_default_schedules(scheduler)
    logger.info("Default schedules registered")

    return scheduler


async def stop_scheduler() -> None:
    """Stop the scheduler gracefully."""
    global _scheduler, _data_store, _engine
    if _scheduler is not None:
        await _scheduler.__aexit__(None, None, None)
        logger.info("Scheduler stopped")
        _scheduler = None
    if _data_store is not None:
        _data_store = None
    if _engine is not None:
        await _engine.dispose()
        logger.info("Database engine disposed")
        _engine = None


# Convenience function for adding scheduled tasks
async def add_schedule(
    func,
    trigger,
    id: str,
    conflict_policy: str = "replace",
    **kwargs,
):
    """
    Add a scheduled task to the scheduler.

    Args:
        func: The function to execute (must be a globally referenceable function)
        trigger: APScheduler trigger (CronTrigger, IntervalTrigger, etc.)
        id: Unique identifier for the schedule
        conflict_policy: "replace" or "do_nothing" when schedule exists
        **kwargs: Additional arguments passed to scheduler.add_schedule
    """
    from apscheduler import ConflictPolicy

    scheduler = await get_scheduler()
    policy = ConflictPolicy.replace if conflict_policy == "replace" else ConflictPolicy.do_nothing
    await scheduler.add_schedule(func, trigger, id=id, conflict_policy=policy, **kwargs)
    logger.info(f"Added schedule: {id}")