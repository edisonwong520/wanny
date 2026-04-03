from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_register_default_schedules_includes_keyword_jobs(monkeypatch):
    monkeypatch.setenv("KEYWORD_REFRESH_INTERVAL", "3600")
    monkeypatch.setenv("KEYWORD_LEARNING_INTERVAL_USER", "21600")
    monkeypatch.setenv("KEYWORD_LEARNING_INTERVAL_GLOBAL", "86400")

    from scheduler import register_default_schedules

    scheduler = AsyncMock()

    await register_default_schedules(scheduler)

    added_ids = [call.kwargs["id"] for call in scheduler.add_schedule.await_args_list]

    assert "daily_memory_review" in added_ids
    assert "device_status_check" in added_ids
    assert "cleanup_expired_sessions" in added_ids
    assert "refresh_global_keyword_cache" in added_ids
    assert "run_user_keyword_learning" in added_ids
    assert "run_global_keyword_learning" in added_ids


def test_scheduler_keyword_interval_helpers_use_env(monkeypatch):
    monkeypatch.setenv("KEYWORD_REFRESH_INTERVAL", "120")
    monkeypatch.setenv("KEYWORD_LEARNING_INTERVAL_USER", "600")
    monkeypatch.setenv("KEYWORD_LEARNING_INTERVAL_GLOBAL", "7200")

    from scheduler.tasks import (
        keyword_learning_interval_global_seconds,
        keyword_learning_interval_user_seconds,
        keyword_refresh_interval_seconds,
    )

    assert keyword_refresh_interval_seconds() == 120
    assert keyword_learning_interval_user_seconds() == 600
    assert keyword_learning_interval_global_seconds() == 7200
