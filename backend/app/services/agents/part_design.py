"""Agent for `part_design` sessions.

This is the original M3/M4 chat orchestrator, lifted out of `chat.py` and
behind the `SessionAgent` protocol. Behavior, event catalog, and persistence
are unchanged from M4 — the move is purely structural so other session types
(onboarding, future agents) can coexist without forking the chat router.

Event catalog (matches the M3 contract):
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
from app.services.storage import artifact_storage_key, get_storage

logger = logging.getLogger(__name__)


class PartDesignAgent:
    """Generates lab hardware from natural-language prompts.

    Pipeline: stream text → rule-based parser → validation → CadQuery
    generation → persist artifact.
    """

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

        assistant_message_id = uuid.uuid4()

        # Persist the assistant Message row up-front so any later artifact rows
        # can FK-reference it. Content is filled in as we stream; everything
        # commits together at message_complete.
        assistant_msg = Message(
            id=assistant_message_id,
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content="",
            metadata_=None,
        )
        db.add(assistant_msg)
        await db.flush()

        # 1. Stream assistant text.
        assistant_text_chunks = _build_assistant_text_chunks(user_content)
        for chunk in assistant_text_chunks:
            yield {
                "event": "text_delta",
                "data": {
                    "message_id": str(assistant_message_id),
                    "delta": chunk,
                },
            }
            if settings.chat_mock:
                await asyncio.sleep(0.15)  # cosmetic pacing

        full_assistant_text = "".join(assistant_text_chunks)
        assistant_msg.content = full_assistant_text

        # 2. Parse the prompt into a structured PartRequest.
        part_request, parse_error = _parse_prompt(
            user_content,
            current_spec=session.current_spec,
        )
        if parse_error or part_request is None:
            assistant_msg.metadata_ = (
                {"parse_error": parse_error} if parse_error else None
            )
            yield {
                "event": "message_complete",
                "data": {
                    "message_id": str(assistant_message_id),
                    "content": full_assistant_text,
                },
            }
            await db.commit()
            return

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

        # Track inferred spec on the session.
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
            assistant_msg.metadata_ = {"validation_errors": validation_issues}
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
        assistant_msg.metadata_ = {"artifact_id": str(artifact.id)}
        yield {
            "event": "message_complete",
            "data": {
                "message_id": str(assistant_message_id),
                "content": full_assistant_text,
            },
        }
        await db.commit()


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

    generated_artifacts = await generate_cad_artifacts(part_request)
    generated = generated_artifacts[0]

    # Insert the artifact row first so we have a stable UUID for the storage key.
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
# Helpers (unchanged from M3/M4; kept private to this agent)
# ---------------------------------------------------------------------------


def _build_assistant_text_chunks(user_content: str) -> list[str]:
    response = (
        f'Here\'s what I extracted from your prompt: "{user_content[:80]}". '
        f"Parsing the parameters now and running validation. "
    )
    chunk_size = max(1, len(response) // 5)
    return [response[i : i + chunk_size] for i in range(0, len(response), chunk_size)]


def _parse_prompt(
    user_content: str,
    *,
    current_spec: dict[str, Any] | None = None,
) -> tuple[Any | None, str | None]:
    """Rule-based parser. M5 keeps it; structured-output LLM swap is a later
    optimization that doesn't change the agent's external behavior."""
    from labsmith.models import PartRequest
    from labsmith.parser import RuleBasedParser

    try:
        parser = RuleBasedParser()
        return parser.parse(user_content), None
    except ValueError as exc:
        if current_spec is None:
            return None, str(exc)

        try:
            previous_request = PartRequest.model_validate(current_spec)
            return parser.parse_update(user_content, previous_request), None
        except ValueError:
            return None, str(exc)


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
