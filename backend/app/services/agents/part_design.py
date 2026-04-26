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
from app.models.project import Project
from app.models.user import User
from app.services.agents.base import AgentEvent
from app.services.cad_generation import generate_cad_artifacts
from app.services.devices import submit_print_job
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

        # 0. LabSmith Device Protocol — short-circuit on a "print this" intent
        # BEFORE the LLM streams anything. If we let the LLM run first, it
        # responds to "print this" as if it were a fresh design request
        # ("describe what you'd like to create…"), which then collides with
        # the dispatch confirmation. By branching first we own the entire
        # assistant message for print intents.
        intent = _parse_print_intent(user_content)
        if intent is not None:
            print_event, reply_text = await _handle_print_intent(
                db, session=session, user=user, intent=intent
            )
            assistant_msg.content = reply_text
            yield {
                "event": "text_delta",
                "data": {
                    "message_id": str(assistant_message_id),
                    "delta": reply_text,
                },
            }
            yield print_event
            assistant_msg.metadata_ = {
                "print_event": print_event["event"],
                "device_id": print_event["data"].get("device_id"),
                "job_ids": print_event["data"].get("job_ids", []),
                "copies_requested": intent.copies,
                "version_requested": intent.version,
            }
            yield {
                "event": "message_complete",
                "data": {
                    "message_id": str(assistant_message_id),
                    "content": reply_text,
                },
            }
            await db.commit()
            return

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
            follow_up = _build_extraction_follow_up(extraction)
            if follow_up:
                full_assistant_text = f"{full_assistant_text}{follow_up}"
                assistant_msg.content = full_assistant_text
                yield {
                    "event": "text_delta",
                    "data": {
                        "message_id": str(assistant_message_id),
                        "delta": follow_up,
                    },
                }
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
        printability_report = _build_printability_report(part_request)
        has_errors = any(issue["severity"] == "error" for issue in validation_issues)

        yield {
            "event": "spec_parsed",
            "data": {
                "part_request": _serialize_part_request(part_request),
                "validation": validation_issues,
                "printability": printability_report,
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
            printability_report=printability_report,
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
    printability_report: dict[str, Any],
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
        validation={"issues": validation_issues, "printability": printability_report},
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


def _build_printability_report(part_request: Any) -> dict[str, Any]:
    from labsmith.validation import build_printability_report

    return build_printability_report(part_request)


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


def _build_extraction_follow_up(extraction: ExtractionResult) -> str:
    if not extraction.error:
        return ""
    if "unit" not in extraction.error.lower() and "millimeter" not in extraction.error.lower():
        return ""
    return f" {extraction.error}"


# ---------------------------------------------------------------------------
# Print intent — LabSmith Device Protocol bridge
# ---------------------------------------------------------------------------

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class _PrintIntent:
    copies: int  # clamped 1..10
    version: int | None  # None = latest


# Whole-phrase triggers — these are unambiguous demo verbs.
_PRINT_PHRASES = (
    "print this",
    "print it",
    "print these",
    "print them",
    "send to printer",
    "send it to the printer",
    "send to the printer",
    "send to a printer",
    "queue this",
    "queue it",
    "queue print",
    "start a print",
    "start the print",
    "kick off a print",
    "kick off the print",
    "fabricate this",
    "fabricate it",
    "/print",
)

# Pattern triggers — commands like "print 5", "print v2", "send 3 copies".
# Most are anchored to the start of the (lowercased, stripped) message so we
# don't misread design prompts like "print a 6x8 tube rack". The "N copies"
# pattern is unanchored because it's a strong intent signal regardless of
# position (e.g., "send 3 copies of v2 to the printer").
_PRINT_PATTERN_TRIGGERS = (
    re.compile(r"^print\s+\d+\b"),
    re.compile(r"^print\s+v\d+\b"),
    re.compile(r"^print\s+(?:one|two|three|four|five|six|seven|eight|nine|ten)\b"),
    re.compile(r"\b\d+\s+(?:more\s+)?(?:copies?|prints?)\b"),
)

_WORD_TO_INT = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def _parse_print_intent(user_content: str) -> _PrintIntent | None:
    """Detect a print intent and extract copy count + version filter.

    Returns None when the message is clearly not a print request. Returns
    a `_PrintIntent` when triggered — even if the copy count is 1 and the
    version is unspecified (latest).
    """
    text = user_content.strip().lower()
    if not text:
        return None

    triggered = any(phrase in text for phrase in _PRINT_PHRASES) or any(
        pat.search(text) for pat in _PRINT_PATTERN_TRIGGERS
    )
    if not triggered:
        return None

    return _PrintIntent(
        copies=_extract_copies(text),
        version=_extract_version(text),
    )


def _extract_copies(text: str) -> int:
    """Find a copy count in the message. Falls back to 1. Clamps to 1..10
    to match the API schema. Word numbers ("two", "three") are honored."""
    for word, value in _WORD_TO_INT.items():
        if re.search(rf"\b{word}\b", text):
            return value

    # `\b\d+\b` — word boundaries skip "1" inside "v1" since v is a word
    # char, so version numbers don't get misread as copies.
    matches = re.findall(r"\b(\d+)\b", text)
    for raw in matches:
        try:
            n = int(raw)
        except ValueError:
            continue
        if 1 <= n <= 100:
            return min(10, max(1, n))
    return 1


def _extract_version(text: str) -> int | None:
    """Match `v1`, `v 1`, or `version 2`. Returns None when unspecified."""
    m = re.search(r"\bv(?:ersion)?\s*(\d+)\b", text)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


async def _handle_print_intent(
    db: AsyncSession,
    *,
    session: DesignSession,
    user: User,
    intent: _PrintIntent,
) -> tuple[AgentEvent, str]:
    """Resolve the artifact, dispatch the job(s), and craft the reply text.

    Returns (event, reply_text). The event is always emitted; the reply
    text is the assistant message body the user sees.
    """
    lab_id = await _lab_id_for_session(db, session=session)
    if lab_id is None:
        return (
            {
                "event": "print_failed",
                "data": {"reason": "missing_lab", "detail": "no lab"},
            },
            "I couldn't print that — this session isn't associated with a lab.",
        )

    artifact, fallback_note = await _resolve_print_artifact(
        db, session_id=session.id, requested_version=intent.version
    )
    if artifact is None:
        return (
            {
                "event": "print_failed",
                "data": {
                    "reason": "no_artifact",
                    "detail": "no artifact in session",
                    "requested_version": intent.version,
                },
            },
            (
                "I'd love to print that, but there's no generated part in this "
                "session yet. Describe what you want to make first — once we "
                "have an STL I can send it to the printer."
            ),
        )

    try:
        jobs = await submit_print_job(
            db,
            lab_id=lab_id,
            user=user,
            artifact_id=artifact.id,
            copies=intent.copies,
        )
    except Exception as exc:  # noqa: BLE001 — surface as event, not stream crash
        logger.exception("Print dispatch failed: %s", exc)
        detail = getattr(exc, "detail", None) or str(exc)
        return (
            {
                "event": "print_failed",
                "data": {"reason": "dispatch_error", "detail": detail},
            },
            (
                f"I couldn't dispatch that print: {detail}. "
                "If you don't have a printer set up yet, add one in Lab "
                "Settings → Devices and try again."
            ),
        )

    if not jobs:
        return (
            {
                "event": "print_failed",
                "data": {"reason": "no_jobs_created", "detail": "scheduler returned []"},
            },
            "I tried to dispatch the print but nothing came back from the scheduler.",
        )

    head = jobs[0]
    event: AgentEvent = {
        "event": "print_dispatched",
        "data": {
            "device_id": str(head.device_id),
            "artifact_id": str(artifact.id),
            "job_ids": [str(j.id) for j in jobs],
            "queue_position": head.queue_position,
            "eta_seconds": head.eta_seconds,
            "label": head.label,
            "copies": len(jobs),
        },
    }
    reply = _compose_print_reply(
        artifact=artifact,
        jobs=jobs,
        fallback_note=fallback_note,
    )
    return event, reply


def _compose_print_reply(
    *,
    artifact: Artifact,
    jobs: list[Any],
    fallback_note: str | None,
) -> str:
    """Friendly, concrete reply describing what just got queued."""
    label = jobs[0].label or _label_for_artifact_simple(artifact)
    n = len(jobs)

    if n == 1:
        job = jobs[0]
        if job.status == "running" or (job.queue_position == 0 and job.eta_seconds):
            eta = _format_eta(job.eta_seconds)
            head = f"Sent {label} to a printer — running now ({eta} left)."
        elif job.queue_position and job.queue_position > 0:
            head = f"Queued {label} — position {job.queue_position + 1} in line."
        else:
            head = f"Sent {label} to a printer."
    else:
        running = sum(
            1 for j in jobs if j.status == "running" or (j.queue_position == 0 and j.eta_seconds)
        )
        queued = n - running
        if running and not queued:
            head = f"Sent {n} copies of {label} — all running on separate printers."
        elif running and queued:
            head = (
                f"Queued {n} copies of {label} — {running} running now, "
                f"{queued} waiting in line."
            )
        else:
            head = f"Queued {n} copies of {label} — all waiting on a printer."

    tail = " Watch live progress in the Print queue panel below."
    if fallback_note:
        return f"{fallback_note} {head}{tail}"
    return f"{head}{tail}"


def _label_for_artifact_simple(artifact: Artifact) -> str:
    spec = artifact.spec_snapshot or {}
    part_type = spec.get("part_type") or artifact.artifact_type.value
    return f"{part_type} v{artifact.version}"


def _format_eta(seconds: float | None) -> str:
    if not isinstance(seconds, (int, float)) or seconds <= 0:
        return "less than a minute"
    if seconds < 60:
        return f"{int(seconds)}s"
    minutes = max(1, int(seconds // 60))
    return f"~{minutes} min"


async def _resolve_print_artifact(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    requested_version: int | None,
) -> tuple[Artifact | None, str | None]:
    """Look up the requested version, or the latest if unspecified.

    Returns (artifact, fallback_note). `fallback_note` is set when the user
    asked for a version that doesn't exist and we fell back to latest — the
    caller prepends it to the reply so they understand what happened.
    """
    if requested_version is not None:
        result = await db.execute(
            select(Artifact)
            .where(
                Artifact.session_id == session_id,
                Artifact.version == requested_version,
            )
            .limit(1)
        )
        match = result.scalar_one_or_none()
        if match is not None:
            return match, None
        # Requested version doesn't exist — fall back to latest with a note.
        latest = await _latest_artifact_for_session(db, session_id=session_id)
        if latest is None:
            return None, None
        note = (
            f"There's no v{requested_version} in this session yet — "
            f"using the latest (v{latest.version}) instead."
        )
        return latest, note

    return await _latest_artifact_for_session(db, session_id=session_id), None


async def _latest_artifact_for_session(
    db: AsyncSession, *, session_id: uuid.UUID
) -> Artifact | None:
    result = await db.execute(
        select(Artifact)
        .where(Artifact.session_id == session_id)
        .order_by(desc(Artifact.version))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _lab_id_for_session(
    db: AsyncSession, *, session: DesignSession
) -> uuid.UUID | None:
    result = await db.execute(
        select(Project.laboratory_id).where(Project.id == session.project_id)
    )
    return result.scalar_one_or_none()
