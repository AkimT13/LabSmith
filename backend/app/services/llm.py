"""LLM provider abstraction for assistant text streaming.

Two providers ship today:

- `MockLLMProvider` — deterministic canned response, no network calls. Default
  selection so tests and key-less dev environments work out of the box.
- `OpenAIProvider` — streams from OpenAI's Chat Completions API. Requires
  `LABSMITH_OPENAI_API_KEY`. Selected via `LABSMITH_CHAT_LLM_PROVIDER=openai`.

Adding a new provider is a class implementing `stream_response()` plus a branch
in `get_llm_provider()`. The chat orchestrator never imports a provider class
directly — it always goes through `get_llm_provider()`.

The contract every provider must uphold: `stream_response(prompt)` is an async
iterator of non-empty text chunks. Order matters; the agent concatenates them
into the assistant message's final `content`.

Note: structured parameter extraction is NOT here — see `spec_extraction.py`.
This module is purely about producing the conversational reply users read.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Protocol

from app.config import settings

logger = logging.getLogger(__name__)


class LLMProvider(Protocol):
    """Streams the assistant's text reply chunk-by-chunk."""

    async def stream_response(self, user_content: str) -> AsyncIterator[str]:
        """Yield non-empty text chunks for the assistant response."""
        ...


# ---------------------------------------------------------------------------
# Mock provider — used by tests and as the safe default.
# ---------------------------------------------------------------------------


class MockLLMProvider:
    """Deterministic canned response. No network calls, no API key needed."""

    async def stream_response(self, user_content: str) -> AsyncIterator[str]:
        response = (
            f'Got it — looking at "{user_content[:80]}". '
            f"Extracting the parameters now and running validation. "
        )
        chunk_size = max(1, len(response) // 5)
        for i in range(0, len(response), chunk_size):
            yield response[i : i + chunk_size]
            # Cosmetic pacing so the frontend sees chunk-by-chunk rendering.
            await asyncio.sleep(0.15)


# ---------------------------------------------------------------------------
# OpenAI provider — real LLM streaming.
# ---------------------------------------------------------------------------


class OpenAIProvider:
    """Streams from OpenAI's Chat Completions API.

    The `openai` SDK is imported lazily inside `__init__` so importing this
    module never crashes when the SDK is missing — it only matters when the
    provider is actually selected. Requires `LABSMITH_OPENAI_API_KEY`.
    """

    def __init__(self, *, api_key: str, model: str, system_prompt: str) -> None:
        if not api_key:
            raise ValueError(
                "LABSMITH_OPENAI_API_KEY must be set when chat_llm_provider=openai"
            )
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RuntimeError(
                "openai package not installed. Run `pip install openai>=1.30` or "
                "switch chat_llm_provider back to 'mock'."
            ) from exc

        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._system_prompt = system_prompt

    async def stream_response(self, user_content: str) -> AsyncIterator[str]:
        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": user_content},
                ],
                stream=True,
            )
        except Exception:
            logger.exception("OpenAI chat-completion request failed")
            raise

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_llm_provider() -> LLMProvider:
    """Resolve the active provider from settings.

    Defaults to `MockLLMProvider` for safety — `chat_llm_provider` must be
    explicitly set to "openai" to enable network calls.
    """
    provider_name = (settings.chat_llm_provider or "mock").lower()

    if provider_name == "openai":
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_chat_model,
            system_prompt=settings.openai_chat_system_prompt,
        )

    if provider_name != "mock":
        logger.warning(
            "Unknown chat_llm_provider=%r; falling back to mock", provider_name
        )

    return MockLLMProvider()
