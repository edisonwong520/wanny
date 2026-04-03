from __future__ import annotations

from comms.device_intent import should_check_device_intent
from comms.initial_keywords import normalize_keyword
from comms.keyword_loader import KeywordLoader


MULTI_INTENT_TOKENS = ("然后", "再", "并且", "andthen", "and", "then")
ENGLISH_SIGNALS = ("turn", "light", "lights", "bedroom", "livingroom", "please", "warmer", "cooler", "brighter", "dimmer")
QUERY_SIGNALS = ("query", "check", "status", "多少", "几度", "看看", "看下")
NORMALIZE_LENGTH_THRESHOLD = 28


def _count_matches(normalized: str, tokens) -> int:
    return sum(1 for token in tokens if token and token in normalized)


async def route_command(user_msg: str, *, account=None, command_mode: bool = False) -> dict:
    normalized = normalize_keyword(user_msg)
    keyword_cache = await KeywordLoader.get_keywords_for_account(getattr(account, "id", None))
    english_signal_count = _count_matches(normalized, ENGLISH_SIGNALS)
    colloquial_signal_count = _count_matches(normalized, keyword_cache["colloquial"])
    multi_intent_count = _count_matches(normalized, MULTI_INTENT_TOKENS)
    query_signal_count = _count_matches(normalized, QUERY_SIGNALS)
    has_device_signal = should_check_device_intent(user_msg, keyword_cache=keyword_cache)

    route = "skip_device"
    reason = "non_device"

    if command_mode and multi_intent_count:
        route = "needs_full_ai"
        reason = "command_mode_multi_intent"
    elif multi_intent_count:
        route = "needs_full_ai"
        reason = "multi_intent"
    elif not command_mode and not has_device_signal and colloquial_signal_count == 0:
        route = "skip_device"
        reason = "no_device_signal"
    elif english_signal_count >= 2:
        route = "needs_normalize"
        reason = "english_heavy"
    elif colloquial_signal_count >= 1 and not has_device_signal:
        route = "try_heuristic_then_normalize"
        reason = "colloquial_without_device_anchor"
    elif colloquial_signal_count >= 1:
        route = "try_heuristic_then_normalize"
        reason = "colloquial"
    elif len(normalized) >= NORMALIZE_LENGTH_THRESHOLD and has_device_signal:
        route = "try_heuristic_then_normalize"
        reason = "long_device_command"
    elif has_device_signal and query_signal_count:
        route = "standard"
        reason = "device_query_signal"
    elif has_device_signal:
        route = "try_heuristic"
        reason = "device_signal"
    elif command_mode:
        route = "try_heuristic"
        reason = "command_mode_default"

    return {
        "route": route,
        "reason": reason,
        "keyword_cache": keyword_cache,
        "signals": {
            "english": english_signal_count,
            "colloquial": colloquial_signal_count,
            "multi_intent": multi_intent_count,
            "query": query_signal_count,
            "has_device_signal": has_device_signal,
            "length": len(normalized),
        },
    }
