"""Chat orchestration service for M3 design sessions.

Produces an async stream of SSE-shaped event dicts. The router is responsible for
encoding them as `event: <type>\\ndata: <json>\\n\\n` and writing to the client.

The pipeline is split into pluggable parts:

- LLM streaming → `app/services/llm.py` (`MockLLMProvider` or `OpenAIProvider`).
  Selected by `LABSMITH_CHAT_LLM_PROVIDER` (default "mock").
- Spec extraction → `RuleBasedParser` from `labsmith.parser` (deterministic).
  Will be swapped for a structured-output LLM call in a later iteration.
- CAD generation → `_run_generation`. Currently writes a fake artifact row when
  `settings.chat_mock` is true; M5 will plug in real CadQuery here.

The M3 contract (`docs/M3_CONTRACT.md`) defines event ordering and payload shapes.
None of the swappable parts above change those guarantees.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.artifact import Artifact, ArtifactType
from app.models.design_session import DesignSession, SessionStatus
from app.models.lab_membership import LabRole
from app.services.llm import get_llm_provider
from app.models.message import Message, MessageRole
from app.models.user import User
from app.services.access import get_session_with_membership

logger = logging.getLogger(__name__)


async def prepare_chat_turn(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    user: User,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> tuple[DesignSession, Message]:
    """Run all preflight checks and persist the user message.

    Returns the (session, user_message) tuple. Raises HTTPException for any
    auth/state problem. This MUST be called before constructing a StreamingResponse
    so that errors (404/403/409) are returned as proper HTTP errors instead of
    being raised mid-stream after headers have already been sent.
    """
    design_session, _membership = await get_session_with_membership(
        db, session_id=session_id, user=user, minimum_role=LabRole.MEMBER
    )

    if design_session.status == SessionStatus.ARCHIVED:
        raise HTTPException(status_code=409, detail="Session is archived")

    user_msg = Message(
        session_id=design_session.id,
        role=MessageRole.USER,
        content=content,
        metadata_=metadata,
    )
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)
    return design_session, user_msg


async def stream_chat_turn(
    db: AsyncSession,
    *,
    design_session: DesignSession,
    user: User,
    user_content: str,
) -> AsyncGenerator[dict[str, Any], None]:
    """Run a single chat turn and yield SSE event dicts.

    Each yielded dict has shape `{"event": "<type>", "data": {<payload>}}`.
    The router encodes these as SSE wire format.

    Caller MUST have called `prepare_chat_turn()` first — this function assumes
    the user message is already persisted and the session is open.
    """
    # The assistant message ID is generated up front so all `text_delta` events
    # carry the same ID and the client can accumulate them under one bubble.
    assistant_message_id = uuid.uuid4()

    try:
        async for event in _orchestrate(
            db,
            design_session=design_session,
            user=user,
            user_content=user_content,
            assistant_message_id=assistant_message_id,
        ):
            yield event
    except Exception as exc:  # noqa: BLE001 — convert to error event
        logger.exception("Chat turn failed: %s", exc)
        yield {
            "event": "error",
            "data": {"code": "internal_error", "detail": str(exc)},
        }


async def _orchestrate(
    db: AsyncSession,
    *,
    design_session: DesignSession,
    user: User,
    user_content: str,
    assistant_message_id: uuid.UUID,
) -> AsyncGenerator[dict[str, Any], None]:
    """Inner orchestration. Split out so `stream_chat_turn` can wrap with error handling."""
    # Persist the assistant Message row up-front so any later artifact rows can
    # safely reference it via FK. The content starts empty and is filled in at
    # message_complete; everything is committed at the very end.
    assistant_msg = Message(
        id=assistant_message_id,
        session_id=design_session.id,
        role=MessageRole.ASSISTANT,
        content="",
        metadata_=None,
    )
    db.add(assistant_msg)
    await db.flush()  # write the placeholder so artifact FKs resolve

    # 2. Stream assistant text. The provider abstraction (app/services/llm.py)
    # decides whether this is the canned mock response or a real OpenAI stream.
    # Either way, each yielded chunk becomes a `text_delta` event.
    provider = get_llm_provider()
    assistant_text_chunks: list[str] = []
    async for chunk in provider.stream_response(user_content):
        assistant_text_chunks.append(chunk)
        yield {
            "event": "text_delta",
            "data": {"message_id": str(assistant_message_id), "delta": chunk},
        }

    # 3. Parse the prompt into a structured PartRequest. The rule-based parser
    # doesn't need the assistant text — it works directly off user input.
    part_request, parse_error = _parse_prompt(user_content)

    full_assistant_text = "".join(assistant_text_chunks)
    assistant_msg.content = full_assistant_text

    if parse_error or part_request is None:
        # No spec extractable. Finalize the message and wrap up.
        assistant_msg.metadata_ = {"parse_error": parse_error} if parse_error else None
        yield {
            "event": "message_complete",
            "data": {"message_id": str(assistant_message_id), "content": full_assistant_text},
        }
        await db.commit()
        return

    # 4. Validate.
    validation_issues = _validate_part_request(part_request)
    has_errors = any(issue["severity"] == "error" for issue in validation_issues)

    yield {
        "event": "spec_parsed",
        "data": {
            "part_request": _serialize_part_request(part_request),
            "validation": validation_issues,
        },
    }

    # Update session.current_spec to track what we've inferred.
    design_session.current_spec = _serialize_part_request(part_request)
    design_session.part_type = part_request.part_type.value

    if has_errors:
        # Skip generation if there are validation errors; finalize the message.
        assistant_msg.metadata_ = {"validation_errors": validation_issues}
        yield {
            "event": "message_complete",
            "data": {"message_id": str(assistant_message_id), "content": full_assistant_text},
        }
        await db.commit()
        return

    # 5. Generation phase.
    template_name = part_request.part_type.value
    yield {
        "event": "generation_started",
        "data": {"template": template_name},
    }

    artifact = await _run_generation(
        db,
        design_session=design_session,
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

    # 6. Finalize the assistant message metadata and commit everything together.
    assistant_msg.metadata_ = {"artifact_id": str(artifact.id)}
    yield {
        "event": "message_complete",
        "data": {"message_id": str(assistant_message_id), "content": full_assistant_text},
    }
    await db.commit()


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


async def _run_generation(
    db: AsyncSession,
    *,
    design_session: DesignSession,
    part_request: Any,
    validation_issues: list[dict[str, Any]],
    message_id: uuid.UUID,
) -> Artifact:
    """Run the CAD pipeline (or mock it) and persist an Artifact row.

    In mock mode we don't write real bytes — `file_path` is None and `file_size_bytes`
    is a synthetic number. The frontend can still render the artifact list, and M4
    will fill in real STL bytes via CadQuery.
    """
    # Determine next version for this session.
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

    artifact = Artifact(
        session_id=design_session.id,
        message_id=message_id,
        artifact_type=ArtifactType.STL,
        file_path=None,
        file_size_bytes=12345 if settings.chat_mock else None,
        spec_snapshot=_serialize_part_request(part_request),
        validation={"issues": validation_issues},
        version=next_version,
    )
    db.add(artifact)
    await db.flush()  # populate artifact.id without committing the parent transaction
    await db.refresh(artifact)
    return artifact


# ---------------------------------------------------------------------------
# Spec parsing + validation wrappers (rule-based today; structured-output LLM
# call in a later iteration). LLM streaming for the assistant reply lives in
# `app/services/llm.py`.
# ---------------------------------------------------------------------------


def _parse_prompt(user_content: str) -> tuple[Any | None, str | None]:
    """Parse a prompt into a PartRequest using the existing rule-based parser.

    Returns (part_request, None) on success, or (None, error_message) on failure.
    """
    from labsmith.parser import RuleBasedParser

    try:
        parser = RuleBasedParser()
        return parser.parse(user_content), None
    except ValueError as exc:
        return None, str(exc)


def _validate_part_request(part_request: Any) -> list[dict[str, Any]]:
    """Run the existing validation rules and return JSON-shaped issues."""
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
    """Convert the existing Pydantic PartRequest into a plain dict for transport."""
    return part_request.model_dump(mode="json")
