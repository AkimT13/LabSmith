"""Tests for the M7 spec extraction abstraction.

Real OpenAI calls aren't exercised — those need an API key. We mock the
OpenAI client with a fake to verify:

1. The factory respects `spec_extractor`.
2. The rule-based extractor parses fresh prompts and patches via
   `current_spec` for iterative phrases.
3. The OpenAI extractor parses well-formed JSON, rejects empty keys, and
   falls back to rule-based on any error.
4. `messages_to_chat_history` filters correctly.
"""
from __future__ import annotations

from typing import Any

import pytest
from app.config import settings
from app.services.spec_extraction import (
    OpenAIExtractor,
    RuleBasedExtractor,
    get_spec_extractor,
    messages_to_chat_history,
)
from labsmith.models import PartType

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


async def test_factory_returns_rule_based_by_default() -> None:
    original = settings.spec_extractor
    settings.spec_extractor = "rule_based"
    try:
        assert isinstance(get_spec_extractor(), RuleBasedExtractor)
    finally:
        settings.spec_extractor = original


async def test_factory_falls_back_to_rule_based_for_unknown_value() -> None:
    original = settings.spec_extractor
    settings.spec_extractor = "made_up_extractor"
    try:
        assert isinstance(get_spec_extractor(), RuleBasedExtractor)
    finally:
        settings.spec_extractor = original


# ---------------------------------------------------------------------------
# Rule-based extractor
# ---------------------------------------------------------------------------


async def test_rule_based_extractor_parses_fresh_prompt() -> None:
    extractor = RuleBasedExtractor()
    result = await extractor.extract(
        user_content="Create a 4 x 6 tube rack with 11 mm diameter and 15 mm spacing"
    )

    assert result.part_request is not None
    assert result.part_request.part_type == PartType.TUBE_RACK
    assert result.source == "rule_based"
    assert result.error is None


async def test_rule_based_extractor_returns_none_for_unparseable_prompt() -> None:
    extractor = RuleBasedExtractor()
    result = await extractor.extract(user_content="hello there")

    assert result.part_request is None
    assert result.source == "rule_based"
    assert result.error is not None


async def test_rule_based_extractor_uses_current_spec_for_iteration() -> None:
    """When the fresh-parse fails (no part-type keywords) but we have a
    current_spec, the extractor should fall through to parse_update so
    follow-ups patch the spec.

    Rule-based phrasing is limited — we use one of the parser's known
    keywords ('depth') here. The OpenAI extractor handles freer-form
    phrasing like 'make the wells deeper'; this test only verifies that
    the iteration code path is wired up correctly for rule-based.
    """
    extractor = RuleBasedExtractor()
    current_spec = {
        "part_type": "gel_comb",
        "well_count": 10,
        "well_width_mm": 5.0,
        "well_height_mm": 1.5,
        "depth_mm": 8.0,
        "notes": [],
    }
    result = await extractor.extract(
        user_content="depth of 12 mm",
        current_spec=current_spec,
    )

    assert result.part_request is not None
    assert result.part_request.part_type == PartType.GEL_COMB
    # Update should have been applied to the existing spec
    assert result.part_request.depth_mm == 12.0
    # And other fields preserved from the prior spec
    assert result.part_request.well_count == 10
    assert result.part_request.well_width_mm == 5.0


async def test_rule_based_extractor_defaults_short_dimension_reply_to_mm() -> None:
    extractor = RuleBasedExtractor()
    current_spec = {
        "part_type": "tube_rack",
        "rows": 4,
        "cols": 6,
        "well_count": 24,
        "diameter_mm": None,
        "spacing_mm": None,
        "depth_mm": None,
        "notes": [],
    }
    result = await extractor.extract(
        user_content="diameter is 11, tube height is 40",
        current_spec=current_spec,
    )

    assert result.part_request is not None
    assert result.source == "rule_based"
    assert result.error is None
    assert result.part_request.diameter_mm == 11.0
    assert result.part_request.spacing_mm == 15.0
    assert result.part_request.depth_mm == 40.0


# ---------------------------------------------------------------------------
# OpenAI extractor — uses a stubbed client to avoid real network calls
# ---------------------------------------------------------------------------


async def test_openai_extractor_rejects_empty_api_key() -> None:
    with pytest.raises(ValueError, match="LABSMITH_OPENAI_API_KEY"):
        OpenAIExtractor(api_key="", model="gpt-4o-mini")


async def test_openai_extractor_parses_valid_response() -> None:
    extractor = OpenAIExtractor(api_key="sk-test", model="gpt-4o-mini")
    extractor._client = _StubOpenAI(
        response_json='{"part_type": "tube_rack", "rows": 4, "cols": 6, '
        '"well_count": 24, "diameter_mm": 11, "spacing_mm": 15, "depth_mm": 40, '
        '"well_width_mm": null, "well_height_mm": null, "tube_volume_ml": null, '
        '"max_width_mm": null, "max_depth_mm": null, "max_height_mm": null, "notes": []}'
    )

    result = await extractor.extract(user_content="4x6 rack with 11mm tubes")

    assert result.part_request is not None
    assert result.part_request.part_type == PartType.TUBE_RACK
    assert result.part_request.rows == 4
    assert result.part_request.cols == 6
    assert result.source == "openai"


async def test_openai_extractor_returns_none_when_part_type_is_null() -> None:
    """LLM returning part_type=null means 'not a part-design request' —
    extractor should pass that through cleanly without falling back."""
    extractor = OpenAIExtractor(api_key="sk-test", model="gpt-4o-mini")
    extractor._client = _StubOpenAI(
        response_json='{"part_type": null, "rows": null, "cols": null, '
        '"well_count": null, "diameter_mm": null, "spacing_mm": null, '
        '"depth_mm": null, "well_width_mm": null, "well_height_mm": null, '
        '"tube_volume_ml": null, "max_width_mm": null, "max_depth_mm": null, '
        '"max_height_mm": null, "notes": []}'
    )

    result = await extractor.extract(user_content="hi how are you")

    assert result.part_request is None
    assert result.source == "openai"


async def test_openai_extractor_falls_back_on_network_error() -> None:
    """Any exception from OpenAI should fall back to rule-based, not crash."""
    extractor = OpenAIExtractor(api_key="sk-test", model="gpt-4o-mini")
    extractor._client = _FailingOpenAI()

    result = await extractor.extract(
        user_content="Create a 4 x 6 tube rack with 11 mm diameter and 15 mm spacing"
    )

    # The rule-based fallback should succeed on this prompt
    assert result.part_request is not None
    assert result.part_request.part_type == PartType.TUBE_RACK
    assert result.source == "openai_fallback_rule_based"


async def test_openai_extractor_falls_back_on_malformed_json() -> None:
    extractor = OpenAIExtractor(api_key="sk-test", model="gpt-4o-mini")
    extractor._client = _StubOpenAI(response_json="this is not json")

    # Use a rule-parseable prompt so the fallback succeeds — confirms the
    # malformed-JSON path actually goes through the fallback rather than
    # propagating the error.
    result = await extractor.extract(
        user_content="4 x 6 tube rack with 11 mm diameter, 15 mm spacing"
    )

    assert result.part_request is not None
    assert result.source == "openai_fallback_rule_based"


# ---------------------------------------------------------------------------
# History helper
# ---------------------------------------------------------------------------


async def test_messages_to_chat_history_filters_empty_and_system() -> None:
    msgs = [
        _FakeMessage("user", "hello"),
        _FakeMessage("assistant", ""),  # filtered (empty)
        _FakeMessage("system", "internal"),  # filtered (system)
        _FakeMessage("assistant", "hi there"),
        _FakeMessage("user", "how are you"),
    ]
    history = messages_to_chat_history(msgs)
    assert history == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
        {"role": "user", "content": "how are you"},
    ]


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class _StubOpenAI:
    """Fake AsyncOpenAI client. Returns a single completion with the supplied
    JSON string as content."""

    def __init__(self, *, response_json: str) -> None:
        self._response_json = response_json
        self.chat = _StubChat(response_json)


class _StubChat:
    def __init__(self, response_json: str) -> None:
        self.completions = _StubCompletions(response_json)


class _StubCompletions:
    def __init__(self, response_json: str) -> None:
        self._response_json = response_json

    async def create(self, **_: Any) -> Any:
        return _FakeCompletionResponse(self._response_json)


class _FakeCompletionResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessageContent(content)


class _FakeMessageContent:
    def __init__(self, content: str) -> None:
        self.content = content


class _FailingOpenAI:
    def __init__(self) -> None:
        self.chat = _FailingChat()


class _FailingChat:
    def __init__(self) -> None:
        self.completions = _FailingCompletions()


class _FailingCompletions:
    async def create(self, **_: Any) -> Any:
        raise RuntimeError("simulated network failure")


class _FakeMessage:
    """Minimal duck-typed Message for messages_to_chat_history tests."""

    def __init__(self, role: str, content: str) -> None:
        self.role = role
        self.content = content
