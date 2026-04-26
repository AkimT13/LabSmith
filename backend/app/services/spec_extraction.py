"""Structured-output parameter extraction for part-design sessions.

The job here is the same as `RuleBasedParser.parse()` from M3 — turn a user's
free-form prompt into a `PartRequest` — but powered by an LLM so prompts like
"I need a rack that fits 50mL Falcon tubes" actually work, and follow-ups like
"make the wells deeper" patch the existing spec instead of re-parsing from
scratch.

Two extractors ship:

- `RuleBasedExtractor` — wraps the existing regex parser. Fast, deterministic,
  zero network calls, no API key needed. Default selection.
- `OpenAIExtractor` — sends prompt + `current_spec` + recent message history
  to OpenAI with a JSON-schema response format that mirrors `PartRequest`.
  Falls back to `RuleBasedExtractor` on any failure (network error, malformed
  JSON, validation error) so a misconfigured LLM never crashes a chat turn.

The agent never imports an extractor class directly — it always goes through
`get_spec_extractor()`. Adding a new backend is one class + a branch in the
factory.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from labsmith.models import PartRequest, PartType
from labsmith.parser import RuleBasedParser

from app.config import settings

logger = logging.getLogger(__name__)


class ExtractionResult:
    """Outcome of one extraction attempt.

    `part_request` is None if no part type could be identified (free-form
    chat that isn't asking for a part). `source` records which extractor
    actually produced the result so we can surface that to logs/metadata —
    useful when the OpenAI extractor falls back to rule-based.
    """

    __slots__ = ("part_request", "source", "error")

    def __init__(
        self,
        part_request: PartRequest | None,
        source: str,
        error: str | None = None,
    ) -> None:
        self.part_request = part_request
        self.source = source
        self.error = error


class SpecExtractor(Protocol):
    """Pulls a `PartRequest` out of natural language."""

    name: str

    async def extract(
        self,
        *,
        user_content: str,
        current_spec: dict[str, Any] | None = None,
        message_history: list[dict[str, str]] | None = None,
    ) -> ExtractionResult: ...


# ---------------------------------------------------------------------------
# Rule-based extractor — wraps the existing regex parser.
# ---------------------------------------------------------------------------


class RuleBasedExtractor:
    """The M3 regex parser, adapted to the extractor protocol.

    Uses `parser.parse_update()` when `current_spec` is set so iterative phrases
    like "make the wells deeper" patch the existing spec instead of failing the
    initial part-type detection. Falls back to a fresh parse if the update path
    isn't applicable. Ignores `message_history` — only the current prompt and
    the prior spec matter for regex-based parsing.
    """

    name = "rule_based"

    async def extract(
        self,
        *,
        user_content: str,
        current_spec: dict[str, Any] | None = None,
        message_history: list[dict[str, str]] | None = None,
    ) -> ExtractionResult:
        parser = RuleBasedParser()
        # First try a fresh parse. If the user is starting a new request,
        # this is the right path.
        try:
            part_request = parser.parse(user_content)
            return ExtractionResult(part_request=part_request, source=self.name)
        except ValueError as exc:
            initial_error = str(exc)

        # Fresh parse failed — if we have a current spec, the user may be
        # iterating on it ("make the wells deeper"). Try the update path.
        if current_spec is not None:
            try:
                previous_request = PartRequest.model_validate(current_spec)
                updated = parser.parse_update(user_content, previous_request)
                return ExtractionResult(part_request=updated, source=self.name)
            except Exception:
                pass

        return ExtractionResult(
            part_request=None, source=self.name, error=initial_error
        )


# ---------------------------------------------------------------------------
# OpenAI extractor — structured outputs + history + iterative refinement.
# ---------------------------------------------------------------------------


# Hand-written JSON schema that mirrors `PartRequest`. We don't auto-generate
# from Pydantic because OpenAI's strict structured-output mode rejects some
# things Pydantic emits (anyOf with null, defaults, etc.), and we want full
# control over field descriptions that the model actually reads.
_PART_REQUEST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "part_type",
        "rows",
        "cols",
        "well_count",
        "diameter_mm",
        "spacing_mm",
        "depth_mm",
        "well_width_mm",
        "well_height_mm",
        "tube_volume_ml",
        "notes",
    ],
    "properties": {
        "part_type": {
            "type": ["string", "null"],
            "enum": [pt.value for pt in PartType] + [None],
            "description": (
                "What kind of lab part the user is describing. Return null if "
                "the message is small talk, a question, or otherwise not a "
                "part-design request."
            ),
        },
        "rows": {
            "type": ["integer", "null"],
            "description": "Number of rows in a grid layout (tube_rack).",
        },
        "cols": {
            "type": ["integer", "null"],
            "description": "Number of columns in a grid layout (tube_rack).",
        },
        "well_count": {
            "type": ["integer", "null"],
            "description": (
                "Total well/tooth count. For grids, set rows*cols and leave "
                "this null — it will be auto-computed."
            ),
        },
        "diameter_mm": {
            "type": ["number", "null"],
            "description": "Hole diameter in millimeters (tube_rack).",
        },
        "spacing_mm": {
            "type": ["number", "null"],
            "description": "Distance between hole centers in millimeters.",
        },
        "depth_mm": {
            "type": ["number", "null"],
            "description": (
                "Vertical depth of the feature in millimeters. For tube_rack "
                "this is the rack height; for gel_comb this is tooth depth."
            ),
        },
        "well_width_mm": {
            "type": ["number", "null"],
            "description": "Tooth width in millimeters (gel_comb).",
        },
        "well_height_mm": {
            "type": ["number", "null"],
            "description": "Tooth thickness in millimeters (gel_comb).",
        },
        "tube_volume_ml": {
            "type": ["number", "null"],
            "description": (
                "Hint when the user describes their tubes by volume (e.g. "
                "'1.5 mL', '50 mL Falcon'). Used to infer diameter if it isn't "
                "given explicitly."
            ),
        },
        "notes": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Any assumptions you made or context worth surfacing to the "
                "user (e.g. 'Defaulted spacing to 15 mm based on tube "
                "diameter'). Empty list if nothing to note."
            ),
        },
    },
}


_EXTRACTION_SYSTEM_PROMPT = (
    "You extract structured laboratory part specs from natural language for "
    "LabSmith.\n"
    "\n"
    "Supported part types right now: tube_rack, gel_comb. multi_well_mold and "
    "microfluidic_channel_mold are valid identifiers but no CAD generator "
    "exists for them — return them only if the user clearly asks for one, "
    "and the system will tell them it's not yet supported.\n"
    "\n"
    "Iterative refinement: when a `current_spec` is provided, the user is "
    "almost always editing it ('make the wells deeper', 'add two more rows', "
    "'change to 1.5 mL tubes'). Start from the current spec and apply the "
    "user's delta. Keep all fields the user didn't mention.\n"
    "\n"
    "If the user is not asking for a part at all (small talk, a question "
    "about an earlier reply, etc.), return part_type=null and leave all "
    "other fields null.\n"
    "\n"
    "Units: every dimension is millimeters unless the user uses a different "
    "unit, in which case convert. Tube volumes stay in mL.\n"
    "\n"
    "Use the `notes` field to record any assumption you made — short, "
    "conversational, written for the user."
)


class OpenAIExtractor:
    """Structured-output extraction via OpenAI's JSON-schema response format.

    Falls back to `RuleBasedExtractor` on any failure (network error, malformed
    response, validation error). The fallback is best-effort: if the rule-based
    parser also fails we return a clean `ExtractionResult(None, ...)` so the
    chat turn ends gracefully at `message_complete` instead of crashing.
    """

    name = "openai"

    def __init__(self, *, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError(
                "LABSMITH_OPENAI_API_KEY must be set when spec_extractor=openai"
            )
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RuntimeError(
                "openai package not installed. Run `pip install openai>=1.30` or "
                "switch spec_extractor back to 'rule_based'."
            ) from exc

        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._fallback = RuleBasedExtractor()

    async def extract(
        self,
        *,
        user_content: str,
        current_spec: dict[str, Any] | None = None,
        message_history: list[dict[str, str]] | None = None,
    ) -> ExtractionResult:
        try:
            return await self._extract_via_openai(
                user_content=user_content,
                current_spec=current_spec,
                message_history=message_history,
            )
        except Exception as exc:
            logger.warning(
                "OpenAI extraction failed (%s); falling back to rule-based parser",
                exc,
            )
            fallback = await self._fallback.extract(user_content=user_content)
            # Tag the source so logs/metadata can tell apart "OpenAI succeeded"
            # from "OpenAI failed and rule-based covered it".
            return ExtractionResult(
                part_request=fallback.part_request,
                source=f"{self.name}_fallback_rule_based",
                error=fallback.error,
            )

    async def _extract_via_openai(
        self,
        *,
        user_content: str,
        current_spec: dict[str, Any] | None,
        message_history: list[dict[str, str]] | None,
    ) -> ExtractionResult:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT}
        ]
        if current_spec is not None:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "current_spec (the user's existing part — patch it "
                        "rather than re-parsing from scratch):\n"
                        f"{json.dumps(current_spec, indent=2)}"
                    ),
                }
            )
        # Cap history at the last 8 turns (16 messages) to keep tokens bounded.
        if message_history:
            messages.extend(message_history[-16:])
        messages.append({"role": "user", "content": user_content})

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "part_request",
                    "schema": _PART_REQUEST_SCHEMA,
                    "strict": True,
                },
            },
        )

        raw = response.choices[0].message.content
        if not raw:
            return ExtractionResult(
                part_request=None,
                source=self.name,
                error="OpenAI returned empty content",
            )

        data = json.loads(raw)

        if data.get("part_type") is None:
            return ExtractionResult(part_request=None, source=self.name)

        # Drop nulls so the Pydantic defaults kick in correctly.
        cleaned = {k: v for k, v in data.items() if v is not None}
        cleaned["source_prompt"] = user_content

        try:
            part_request = PartRequest(**cleaned)
        except Exception as exc:
            logger.warning("OpenAI returned an invalid PartRequest: %s", exc)
            raise

        return ExtractionResult(part_request=part_request, source=self.name)


# ---------------------------------------------------------------------------
# Factory + history helper
# ---------------------------------------------------------------------------


def get_spec_extractor() -> SpecExtractor:
    extractor_name = (settings.spec_extractor or "rule_based").lower()

    if extractor_name == "openai":
        return OpenAIExtractor(
            api_key=settings.openai_api_key,
            model=settings.openai_extraction_model,
        )

    if extractor_name != "rule_based":
        logger.warning(
            "Unknown spec_extractor=%r; falling back to rule_based", extractor_name
        )

    return RuleBasedExtractor()


def messages_to_chat_history(messages: list[Any]) -> list[dict[str, str]]:
    """Convert ORM Message rows into OpenAI chat-history format.

    Drops system messages (the extractor has its own system prompt) and any
    messages with empty content. Keeps the chronological order.
    """
    out: list[dict[str, str]] = []
    for msg in messages:
        role = getattr(msg, "role", None)
        content = getattr(msg, "content", None)
        if not content:
            continue
        # Coerce enum -> string if needed
        role_value = getattr(role, "value", role)
        if role_value not in ("user", "assistant"):
            continue
        out.append({"role": role_value, "content": content})
    return out
