"""
ASGI config for wanny_server project.

It exposes the ASGI callable as a module-level variable named ``application``.

Integrates APScheduler with ASGI lifespan for task scheduling with MySQL persistence.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wanny_server.settings")


async def scheduler_lifespan_app(scope, receive, send):
    """
    ASGI application wrapper that manages scheduler lifecycle.

    This middleware starts the scheduler on startup and stops it gracefully on shutdown.
    """
    if scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                # Import here to avoid circular imports
                from scheduler.core import start_scheduler

                await start_scheduler()
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                from scheduler.core import stop_scheduler

                await stop_scheduler()
                await send({"type": "lifespan.shutdown.complete"})
                return
    else:
        await django_app(scope, receive, send)


# Get Django ASGI application
django_app = get_asgi_application()

# Wrap with scheduler lifespan middleware
application = scheduler_lifespan_app