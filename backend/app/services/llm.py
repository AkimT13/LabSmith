"""LLM provider abstraction for the M3 chat pipeline.

Two providers ship today:

- `MockLLMProvider` — deterministic canned response, no network calls. Used by
  tests and by default-configured dev installs. Behavior matches what the chat
  service did before this abstraction existed, so the M3 contract surface is
  unchanged.
- `OpenAIProvider` — streams from OpenAI's Chat Completions API. Requires
  `LABSMITH_OPENAI_API_KEY`. Selected via `LABSMITH_CHAT_LLM_PROVIDER=openai`.

Adding a new provider is a matter of writing a class that implements
`stream_response()` and registering it in `get_llm_provider()`. The chat
orchestrator never imports a provider directly — it always goes through
`get_llm_provider()` so the rest of M3 is provider-agnostic.

The contract guarantee both providers must uphold: `stream_response(prompt)`
returns an async iterator of non-empty text chunks. Order matters; the chat
router concatenates them into the assistant message's final `content`.
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
    """Deterministic canned response. No network calls, no API key needed.

    Used by tests so the SSE pipeline can be exercised end-to-end without
    requiring an OpenAI account. Matches the response shape the chat service
    used before the provider abstraction existed, so test fixtures and golden
    SSE traces remain stable.
    """

    async def stream_response(self, user_content: str) -> AsyncIterator[str]:
        response = (
            f'Here\'s what I extracted from your prompt: "{user_content[:80]}". '
            f"Parsing the parameters now and running validation. "
        )
        chunk_size = max(1, len(response) // 5)
        for i in range(0, len(response), chunk_size):
            yield response[i : i + chunk_size]
            # Cosmetic pacing so the frontend can verify chunk-by-chunk rendering.
            await asyncio.sleep(0.15)


# ---------------------------------------------------------------------------
# OpenAI provider — real LLM streaming.
# ---------------------------------------------------------------------------


class OpenAIProvider:
    """Streams from OpenAI's Chat Completions API.

    The `openai` SDK is imported lazily inside `__init__` so installs without
    that extra package don't pay an import cost just because this module is
    imported. Requires `LABSMITH_OPENAI_API_KEY`. The model is configurable
    via `LABSMITH_OPENAI_MODEL` (default `gpt-4o-mini`).
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
            logger.exception("OpenAI request failed")
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
            model=settings.openai_model,
            system_prompt=settings.openai_system_prompt,
        )

    if provider_name != "mock":
        logger.warning(
            "Unknown chat_llm_provider=%r; falling back to mock", provider_name
        )

    return MockLLMProvider()
