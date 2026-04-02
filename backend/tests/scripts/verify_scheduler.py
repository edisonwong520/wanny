"""
Verification script for APScheduler integration.

This script tests the scheduler without starting Django's full ASGI server.
Run: uv run python tests/scripts/verify_scheduler.py
"""

import asyncio
import os
import sys
import logging

# Setup Django path
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, backend_dir)
sys.path.insert(0, os.path.join(backend_dir, 'apps'))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wanny_server.settings")

import django
django.setup()

# Use simple console logger for verification
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("verify_scheduler")


# Test task must be a global function for APScheduler to serialize
async def test_task():
    """Test task for scheduler verification."""
    from datetime import datetime
    logger.info(f"*** TEST TASK EXECUTED at {datetime.now()} ***")


async def test_scheduler():
    """Test scheduler startup, shutdown and MySQL connection."""
    from scheduler.core import start_scheduler, stop_scheduler, get_scheduler
    from apscheduler.triggers.interval import IntervalTrigger

    try:
        # Start scheduler
        logger.info("Starting scheduler...")
        scheduler = await start_scheduler()
        logger.info("Scheduler started successfully")

        # Add a test schedule
        await scheduler.add_schedule(
            test_task,
            IntervalTrigger(seconds=5),
            id="test_task",
            conflict_policy="replace",
        )
        logger.info("Added test task schedule (5s interval)")

        # Wait for one execution
        logger.info("Waiting 7 seconds for task execution...")
        await asyncio.sleep(7)

        # Check schedules
        schedules = await scheduler.get_schedules()
        logger.info(f"Active schedules: {[s.id for s in schedules]}")

        # Stop scheduler
        logger.info("Stopping scheduler...")
        await stop_scheduler()
        logger.info("Scheduler stopped successfully")

        print("\n" + "=" * 60)
        print("SUCCESS: Scheduler integration verified!")
        print("=" * 60)

    except Exception as e:
        logger.error(f"Scheduler test failed: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    print("=" * 60)
    print("APScheduler Integration Verification")
    print("=" * 60)
    print()
    asyncio.run(test_scheduler())