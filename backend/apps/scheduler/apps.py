"""
Django app config for scheduler integration.
Registers default scheduled tasks when the app is ready.
"""

from django.apps import AppConfig
from logging import getLogger

logger = getLogger(__name__)


class SchedulerConfig(AppConfig):
    """Django app config for scheduler integration."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "scheduler"
    verbose_name = "Task Scheduler"

    def ready(self):
        """
        Register default scheduled tasks when Django app is ready.

        Note: Tasks are registered lazily when the scheduler starts,
        not here. This method is kept for future Django-specific setup.
        """
        # Import tasks to ensure they're available for scheduling
        # Actual registration happens in asgi.py lifespan startup
        try:
            from scheduler import register_default_tasks
            register_default_tasks()
        except ImportError:
            logger.debug("Default tasks registration deferred to scheduler startup")