from __future__ import annotations


_current_bot = None


def set_current_bot(bot) -> None:
    global _current_bot
    _current_bot = bot


def get_current_bot():
    return _current_bot
