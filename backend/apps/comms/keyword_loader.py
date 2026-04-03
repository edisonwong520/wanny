from __future__ import annotations

import os
import time
from copy import deepcopy

from asgiref.sync import sync_to_async

from comms.initial_keywords import build_keyword_cache, get_initial_keyword_cache
from comms.models import LearnedKeyword


def _refresh_interval_seconds() -> int:
    try:
        return max(int(os.getenv("KEYWORD_REFRESH_INTERVAL", "3600")), 1)
    except ValueError:
        return 3600


def dynamic_keywords_enabled() -> bool:
    return os.getenv("ENABLE_DYNAMIC_KEYWORDS", "true").strip().lower() not in {"0", "false", "off", "no"}


class KeywordLoader:
    _global_cache = get_initial_keyword_cache()
    _global_loaded_at = 0.0
    _account_cache: dict[int, tuple[float, dict]] = {}

    @classmethod
    def base_cache(cls) -> dict:
        return deepcopy(get_initial_keyword_cache())

    @classmethod
    async def get_keywords_for_account(cls, account_id: int | None) -> dict:
        base = deepcopy(await cls._get_global_cache())
        if not dynamic_keywords_enabled() or not account_id:
            return base

        now = time.time()
        cached = cls._account_cache.get(account_id)
        if cached and now - cached[0] < _refresh_interval_seconds():
            return cls._merge_caches(base, cached[1])

        account_cache = await sync_to_async(cls._load_account_cache_sync, thread_sensitive=True)(account_id)
        cls._account_cache[account_id] = (now, account_cache)
        return cls._merge_caches(base, account_cache)

    @classmethod
    async def invalidate_account(cls, account_id: int | None):
        if account_id:
            cls._account_cache.pop(account_id, None)
        else:
            cls._global_loaded_at = 0.0

    @classmethod
    async def _get_global_cache(cls) -> dict:
        now = time.time()
        if now - cls._global_loaded_at < _refresh_interval_seconds():
            return deepcopy(cls._global_cache)

        global_cache = await sync_to_async(cls._load_global_cache_sync, thread_sensitive=True)()
        cls._global_cache = cls._merge_caches(get_initial_keyword_cache(), global_cache)
        cls._global_loaded_at = now
        return deepcopy(cls._global_cache)

    @classmethod
    def _load_global_cache_sync(cls) -> dict:
        if not dynamic_keywords_enabled():
            return cls.base_cache()
        entries = list(
            LearnedKeyword.objects.filter(account__isnull=True, is_active=True)
            .values("keyword", "category", "canonical", "canonical_payload")
        )
        return build_keyword_cache(entries)

    @classmethod
    def _load_account_cache_sync(cls, account_id: int) -> dict:
        entries = list(
            LearnedKeyword.objects.filter(account_id=account_id, is_active=True)
            .values("keyword", "category", "canonical", "canonical_payload")
        )
        return build_keyword_cache(entries)

    @classmethod
    def _merge_caches(cls, base: dict, overlay: dict) -> dict:
        merged = {
            "devices": set(base.get("devices", set())) | set(overlay.get("devices", set())),
            "rooms": set(base.get("rooms", set())) | set(overlay.get("rooms", set())),
            "controls": set(base.get("controls", set())) | set(overlay.get("controls", set())),
            "actions": set(base.get("actions", set())) | set(overlay.get("actions", set())),
            "colloquial": set(base.get("colloquial", set())) | set(overlay.get("colloquial", set())),
            "mapping": dict(base.get("mapping", {})),
            "payloads": dict(base.get("payloads", {})),
        }
        merged["mapping"].update(overlay.get("mapping", {}))
        merged["payloads"].update(overlay.get("payloads", {}))
        return merged
