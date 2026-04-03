from __future__ import annotations

import asyncio
import os

from openai import AsyncOpenAI


NORMALIZER_PROMPT = """
你是智能家居指令标准化器。把用户口语化/英文/混合表达转为简洁的标准中文指令。

规则：
1. 输出必须是简洁中文，不超过20字
2. 只保留核心意图：动作 + 设备/房间 + 属性（如有）
3. 无法识别为设备指令时，输出原文不变
4. 只输出标准化结果，不要解释
""".strip()


def normalizer_enabled() -> bool:
    return os.getenv("ENABLE_COMMAND_NORMALIZER", "false").strip().lower() in {"1", "true", "on", "yes"}


class CommandNormalizer:
    @classmethod
    async def normalize(cls, user_msg: str) -> str:
        if not normalizer_enabled():
            return user_msg

        timeout_seconds = cls._timeout_seconds()
        try:
            return await asyncio.wait_for(cls._call_openai(user_msg), timeout=timeout_seconds)
        except Exception:
            return user_msg

    @classmethod
    async def _call_openai(cls, user_msg: str) -> str:
        base_url = os.getenv("NORMALIZER_BASE_URL") or os.getenv("AI_BASE_URL")
        api_key = os.getenv("NORMALIZER_API_KEY") or os.getenv("AI_API_KEY")
        model = os.getenv("NORMALIZER_MODEL") or os.getenv("AI_MODEL", "gpt-4o-mini")
        if not base_url or not api_key:
            return user_msg

        client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        response = await client.chat.completions.create(
            model=model,
            temperature=0.1,
            max_tokens=32,
            messages=[
                {"role": "system", "content": NORMALIZER_PROMPT},
                {"role": "user", "content": user_msg},
            ],
        )
        content = str(response.choices[0].message.content or "").strip()
        return content or user_msg

    @classmethod
    def _timeout_seconds(cls) -> float:
        try:
            return max(float(os.getenv("NORMALIZER_TIMEOUT_SECONDS", "3")), 0.1)
        except ValueError:
            return 3.0
