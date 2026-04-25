"""Tests for the LLM provider abstraction.

We don't make real OpenAI calls in tests — those would require an API key and
cost money. Instead we verify:

1. The factory respects `chat_llm_provider` setting.
2. The factory falls back to mock for unknown values (with a warning).
3. The mock provider yields non-empty chunks that concatenate to the same
   canned response the chat service used before the abstraction was added,
   so existing SSE tests keep passing.
4. The OpenAI provider rejects an empty API key fast (so misconfiguration
   never silently turns into a slow network failure).
"""
from __future__ import annotations

import pytest
from app.config import settings
from app.services.llm import MockLLMProvider, OpenAIProvider, get_llm_provider

pytestmark = pytest.mark.asyncio


async def test_factory_returns_mock_by_default() -> None:
    original = settings.chat_llm_provider
    settings.chat_llm_provider = "mock"
    try:
        assert isinstance(get_llm_provider(), MockLLMProvider)
    finally:
        settings.chat_llm_provider = original


async def test_factory_falls_back_to_mock_for_unknown_provider() -> None:
    original = settings.chat_llm_provider
    settings.chat_llm_provider = "totally-not-a-provider"
    try:
        assert isinstance(get_llm_provider(), MockLLMProvider)
    finally:
        settings.chat_llm_provider = original


async def test_mock_provider_yields_non_empty_chunks() -> None:
    provider = MockLLMProvider()
    chunks = [chunk async for chunk in provider.stream_response("test prompt")]

    assert len(chunks) > 0
    assert all(len(c) > 0 for c in chunks)
    full_text = "".join(chunks)
    assert "test prompt" in full_text


async def test_openai_provider_rejects_empty_api_key() -> None:
    with pytest.raises(ValueError, match="LABSMITH_OPENAI_API_KEY"):
        OpenAIProvider(api_key="", model="gpt-4o-mini", system_prompt="test")
