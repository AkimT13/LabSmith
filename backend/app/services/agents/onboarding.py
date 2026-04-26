"""Deterministic + retrieval-augmented agent for `onboarding` sessions.

M9 starts with useful, local behavior before adding RAG or uploaded lab docs.
The agent classifies the user's question into a small orientation topic,
retrieves the most relevant snippets from lab-uploaded documents (lexical
by default; semantic via OpenAI embeddings when configured), streams a
practical checklist-style answer, and emits onboarding-only events. It
never parses CAD specs and never creates artifacts.

When real document content is retrieved, the reply incorporates the snippets
and the agent emits one `doc_referenced` event per cited document so the
frontend can link to the source. When no relevant chunks are found, the
agent falls back to the prior "available documents (no semantic match yet)"
branch — keeping prior tests stable and the v0 contract honored.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.design_session import DesignSession, SessionType
from app.models.lab_document import LabDocument
from app.models.laboratory import Laboratory
from app.models.message import Message, MessageRole
from app.models.project import Project
from app.models.user import User
from app.services.agents.base import AgentEvent
from app.services.onboarding_retrieval import (
    DocumentChunk,
    ScoredChunk,
    chunk_document_text,
    get_retriever,
)
from app.services.storage import get_storage

logger = logging.getLogger(__name__)


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
    lab_id: uuid.UUID | None
    lab_name: str
    project_name: str
    session_title: str
    document_titles: tuple[str, ...]


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
            "role",
            "roles",
            "roster",
            "team",
            "members",
            "people",
        ),
        rationale="Matched ownership, role, or contact language.",
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

        # Load full text for retrieval. Skips docs whose bytes can't be decoded
        # (binaries, missing files) — they're still mentioned by title via
        # `context.document_titles`.
        retrievable_documents: list[_RetrievableDocument] = []
        if context.lab_id is not None:
            retrievable_documents = await _load_documents_with_text(
                db, lab_id=context.lab_id
            )

        scored_chunks = await _retrieve(
            user_content=user_content,
            documents=retrievable_documents,
        )

        # Citations: dedup by document_id, preserve top-score order.
        citations = _build_citations(scored_chunks)

        assistant_message_id = uuid.uuid4()
        content = _build_reply(
            topic=topic,
            context=context,
            user=user,
            user_content=user_content,
            scored_chunks=scored_chunks,
            citations=citations,
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
                "doc_backed": bool(citations),
                "retriever": _retriever_name() if citations else None,
                "cited_documents": [
                    {
                        "document_id": str(citation.document_id),
                        "title": citation.title,
                        "score": round(citation.score, 4),
                    }
                    for citation in citations
                ],
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

        # `doc_referenced` is reserved for actual document-backed retrieval per
        # the M9 contract. We only emit when at least one chunk was scored
        # above zero — title-only listing isn't enough.
        for citation in citations:
            yield {
                "event": "doc_referenced",
                "data": {
                    "document_id": str(citation.document_id),
                    "title": citation.title,
                    "source": "uploaded document",
                    "url": f"/api/v1/documents/{citation.document_id}/download",
                    "score": round(citation.score, 4),
                },
            }

        # If we retrieved real chunks AND the LLM provider is configured,
        # synthesize a natural answer from the retrieved snippets instead of
        # dumping the templated reply. The user gets "Daniel Okafor is the
        # Lab Safety Officer" instead of "here's a snippet that contains it".
        # Falls back to the templated reply on any LLM failure.
        if citations and _llm_synthesis_available():
            llm_text, llm_failed = await _collect_rag_synthesis_or_none(
                user_content=user_content,
                citations=citations,
                lab_name=context.lab_name,
            )
            if llm_text and not llm_failed:
                content = llm_text
                assistant_msg.content = content
                # Stream to the client in roughly chunk-shaped pieces so the
                # UI's text_delta handler still sees a streaming reply.
                async for event in _stream_text(assistant_message_id, content):
                    yield event
            else:
                async for event in _stream_text(assistant_message_id, content):
                    yield event
        else:
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


# ---------------------------------------------------------------------------
# Topic + context (unchanged from v0)
# ---------------------------------------------------------------------------


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
            lab_id=None,
            lab_name="this lab",
            project_name="this project",
            session_title=session.title,
            document_titles=(),
        )

    project, laboratory = row
    document_titles = await _load_document_titles(db, laboratory.id)
    return OnboardingContext(
        lab_id=laboratory.id,
        lab_name=laboratory.name,
        project_name=project.name,
        session_title=session.title,
        document_titles=document_titles,
    )


async def _load_document_titles(
    db: AsyncSession,
    lab_id: uuid.UUID,
) -> tuple[str, ...]:
    result = await db.execute(
        select(LabDocument.title)
        .where(LabDocument.laboratory_id == lab_id)
        .order_by(LabDocument.created_at.desc())
        .limit(5)
    )
    return tuple(result.scalars().all())


# ---------------------------------------------------------------------------
# Document retrieval (M9)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _RetrievableDocument:
    document_id: uuid.UUID
    title: str
    chunks: tuple[DocumentChunk, ...]


@dataclass(frozen=True)
class _Citation:
    document_id: uuid.UUID
    title: str
    score: float
    snippet: str


async def _load_documents_with_text(
    db: AsyncSession,
    *,
    lab_id: uuid.UUID,
) -> list[_RetrievableDocument]:
    """Fetch lab documents + decoded text + chunks. Membership scoping is
    enforced by the caller (we look up by lab_id, which only flows through
    `_load_context` after the session-membership check in the chat dispatcher)."""
    result = await db.execute(
        select(LabDocument)
        .where(LabDocument.laboratory_id == lab_id)
        .order_by(LabDocument.created_at.desc())
    )
    documents = list(result.scalars().all())
    if not documents:
        return []

    storage = get_storage()
    out: list[_RetrievableDocument] = []
    for document in documents:
        text = await _read_document_text(storage, document)
        if text is None or not text.strip():
            continue
        chunks = chunk_document_text(
            document_id=document.id,
            document_title=document.title,
            text=text,
        )
        if not chunks:
            continue
        out.append(
            _RetrievableDocument(
                document_id=document.id,
                title=document.title,
                chunks=tuple(chunks),
            )
        )
    return out


async def _read_document_text(storage: object, document: LabDocument) -> str | None:
    """Best-effort UTF-8 decode of a document's stored bytes. Returns None for
    binaries or missing files; the agent silently skips those for retrieval
    while still listing them by title in the fallback note."""
    try:
        data: bytes = await storage.read(document.file_path)  # type: ignore[attr-defined]
    except (FileNotFoundError, ValueError) as exc:
        logger.warning(
            "Skipping document %s for retrieval: storage read failed (%s)",
            document.id,
            exc,
        )
        return None

    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        logger.info(
            "Skipping document %s for retrieval: not UTF-8 decodable", document.id
        )
        return None


async def _retrieve(
    *,
    user_content: str,
    documents: list[_RetrievableDocument],
) -> list[ScoredChunk]:
    if not documents:
        return []
    pool: list[DocumentChunk] = []
    for doc in documents:
        pool.extend(doc.chunks)
    if not pool:
        return []

    retriever = get_retriever()
    return await retriever.retrieve(
        query=user_content,
        chunks=pool,
        top_k=settings.onboarding_top_k_chunks,
    )


def _build_citations(scored_chunks: Sequence[ScoredChunk]) -> list[_Citation]:
    """Dedup chunks down to one citation per document, keeping the highest
    score and a short snippet from the best-scoring chunk."""
    seen: dict[uuid.UUID, _Citation] = {}
    for sc in scored_chunks:
        existing = seen.get(sc.chunk.document_id)
        if existing is None or sc.score > existing.score:
            seen[sc.chunk.document_id] = _Citation(
                document_id=sc.chunk.document_id,
                title=sc.chunk.document_title,
                score=sc.score,
                snippet=_short_snippet(sc.chunk.text),
            )
    # Preserve top-score order.
    return sorted(seen.values(), key=lambda c: c.score, reverse=True)


def _short_snippet(text: str, *, max_chars: int = 240) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"


def _retriever_name() -> str:
    return (settings.onboarding_retriever or "lexical").lower()


# ---------------------------------------------------------------------------
# LLM synthesis (RAG) — turns retrieved snippets into a natural answer
# ---------------------------------------------------------------------------


_RAG_SYSTEM_PROMPT = (
    "You are LabSmith, an onboarding assistant for the {lab_name} lab. "
    "Answer the user's question using ONLY the provided lab document "
    "snippets. Be direct: 1-3 sentences for factual lookups, more if the "
    "question is procedural or open-ended. When you state a fact taken "
    "from a document, mention the document in parentheses, e.g. "
    "'(per Lab Roster)'. If the snippets don't contain the answer, say so "
    "honestly and suggest who the user could ask. Don't invent contacts, "
    "dates, room numbers, or procedures that aren't in the snippets."
)


def _llm_synthesis_available() -> bool:
    """We do RAG synthesis only when the chat LLM provider is OpenAI AND a key
    is configured. Mock providers can't generate a useful answer from arbitrary
    document context."""
    return (
        (settings.chat_llm_provider or "").lower() == "openai"
        and bool(settings.openai_api_key)
    )


async def _collect_rag_synthesis_or_none(
    *,
    user_content: str,
    citations: Sequence[_Citation],
    lab_name: str,
) -> tuple[str | None, bool]:
    """Run an OpenAI chat completion that synthesizes an answer from the
    retrieved citation snippets. Returns (text, failed) — `failed` is True
    if anything went wrong, in which case the caller should fall back to the
    templated reply.

    Non-streaming because the agent already streams the assembled text via
    `_stream_text` for visual consistency with the templated path. Synthesis
    is fast enough that the user-perceived delay is fine.
    """
    try:
        from openai import AsyncOpenAI
    except ImportError:
        logger.warning("openai package not installed; skipping RAG synthesis")
        return None, True

    context_blocks = "\n\n".join(
        f"### {c.title}\n{c.snippet}" for c in citations
    )
    messages = [
        {"role": "system", "content": _RAG_SYSTEM_PROMPT.format(lab_name=lab_name)},
        {
            "role": "system",
            "content": f"Lab document snippets retrieved for this question:\n\n{context_blocks}",
        },
        {"role": "user", "content": user_content},
    ]

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=messages,
        )
        if not response.choices:
            return None, True
        text = response.choices[0].message.content
        if not text or not text.strip():
            return None, True
        return text.strip(), False
    except Exception as exc:
        logger.warning("RAG synthesis failed (%s); falling back to templated reply", exc)
        return None, True


# ---------------------------------------------------------------------------
# Reply assembly
# ---------------------------------------------------------------------------


def _build_reply(
    *,
    topic: OnboardingTopic,
    context: OnboardingContext,
    user: User,
    user_content: str,
    scored_chunks: Sequence[ScoredChunk],
    citations: Sequence[_Citation],
) -> str:
    user_name = user.display_name or "there"
    checklist = _format_checklist(topic.checklist)
    followups = _format_lines(topic.followups)
    prompt = user_content.strip()
    document_note = _build_document_note(
        document_titles=context.document_titles,
        scored_chunks=scored_chunks,
        citations=citations,
    )

    return (
        f"Hi {user_name}. For {context.lab_name} / {context.project_name}, "
        f"I would treat this as an onboarding question about {topic.label.lower()}.\n\n"
        f"{document_note}\n\n"
        f"Your question: {prompt}\n\n"
        "Suggested checklist:\n"
        f"{checklist}\n\n"
        "Good next questions:\n"
        f"{followups}"
    )


def _build_document_note(
    *,
    document_titles: Sequence[str],
    scored_chunks: Sequence[ScoredChunk],
    citations: Sequence[_Citation],
) -> str:
    # Three branches:
    #   (1) no documents at all -> orientation guidance only
    #   (2) documents exist but no chunks scored above zero -> list titles, say
    #       semantic match didn't fire (kept stable for older tests)
    #   (3) documents exist AND retrieval found relevant snippets -> incorporate
    #       snippets and cite the source documents
    if not document_titles and not scored_chunks:
        return (
            "I do not have uploaded lab documents connected yet, so this is "
            "general orientation guidance rather than lab policy."
        )

    if not citations:
        documents = _format_lines(document_titles)
        return (
            "I can see uploaded lab document records, but semantic search and "
            "citations are not connected yet. Use this as orientation guidance "
            "and verify against these available documents:\n"
            f"{documents}"
        )

    snippet_lines = "\n\n".join(
        f"- {citation.title}: {citation.snippet}" for citation in citations
    )
    citation_lines = _format_lines(
        [f"{citation.title} (relevance {citation.score:.2f})" for citation in citations]
    )
    return (
        "Based on your lab documents, here's what's most relevant to this "
        "question:\n\n"
        f"{snippet_lines}\n\n"
        "Sources cited above:\n"
        f"{citation_lines}"
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
