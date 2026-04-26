"""Document retrieval for the M9 onboarding agent.

Two backends ship today:

- `LexicalRetriever` — TF-IDF-style scoring over chunked text. Deterministic,
  no API key, no network calls. Default selection.
- `OpenAIEmbeddingRetriever` — uses OpenAI's embeddings API for semantic
  retrieval. Catches paraphrases and synonyms the lexical scorer would miss
  ("what's the centrifuge protocol" against doc text "Beckman J6 user
  manual"). Falls back to `LexicalRetriever` on any failure (network error,
  malformed response, empty embeddings) so a misconfigured key never crashes
  a chat turn.

Both backends share the same `Retriever` protocol — adding a third (cohere,
local sentence-transformers, etc.) is one class + a branch in `get_retriever()`.

Retrieval is computed per turn for now. There is no persistent embedding
index. With current document size limits (`lab_document_max_bytes = 1MB`)
and `top_k = 3` this costs well under a cent per turn for the OpenAI path
and ~ms for the lexical path. If document collections grow large enough to
matter, the right next step is a `lab_document_chunks` table with cached
embeddings; the protocol here doesn't change.

The agent never imports a retriever class directly — it always goes through
`get_retriever()`. Selection is via `LABSMITH_ONBOARDING_RETRIEVER`.
"""
from __future__ import annotations

import logging
import math
import re
import uuid
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DocumentChunk:
    """A single chunk of a lab document, ready to be scored against a query."""

    document_id: uuid.UUID
    document_title: str
    chunk_index: int
    text: str


@dataclass(frozen=True)
class ScoredChunk:
    """A chunk with its retrieval score. Higher = more relevant. The retriever
    returns these sorted descending."""

    chunk: DocumentChunk
    score: float


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


# Tokens shorter than this many chars are dropped from lexical scoring so
# things like "a", "I", "of", "to", "is" don't dominate. (We keep them in
# the chunk text, of course — only scoring ignores them.)
_MIN_TOKEN_LEN = 2


_STOPWORDS = frozenset(
    {
        "a", "about", "above", "after", "again", "against", "all", "am", "an",
        "and", "any", "are", "as", "at", "be", "because", "been", "before",
        "being", "below", "between", "both", "but", "by", "can", "did", "do",
        "does", "doing", "down", "during", "each", "few", "for", "from",
        "further", "had", "has", "have", "having", "he", "her", "here", "hers",
        "herself", "him", "himself", "his", "how", "i", "if", "in", "into",
        "is", "it", "its", "itself", "just", "me", "more", "most", "my",
        "myself", "no", "nor", "not", "now", "of", "off", "on", "once", "only",
        "or", "other", "our", "ours", "ourselves", "out", "over", "own", "same",
        "she", "should", "so", "some", "such", "than", "that", "the", "their",
        "theirs", "them", "themselves", "then", "there", "these", "they",
        "this", "those", "through", "to", "too", "under", "until", "up",
        "very", "was", "we", "were", "what", "when", "where", "which", "while",
        "who", "whom", "why", "will", "with", "you", "your", "yours",
        "yourself", "yourselves",
    }
)


def chunk_document_text(
    *,
    document_id: uuid.UUID,
    document_title: str,
    text: str,
    max_chars: int | None = None,
) -> list[DocumentChunk]:
    """Split `text` into chunks of at most `max_chars` characters.

    Splits on blank-line paragraph boundaries first, then merges adjacent
    paragraphs while staying under `max_chars`. Long paragraphs are broken
    on sentence-ish boundaries so we don't return a 5KB chunk just because
    the source document was one big block of text.
    """
    if not text or not text.strip():
        return []

    target = max_chars if max_chars is not None else settings.onboarding_chunk_max_chars
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        # No paragraph breaks — treat the whole thing as one paragraph and
        # let the long-paragraph splitter handle it.
        paragraphs = [text.strip()]

    raw_chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > target:
            # Flush whatever's pending, then split the long paragraph.
            if current:
                raw_chunks.append(current)
                current = ""
            raw_chunks.extend(_split_long_paragraph(paragraph, target))
            continue

        if not current:
            current = paragraph
        elif len(current) + 2 + len(paragraph) <= target:
            current = f"{current}\n\n{paragraph}"
        else:
            raw_chunks.append(current)
            current = paragraph
    if current:
        raw_chunks.append(current)

    return [
        DocumentChunk(
            document_id=document_id,
            document_title=document_title,
            chunk_index=i,
            text=chunk_text,
        )
        for i, chunk_text in enumerate(raw_chunks)
    ]


def _split_long_paragraph(paragraph: str, max_chars: int) -> list[str]:
    """Best-effort sentence-aware split for a paragraph longer than max_chars."""
    sentences = re.split(r"(?<=[.!?])\s+", paragraph)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if not sentence:
            continue
        if len(sentence) > max_chars:
            # Sentence itself is too long — fall back to a hard char split.
            if current:
                chunks.append(current)
                current = ""
            for i in range(0, len(sentence), max_chars):
                chunks.append(sentence[i : i + max_chars])
            continue

        if not current:
            current = sentence
        elif len(current) + 1 + len(sentence) <= max_chars:
            current = f"{current} {sentence}"
        else:
            chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


def _tokenize(text: str) -> list[str]:
    """Lowercase, alphanumeric tokens with stopwords + super-short tokens dropped."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if len(t) >= _MIN_TOKEN_LEN and t not in _STOPWORDS]


# ---------------------------------------------------------------------------
# Retriever protocol + factory
# ---------------------------------------------------------------------------


class Retriever(Protocol):
    """Score and rank document chunks against a user query."""

    name: str

    async def retrieve(
        self,
        *,
        query: str,
        chunks: list[DocumentChunk],
        top_k: int,
    ) -> list[ScoredChunk]:
        """Return the top-k most relevant chunks for `query`, score-descending.

        Implementations MUST drop chunks with zero/near-zero scores rather than
        padding the output to k. Returning fewer than k is fine and often
        correct (no relevant content found).
        """
        ...


# ---------------------------------------------------------------------------
# Lexical retriever — TF-IDF-ish scoring
# ---------------------------------------------------------------------------


class LexicalRetriever:
    """Bag-of-words scoring with IDF weighting over the per-turn chunk pool.

    Deterministic, fast, no external dependencies. Misses paraphrases and
    synonyms — that's what `OpenAIEmbeddingRetriever` is for. The two
    retrievers share the same `Retriever` protocol so the agent code is
    backend-agnostic.
    """

    name = "lexical"

    async def retrieve(
        self,
        *,
        query: str,
        chunks: list[DocumentChunk],
        top_k: int,
    ) -> list[ScoredChunk]:
        if not chunks:
            return []

        query_tokens = set(_tokenize(query))
        if not query_tokens:
            return []

        # Document frequency across the per-turn chunk pool.
        df: dict[str, int] = defaultdict(int)
        for chunk in chunks:
            for token in set(_tokenize(chunk.text)):
                df[token] += 1
        n_chunks = len(chunks)

        scored: list[ScoredChunk] = []
        for chunk in chunks:
            chunk_tokens = _tokenize(chunk.text)
            if not chunk_tokens:
                continue
            tf = Counter(chunk_tokens)
            score = 0.0
            for token in query_tokens:
                if token not in tf:
                    continue
                idf = math.log(1 + n_chunks / (1 + df[token]))
                score += tf[token] * idf
            if score > 0:
                scored.append(ScoredChunk(chunk=chunk, score=score))

        scored.sort(key=lambda sc: sc.score, reverse=True)
        return scored[:top_k]


# ---------------------------------------------------------------------------
# OpenAI embedding retriever — semantic match
# ---------------------------------------------------------------------------


class OpenAIEmbeddingRetriever:
    """Cosine-similarity retrieval over OpenAI embeddings.

    Embeds the query plus every chunk in one API call (the embeddings
    endpoint accepts a list of inputs), then cosine-scores. Falls back to
    `LexicalRetriever` on any failure — network errors, empty responses,
    response shape drift — so the agent always gets *something* even if the
    embeddings provider is down.

    Embeddings are computed per turn. If the same chunk is hit on every turn
    that's wasted work, but with current document size limits the cost is
    well under a cent per turn. A persistent embeddings cache is the right
    follow-up if collections grow.
    """

    name = "openai"

    def __init__(self, *, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError(
                "LABSMITH_OPENAI_API_KEY must be set when onboarding_retriever=openai"
            )
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RuntimeError(
                "openai package not installed. Run `pip install openai>=1.30` or "
                "switch onboarding_retriever back to 'lexical'."
            ) from exc

        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._fallback = LexicalRetriever()

    async def retrieve(
        self,
        *,
        query: str,
        chunks: list[DocumentChunk],
        top_k: int,
    ) -> list[ScoredChunk]:
        if not chunks:
            return []
        try:
            return await self._retrieve_via_openai(
                query=query, chunks=chunks, top_k=top_k
            )
        except Exception as exc:
            logger.warning(
                "OpenAI embedding retrieval failed (%s); falling back to lexical",
                exc,
            )
            return await self._fallback.retrieve(
                query=query, chunks=chunks, top_k=top_k
            )

    async def _retrieve_via_openai(
        self,
        *,
        query: str,
        chunks: list[DocumentChunk],
        top_k: int,
    ) -> list[ScoredChunk]:
        # One API call: query at index 0, then each chunk's text.
        inputs: list[str] = [query] + [chunk.text for chunk in chunks]
        response = await self._client.embeddings.create(model=self._model, input=inputs)
        vectors = [item.embedding for item in response.data]
        if len(vectors) != len(inputs):
            raise RuntimeError(
                f"OpenAI returned {len(vectors)} embeddings for {len(inputs)} inputs"
            )

        query_vec = vectors[0]
        scored: list[ScoredChunk] = []
        for chunk, chunk_vec in zip(chunks, vectors[1:], strict=True):
            similarity = _cosine_similarity(query_vec, chunk_vec)
            # Cosine similarity is in [-1, 1]; treat 0 as "irrelevant" so the
            # output mirrors the lexical contract (no padding with junk).
            if similarity > 0:
                scored.append(ScoredChunk(chunk=chunk, score=similarity))

        scored.sort(key=lambda sc: sc.score, reverse=True)
        return scored[:top_k]


def _cosine_similarity(a: Iterable[float], b: Iterable[float]) -> float:
    a_list = list(a)
    b_list = list(b)
    dot = sum(ai * bi for ai, bi in zip(a_list, b_list, strict=True))
    norm_a = math.sqrt(sum(ai * ai for ai in a_list))
    norm_b = math.sqrt(sum(bi * bi for bi in b_list))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_retriever() -> Retriever:
    """Resolve the active retriever from settings.

    Defaults to `LexicalRetriever` for safety — `onboarding_retriever` must be
    explicitly set to "openai" to enable embedding API calls.
    """
    name = (settings.onboarding_retriever or "lexical").lower()

    if name == "openai":
        return OpenAIEmbeddingRetriever(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
        )

    if name != "lexical":
        logger.warning(
            "Unknown onboarding_retriever=%r; falling back to lexical", name
        )

    return LexicalRetriever()
