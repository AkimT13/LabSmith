"""Agent for `part_design` sessions.

Pipeline: stream assistant text → extract a structured `PartRequest` →
validate → run CadQuery → persist artifact.

The streaming text and parameter extraction are both pluggable as of M7:

- Assistant text comes from `app/services/llm.py::get_llm_provider()` —
  mock by default (canned response, no key needed) or OpenAI when
  `LABSMITH_CHAT_LLM_PROVIDER=openai`.
- Parameter extraction comes from
  `app/services/spec_extraction.py::get_spec_extractor()` — rule-based
  regex by default or OpenAI structured-output when
  `LABSMITH_SPEC_EXTRACTOR=openai`. The OpenAI extractor reads
  `session.current_spec` and the recent message history so iterative
  phrases like "make the wells deeper" patch the existing spec instead of
  re-parsing from scratch. It falls back to the rule-based parser on any
  failure, so a misconfigured key never crashes a chat turn.

CadQuery generation lives in `app/services/cad_generation.py` and lands
real STL bytes via `_run_generation` below.

Event catalog (matches the M3/M4/M5 contract):
    text_delta            (0..N)
    spec_parsed           (0..1, only if a spec was parseable)
    generation_started    (0..1, only if validation passed)
    generation_complete   (0..1, only if generation succeeded)
    message_complete      (1, always)
    error                 (handled by the dispatcher, not the agent)
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.artifact import Artifact
from app.models.design_session import DesignSession, SessionType
from app.models.message import Message, MessageRole
from app.models.user import User
from app.services.agents.base import AgentEvent
from app.services.cad_generation import generate_cad_artifacts
from app.services.llm import get_llm_provider
from app.services.spec_extraction import (
    ExtractionResult,
    get_spec_extractor,
    messages_to_chat_history,
)
from app.services.storage import artifact_storage_key, get_storage

logger = logging.getLogger(__name__)


class PartDesignAgent:
    """Generates lab hardware from natural-language prompts."""

    session_type = SessionType.PART_DESIGN

    async def run_turn(
        self,
        *,
        db: AsyncSession,
        session: DesignSession,
        user: User,
        user_content: str,
    ) -> AsyncGenerator[AgentEvent, None]:
        loaded_session = await db.get(DesignSession, session.id)
        if loaded_session is not None:
            session = loaded_session

        # Snapshot prior conversation history BEFORE we add the assistant
        # placeholder — that way the extractor sees a clean record of past
        # turns without the in-flight empty assistant message. We also drop
        # the most recent user message because it's already passed as
        # `user_content` (and the OpenAI chat format prefers the current
        # message be separate from history).
        prior_history = await _load_prior_chat_history(
            db, session_id=session.id, exclude_latest_user_message=True
        )

        assistant_message_id = uuid.uuid4()
        assistant_msg = Message(
            id=assistant_message_id,
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content="",
            metadata_=None,
        )
        db.add(assistant_msg)
        await db.flush()

        # 1. Stream assistant text via the active LLM provider. Mock by default.
        provider = get_llm_provider()
        assistant_text_chunks: list[str] = []
        async for chunk in provider.stream_response(user_content):
            assistant_text_chunks.append(chunk)
            yield {
                "event": "text_delta",
                "data": {
                    "message_id": str(assistant_message_id),
                    "delta": chunk,
                },
            }

        full_assistant_text = "".join(assistant_text_chunks)
        assistant_msg.content = full_assistant_text

        # 2. Extract a structured PartRequest. Pluggable: rule-based (default)
        # or OpenAI structured outputs.
        extractor = get_spec_extractor()
        extraction = await extractor.extract(
            user_content=user_content,
            current_spec=session.current_spec,
            message_history=prior_history,
        )

        if extraction.part_request is None:
            assistant_msg.metadata_ = _metadata_for_failed_extraction(extraction)
            yield {
                "event": "message_complete",
                "data": {
                    "message_id": str(assistant_message_id),
                    "content": full_assistant_text,
                },
            }
            await db.commit()
            return

        part_request = extraction.part_request

        # 3. Validate.
        validation_issues = _validate_part_request(part_request)
        has_errors = any(issue["severity"] == "error" for issue in validation_issues)

        yield {
            "event": "spec_parsed",
            "data": {
                "part_request": _serialize_part_request(part_request),
                "validation": validation_issues,
            },
        }

        # Track inferred spec on the session so the next turn's extractor sees it.
        session.current_spec = _serialize_part_request(part_request)
        session.part_type = part_request.part_type.value

        if has_errors:
            clarification = _build_validation_follow_up(validation_issues)
            if clarification:
                full_assistant_text = f"{full_assistant_text}{clarification}"
                assistant_msg.content = full_assistant_text
                yield {
                    "event": "text_delta",
                    "data": {
                        "message_id": str(assistant_message_id),
                        "delta": clarification,
                    },
                }
            assistant_msg.metadata_ = {
                "validation_errors": validation_issues,
                "extraction_source": extraction.source,
            }
            yield {
                "event": "message_complete",
                "data": {
                    "message_id": str(assistant_message_id),
                    "content": full_assistant_text,
                },
            }
            await db.commit()
            return

        # 4. Generation phase.
        template_name = part_request.part_type.value
        yield {
            "event": "generation_started",
            "data": {"template": template_name},
        }

        artifact = await _run_generation(
            db,
            design_session=session,
            part_request=part_request,
            validation_issues=validation_issues,
            message_id=assistant_message_id,
        )

        yield {
            "event": "generation_complete",
            "data": {
                "artifact_id": str(artifact.id),
                "artifact_type": artifact.artifact_type.value,
                "file_size_bytes": artifact.file_size_bytes,
                "version": artifact.version,
            },
        }

        # 5. Finalize and commit.
        assistant_msg.metadata_ = {
            "artifact_id": str(artifact.id),
            "extraction_source": extraction.source,
        }
        yield {
            "event": "message_complete",
            "data": {
                "message_id": str(assistant_message_id),
                "content": full_assistant_text,
            },
        }
        await db.commit()


# ---------------------------------------------------------------------------
# History helper
# ---------------------------------------------------------------------------


async def _load_prior_chat_history(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    exclude_latest_user_message: bool,
) -> list[dict[str, str]]:
    """Load past chat turns for use as LLM context.

    `prepare_chat_turn()` has already persisted the current user message,
    so when `exclude_latest_user_message=True` we trim the most-recent
    user row off the history (it'll be passed separately as `user_content`).
    """
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
    )
    rows = list(result.scalars().all())
    if exclude_latest_user_message and rows and rows[-1].role == MessageRole.USER:
        rows = rows[:-1]
    return messages_to_chat_history(rows)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


async def _run_generation(
    db: AsyncSession,
    *,
    design_session: DesignSession,
    part_request: Any,
    validation_issues: list[dict[str, Any]],
    message_id: uuid.UUID,
) -> Artifact:
    """Run the CAD pipeline and persist the generated artifact row."""
    result = await db.execute(
        select(Artifact.version)
        .where(Artifact.session_id == design_session.id)
        .order_by(desc(Artifact.version))
        .limit(1)
    )
    last_version = result.scalar_one_or_none()
    next_version = (last_version or 0) + 1

    if settings.chat_mock:
        await asyncio.sleep(0.4)  # cosmetic delay so client sees a "generating" phase

    generated_artifacts = await generate_cad_artifacts(part_request)
    generated = generated_artifacts[0]

    artifact = Artifact(
        session_id=design_session.id,
        message_id=message_id,
        artifact_type=generated.artifact_type,
        file_path=None,
        file_size_bytes=None,
        spec_snapshot=_serialize_part_request(part_request),
        validation={"issues": validation_issues},
        version=next_version,
    )
    db.add(artifact)
    await db.flush()
    await db.refresh(artifact)

    storage = get_storage()
    key = artifact_storage_key(
        session_id=str(design_session.id),
        artifact_id=str(artifact.id),
        version=next_version,
        extension=generated.extension,
    )
    stored = await storage.save(key, generated.data, content_type=generated.content_type)
    artifact.file_path = stored.key
    artifact.file_size_bytes = stored.size_bytes
    await db.flush()
    await db.refresh(artifact)
    return artifact


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _metadata_for_failed_extraction(extraction: ExtractionResult) -> dict[str, Any]:
    metadata: dict[str, Any] = {"extraction_source": extraction.source}
    if extraction.error:
        metadata["parse_error"] = extraction.error
    return metadata


def _validate_part_request(part_request: Any) -> list[dict[str, Any]]:
    from labsmith.validation import validate_part_request

    issues = validate_part_request(part_request)
    return [
        {
            "severity": issue.severity.value,
            "code": issue.code,
            "message": issue.message,
            "field": issue.field,
        }
        for issue in issues
    ]


def _serialize_part_request(part_request: Any) -> dict[str, Any]:
    return part_request.model_dump(mode="json")


def _build_validation_follow_up(validation_issues: list[dict[str, Any]]) -> str:
    missing_questions = [
        issue["message"]
        for issue in validation_issues
        if issue["severity"] == "error" and issue["code"] == "missing_parameter"
    ]
    if not missing_questions:
        return ""
    return " I need one more detail before generating: " + " ".join(missing_questions)
