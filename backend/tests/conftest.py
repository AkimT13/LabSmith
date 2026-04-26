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
