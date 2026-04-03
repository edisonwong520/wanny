from __future__ import annotations

import logging

from asgiref.sync import sync_to_async

from accounts.models import Account
from comms.keyword_learner import KeywordLearner
from comms.keyword_loader import KeywordLoader

logger = logging.getLogger(__name__)


async def refresh_keyword_cache(account_id: int | None = None):
    await KeywordLoader.invalidate_account(account_id)
    if account_id:
        await KeywordLoader.get_keywords_for_account(account_id)
    else:
        await KeywordLoader.get_keywords_for_account(None)


async def run_keyword_learning_for_account(account_id: int) -> int:
    learned = await KeywordLearner.run_learning_cycle(account_id)
    await refresh_keyword_cache(account_id)
    return learned


async def run_global_keyword_learning() -> int:
    account_ids = await sync_to_async(list)(Account.objects.values_list("id", flat=True))
    total = 0
    for account_id in account_ids:
        total += await run_keyword_learning_for_account(account_id)
    return total


async def refresh_global_keyword_cache() -> None:
    logger.info("[Keyword Tasks] Refreshing global keyword cache")
    await refresh_keyword_cache(None)
    logger.info("[Keyword Tasks] Global keyword cache refreshed")


async def run_periodic_user_keyword_learning() -> int:
    logger.info("[Keyword Tasks] Starting periodic user keyword learning sweep")
    total = await run_global_keyword_learning()
    logger.info("[Keyword Tasks] Periodic user keyword learning completed: learned=%s", total)
    return total


async def run_periodic_global_keyword_learning() -> int:
    logger.info("[Keyword Tasks] Starting periodic global keyword refresh from devices/history")
    total = await run_global_keyword_learning()
    logger.info("[Keyword Tasks] Periodic global keyword learning completed: learned=%s", total)
    return total
