"""Shared pytest fixtures for the backend test suite."""
from __future__ import annotations

import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from app.config import settings
from app.services import storage as storage_module


@pytest.fixture(autouse=True)
def isolated_storage_dir() -> Iterator[Path]:
    """Point the storage backend at a per-test tmp directory.

    Tests that exercise the chat/artifact pipeline write real files to disk via
    `LocalFilesystemStorage`. Without this fixture they'd accumulate under
    `backend/storage/` in the dev tree. The override is `autouse=True` so every
    test gets a fresh, isolated dir without having to opt in.
    """
    original_dir = settings.storage_dir
    with tempfile.TemporaryDirectory(prefix="labsmith-test-storage-") as tmp:
        settings.storage_dir = tmp
        storage_module.reset_storage_for_testing()
        try:
            yield Path(tmp)
        finally:
            settings.storage_dir = original_dir
            storage_module.reset_storage_for_testing()


@pytest.fixture(autouse=True)
def force_mock_llm_providers() -> Iterator[None]:
    """Force every test to default to mock providers, regardless of what's in
    the developer's local `.env`. Without this, a `LABSMITH_CHAT_LLM_PROVIDER=
    openai` configured for the live demo silently makes tests hit the real
    OpenAI API — which is non-deterministic, costs money, and breaks
    assertions that expect templated output.

    Tests that specifically want to exercise the OpenAI paths should override
    these settings explicitly inside the test body and restore them in a
    `try/finally`.
    """
    originals = {
        "chat_llm_provider": settings.chat_llm_provider,
        "spec_extractor": settings.spec_extractor,
        "onboarding_retriever": settings.onboarding_retriever,
    }
    settings.chat_llm_provider = "mock"
    settings.spec_extractor = "rule_based"
    settings.onboarding_retriever = "lexical"
    try:
        yield
    finally:
        settings.chat_llm_provider = originals["chat_llm_provider"]
        settings.spec_extractor = originals["spec_extractor"]
        settings.onboarding_retriever = originals["onboarding_retriever"]
