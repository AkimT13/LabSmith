"""Unit tests for the M9 onboarding retrieval module.

Real OpenAI calls aren't exercised — the embedding retriever is exercised with
a stubbed client. The tests verify:

1. The factory respects `onboarding_retriever`.
2. Chunking splits paragraphs and breaks long single paragraphs sensibly.
3. The lexical retriever scores by token overlap × IDF and drops zero-score
   chunks.
4. The OpenAI embedding retriever computes cosine over a stubbed embedding
   response and falls back to lexical on any failure.
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest
from app.config import settings
from app.services.onboarding_retrieval import (
    LexicalRetriever,
    OpenAIEmbeddingRetriever,
    chunk_document_text,
    get_retriever,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


async def test_factory_returns_lexical_by_default() -> None:
    original = settings.onboarding_retriever
    settings.onboarding_retriever = "lexical"
    try:
        assert isinstance(get_retriever(), LexicalRetriever)
    finally:
        settings.onboarding_retriever = original


async def test_factory_falls_back_to_lexical_for_unknown_value() -> None:
    original = settings.onboarding_retriever
    settings.onboarding_retriever = "made-up-retriever"
    try:
        assert isinstance(get_retriever(), LexicalRetriever)
    finally:
        settings.onboarding_retriever = original


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


async def test_chunk_text_splits_on_paragraph_boundaries() -> None:
    document_id = uuid.uuid4()
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."

    chunks = chunk_document_text(
        document_id=document_id,
        document_title="Multi-paragraph",
        text=text,
        max_chars=20,  # Force one chunk per paragraph
    )

    assert len(chunks) == 3
    assert chunks[0].text == "First paragraph."
    assert chunks[1].text == "Second paragraph."
    assert chunks[2].text == "Third paragraph."
    assert all(c.document_title == "Multi-paragraph" for c in chunks)
    assert [c.chunk_index for c in chunks] == [0, 1, 2]


async def test_chunk_text_merges_short_paragraphs_under_target() -> None:
    chunks = chunk_document_text(
        document_id=uuid.uuid4(),
        document_title="Merged",
        text="A.\n\nB.\n\nC.",
        max_chars=200,
    )
    assert len(chunks) == 1
    assert "A." in chunks[0].text and "B." in chunks[0].text and "C." in chunks[0].text


async def test_chunk_text_breaks_long_paragraphs_on_sentence_boundaries() -> None:
    long_para = " ".join(f"Sentence number {i}." for i in range(20))
    chunks = chunk_document_text(
        document_id=uuid.uuid4(),
        document_title="Long",
        text=long_para,
        max_chars=80,
    )
    # Should produce multiple chunks, each bounded
    assert len(chunks) > 1
    assert all(len(c.text) <= 80 for c in chunks)


async def test_chunk_text_returns_empty_for_empty_input() -> None:
    chunks = chunk_document_text(
        document_id=uuid.uuid4(), document_title="Empty", text="   "
    )
    assert chunks == []


# ---------------------------------------------------------------------------
# Lexical retriever
# ---------------------------------------------------------------------------


async def test_lexical_retriever_returns_relevant_chunks() -> None:
    document_id = uuid.uuid4()
    chunks = chunk_document_text(
        document_id=document_id,
        document_title="Microscope SOP",
        text=(
            "Microscope booking procedure: reserve the slot in the calendar "
            "one day ahead.\n\nAutoclave operation: load the bag and start "
            "the cycle.\n\nFreezer inventory: keep a log of new samples."
        ),
        max_chars=120,
    )

    retriever = LexicalRetriever()
    results = await retriever.retrieve(
        query="how do I book the microscope",
        chunks=chunks,
        top_k=2,
    )

    assert len(results) >= 1
    assert "microscope" in results[0].chunk.text.lower()
    # All returned chunks have positive scores
    assert all(r.score > 0 for r in results)
    # Sorted descending
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


async def test_lexical_retriever_returns_empty_for_no_overlap() -> None:
    chunks = chunk_document_text(
        document_id=uuid.uuid4(),
        document_title="Disjoint",
        text="Beckman J6 spin balancing parameters.",
    )
    retriever = LexicalRetriever()
    results = await retriever.retrieve(
        query="who runs the freezer inventory",
        chunks=chunks,
        top_k=3,
    )
    assert results == []


async def test_lexical_retriever_handles_empty_inputs() -> None:
    retriever = LexicalRetriever()
    assert await retriever.retrieve(query="anything", chunks=[], top_k=3) == []
    assert (
        await retriever.retrieve(
            query="",
            chunks=chunk_document_text(
                document_id=uuid.uuid4(), document_title="x", text="something"
            ),
            top_k=3,
        )
        == []
    )


async def test_lexical_retriever_caps_at_top_k() -> None:
    chunks = chunk_document_text(
        document_id=uuid.uuid4(),
        document_title="Many",
        text="\n\n".join([f"Microscope notes {i}." for i in range(10)]),
        max_chars=30,
    )
    retriever = LexicalRetriever()
    results = await retriever.retrieve(
        query="microscope notes", chunks=chunks, top_k=3
    )
    assert len(results) <= 3


# ---------------------------------------------------------------------------
# OpenAI embedding retriever — stubbed
# ---------------------------------------------------------------------------


async def test_openai_embedding_retriever_rejects_empty_api_key() -> None:
    with pytest.raises(ValueError, match="LABSMITH_OPENAI_API_KEY"):
        OpenAIEmbeddingRetriever(api_key="", model="text-embedding-3-small")


async def test_openai_embedding_retriever_scores_via_cosine() -> None:
    # Query embedding aligned with first chunk, orthogonal to second.
    retriever = OpenAIEmbeddingRetriever(
        api_key="sk-test", model="text-embedding-3-small"
    )
    retriever._client = _StubOpenAIEmbeddings(
        vectors=[
            [1.0, 0.0],   # query
            [1.0, 0.0],   # chunk 0 — perfect match
            [0.0, 1.0],   # chunk 1 — orthogonal (cosine = 0, dropped)
        ]
    )
    chunks = chunk_document_text(
        document_id=uuid.uuid4(),
        document_title="Two",
        text="First chunk text.\n\nSecond chunk text.",
        max_chars=30,
    )
    assert len(chunks) == 2

    results = await retriever.retrieve(query="anything", chunks=chunks, top_k=3)

    # The orthogonal chunk has cosine = 0 and is dropped
    assert len(results) == 1
    assert results[0].chunk.chunk_index == 0
    assert results[0].score == pytest.approx(1.0)


async def test_openai_embedding_retriever_falls_back_on_failure() -> None:
    """Any exception from the embeddings call should fall back to lexical."""
    retriever = OpenAIEmbeddingRetriever(
        api_key="sk-test", model="text-embedding-3-small"
    )
    retriever._client = _FailingOpenAIEmbeddings()

    chunks = chunk_document_text(
        document_id=uuid.uuid4(),
        document_title="Lexical-friendly",
        text="Microscope booking procedure.",
    )
    # The lexical fallback should succeed on this prompt.
    results = await retriever.retrieve(
        query="microscope booking", chunks=chunks, top_k=3
    )

    assert len(results) >= 1
    assert results[0].chunk.document_title == "Lexical-friendly"


async def test_openai_embedding_retriever_handles_empty_chunks() -> None:
    retriever = OpenAIEmbeddingRetriever(
        api_key="sk-test", model="text-embedding-3-small"
    )
    # Should never reach the client when there are no chunks.
    retriever._client = _FailingOpenAIEmbeddings()
    results = await retriever.retrieve(query="anything", chunks=[], top_k=3)
    assert results == []


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class _StubOpenAIEmbeddings:
    def __init__(self, *, vectors: list[list[float]]) -> None:
        self._vectors = vectors
        self.embeddings = _StubEmbeddingsResource(vectors)


class _StubEmbeddingsResource:
    def __init__(self, vectors: list[list[float]]) -> None:
        self._vectors = vectors

    async def create(self, **_: Any) -> Any:
        return _FakeEmbeddingResponse(self._vectors)


class _FakeEmbeddingResponse:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.data = [_FakeEmbeddingItem(v) for v in vectors]


class _FakeEmbeddingItem:
    def __init__(self, embedding: list[float]) -> None:
        self.embedding = embedding


class _FailingOpenAIEmbeddings:
    def __init__(self) -> None:
        self.embeddings = _FailingEmbeddingsResource()


class _FailingEmbeddingsResource:
    async def create(self, **_: Any) -> Any:
        raise RuntimeError("simulated embeddings failure")
