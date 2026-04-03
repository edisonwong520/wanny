import logging
from datetime import datetime

from asgiref.sync import sync_to_async

from care.services.processor import CareEventProcessor
from care.services.push import CarePushService
from care.services.scanner import InspectionScanner
from care.services.weather import WeatherDataService

logger = logging.getLogger(__name__)


async def run_periodic_inspection() -> int:
    logger.info("[Scheduled Task] Proactive care inspection started at %s", datetime.now())
    created = await sync_to_async(InspectionScanner.scan_all_accounts)()
    pushed = await CarePushService.deliver_due_suggestions()
    logger.info("[Scheduled Task] Proactive care inspection completed: created=%s", created)
    logger.info("[Scheduled Task] Proactive care push after inspection: pushed=%s", pushed)
    return created


async def fetch_weather_and_generate_care() -> int:
    logger.info("[Scheduled Task] Weather fetch started at %s", datetime.now())

    def _run_sync():
        generated = 0
        for source in WeatherDataService.fetch_all_active_sources():
            if CareEventProcessor.process_weather_source(source) is not None:
                generated += 1
        return generated

    created = await sync_to_async(_run_sync)()
    pushed = await CarePushService.deliver_due_suggestions()
    logger.info("[Scheduled Task] Weather fetch completed: generated=%s", created)
    logger.info("[Scheduled Task] Proactive care push after weather fetch: pushed=%s", pushed)
    return created


async def deliver_care_suggestions() -> int:
    logger.info("[Scheduled Task] Proactive care push started at %s", datetime.now())
    pushed = await CarePushService.deliver_due_suggestions()
    logger.info("[Scheduled Task] Proactive care push completed: pushed=%s", pushed)
    return pushed
