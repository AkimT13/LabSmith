"""Deterministic v0 agent for `onboarding` sessions.

M9 starts with useful, local behavior before adding RAG or uploaded lab docs.
The agent classifies the user's question into a small orientation topic,
streams a practical checklist-style answer, and emits onboarding-only events.
It never parses CAD specs and never creates artifacts.
"""
from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.design_session import DesignSession, SessionType
from app.models.laboratory import Laboratory
from app.models.message import Message, MessageRole
from app.models.project import Project
from app.models.user import User
from app.services.agents.base import AgentEvent


@dataclass(frozen=True)
class OnboardingTopic:
    key: str
    label: str
    keywords: tuple[str, ...]
    rationale: str
    checklist: tuple[tuple[str, str], ...]
    followups: tuple[str, ...]


@dataclass(frozen=True)
class OnboardingContext:
    lab_name: str
    project_name: str
    session_title: str


_TOPICS: tuple[OnboardingTopic, ...] = (
    OnboardingTopic(
        key="safety",
        label="Safety and training",
        keywords=("safety", "ppe", "training", "waste", "hazard", "emergency"),
        rationale="Matched safety, training, or hazard language.",
        checklist=(
            (
                "Confirm required training",
                "Ask which safety modules are required before hands-on work.",
            ),
            (
                "Find emergency norms",
                "Locate spill, waste, eyewash, and incident reporting procedures.",
            ),
            ("Get supervised sign-off", "Have a qualified lab member observe the first run."),
        ),
        followups=(
            "What safety training do I need before using this equipment?",
            "Where are waste and spill procedures documented?",
        ),
    ),
    OnboardingTopic(
        key="protocols",
        label="Protocols and SOPs",
        keywords=("protocol", "sop", "procedure", "assay", "experiment", "workflow"),
        rationale="Matched protocol, SOP, or workflow language.",
        checklist=(
            (
                "Find the current version",
                "Ask for the active SOP and avoid using copied older files.",
            ),
            (
                "Identify critical parameters",
                "Note incubation times, volumes, temperatures, and stopping points.",
            ),
            (
                "Run with a reviewer",
                "Schedule the first run with the protocol owner or a trained member.",
            ),
        ),
        followups=(
            "Who owns the current SOP for this workflow?",
            "What are the failure points I should watch for?",
        ),
    ),
    OnboardingTopic(
        key="equipment",
        label="Equipment and locations",
        keywords=(
            "equipment",
            "instrument",
            "machine",
            "where",
            "location",
            "freezer",
            "centrifuge",
            "microscope",
        ),
        rationale="Matched equipment or location language.",
        checklist=(
            ("Find the physical location", "Confirm where the instrument or supply lives."),
            ("Identify the owner", "Ask who maintains it and who can train new users."),
            (
                "Check booking rules",
                "Learn reservation, calibration, cleaning, and shutdown expectations.",
            ),
        ),
        followups=(
            "Where is the equipment stored and who owns it?",
            "Do I need training or booking access before using it?",
        ),
    ),
    OnboardingTopic(
        key="people",
        label="People and ownership",
        keywords=(
            "who",
            "owner",
            "owns",
            "contact",
            "responsible",
            "help",
            "manager",
            "pi",
        ),
        rationale="Matched ownership or contact language.",
        checklist=(
            ("Name the owner", "Identify the person responsible for the workflow or asset."),
            ("Clarify backup coverage", "Ask who can help when the owner is unavailable."),
            ("Capture escalation path", "Write down when to ask a peer, lab manager, or PI."),
        ),
        followups=(
            "Who should review my first attempt?",
            "Who is the backup contact when the owner is unavailable?",
        ),
    ),
    OnboardingTopic(
        key="access",
        label="Access and permissions",
        keywords=(
            "access",
            "badge",
            "permission",
            "account",
            "login",
            "software",
            "calendar",
        ),
        rationale="Matched access, account, or permission language.",
        checklist=(
            (
                "List required access",
                "Separate physical access, software accounts, and equipment calendars.",
            ),
            ("Find the approver", "Ask who approves each access request."),
            (
                "Test before deadline",
                "Verify login or booking access before the first planned run.",
            ),
        ),
        followups=(
            "Which accounts or calendars do I need access to?",
            "Who approves access for this workflow?",
        ),
    ),
    OnboardingTopic(
        key="data",
        label="Data and records",
        keywords=(
            "data",
            "folder",
            "notebook",
            "eln",
            "files",
            "storage",
            "record",
            "results",
        ),
        rationale="Matched data, file, or lab-record language.",
        checklist=(
            (
                "Find the canonical storage location",
                "Ask where raw data, processed data, and notes belong.",
            ),
            ("Clarify naming rules", "Record file, sample, and notebook naming conventions."),
            (
                "Capture retention expectations",
                "Ask what must be retained for audits or publication.",
            ),
        ),
        followups=(
            "Where should I store raw data and analysis files?",
            "What naming convention should I follow?",
        ),
    ),
)

_DEFAULT_TOPIC = OnboardingTopic(
    key="getting_started",
    label="Getting started",
    keywords=(),
    rationale="No specific onboarding topic matched, so using a general first-day path.",
    checklist=(
        ("Map the workflow", "Write down the workflow, assets, people, and approvals involved."),
        ("Find the owner", "Ask who maintains the current source of truth."),
        ("Shadow before solo work", "Watch one complete run before attempting it independently."),
    ),
    followups=(
        "What should I learn first for this project?",
        "Who should I talk to before doing hands-on work?",
    ),
)


class OnboardingAgent:
    session_type = SessionType.ONBOARDING

    async def run_turn(
        self,
        *,
        db: AsyncSession,
        session: DesignSession,
        user: User,
        user_content: str,
    ) -> AsyncGenerator[AgentEvent, None]:
        topic = _select_topic(user_content)
        context = await _load_context(db, session)
        assistant_message_id = uuid.uuid4()
        content = _build_reply(
            topic=topic,
            context=context,
            user=user,
            user_content=user_content,
        )

        assistant_msg = Message(
            id=assistant_message_id,
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content=content,
            metadata_={
                "agent": "onboarding",
                "version": "v0",
                "topic": topic.key,
                "doc_backed": False,
            },
        )
        db.add(assistant_msg)
        await db.flush()

        yield {
            "event": "topic_suggested",
            "data": {
                "topic": topic.key,
                "label": topic.label,
                "rationale": topic.rationale,
                "suggested_questions": list(topic.followups),
            },
        }

        for index, (title, detail) in enumerate(topic.checklist, start=1):
            yield {
                "event": "checklist_step",
                "data": {
                    "step_id": f"{topic.key}-{index}",
                    "title": title,
                    "detail": detail,
                    "status": "suggested",
                },
            }

        async for event in _stream_text(assistant_message_id, content):
            yield event

        yield {
            "event": "message_complete",
            "data": {
                "message_id": str(assistant_message_id),
                "content": content,
            },
        }
        await db.commit()


def _select_topic(user_content: str) -> OnboardingTopic:
    normalized = user_content.lower()
    for topic in _TOPICS:
        if any(keyword in normalized for keyword in topic.keywords):
            return topic
    return _DEFAULT_TOPIC


async def _load_context(db: AsyncSession, session: DesignSession) -> OnboardingContext:
    result = await db.execute(
        select(Project, Laboratory)
        .join(Laboratory, Laboratory.id == Project.laboratory_id)
        .where(Project.id == session.project_id)
    )
    row = result.one_or_none()
    if row is None:
        return OnboardingContext(
            lab_name="this lab",
            project_name="this project",
            session_title=session.title,
        )

    project, laboratory = row
    return OnboardingContext(
        lab_name=laboratory.name,
        project_name=project.name,
        session_title=session.title,
    )


def _build_reply(
    *,
    topic: OnboardingTopic,
    context: OnboardingContext,
    user: User,
    user_content: str,
) -> str:
    user_name = user.display_name or "there"
    checklist = _format_checklist(topic.checklist)
    followups = _format_lines(topic.followups)
    prompt = user_content.strip()

    return (
        f"Hi {user_name}. For {context.lab_name} / {context.project_name}, "
        f"I would treat this as an onboarding question about {topic.label.lower()}.\n\n"
        "I do not have uploaded lab documents connected yet, so this is general "
        "orientation guidance rather than lab policy.\n\n"
        f"Your question: {prompt}\n\n"
        "Suggested checklist:\n"
        f"{checklist}\n\n"
        "Good next questions:\n"
        f"{followups}"
    )


def _format_checklist(checklist: Sequence[tuple[str, str]]) -> str:
    return "\n".join(
        f"- {title}: {detail}"
        for title, detail in checklist
    )


def _format_lines(items: Sequence[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


async def _stream_text(
    assistant_message_id: uuid.UUID,
    content: str,
) -> AsyncGenerator[AgentEvent, None]:
    chunk_size = max(1, len(content) // 5)
    for i in range(0, len(content), chunk_size):
        chunk = content[i : i + chunk_size]
        yield {
            "event": "text_delta",
            "data": {
                "message_id": str(assistant_message_id),
                "delta": chunk,
            },
        }
        if settings.chat_mock:
            await asyncio.sleep(0.03)
