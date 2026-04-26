"""Tests for the local filesystem storage backend."""
from __future__ import annotations

from pathlib import Path

import pytest
from app.services.storage import (
    LocalFilesystemStorage,
    artifact_storage_key,
    get_storage,
)

pytestmark = pytest.mark.asyncio


async def test_save_read_roundtrip(tmp_path: Path) -> None:
    storage = LocalFilesystemStorage(tmp_path)

    obj = await storage.save("foo/bar.bin", b"hello", content_type="application/octet-stream")
    assert obj.key == "foo/bar.bin"
    assert obj.size_bytes == 5
    assert obj.content_type == "application/octet-stream"

    assert await storage.exists("foo/bar.bin") is True
    assert await storage.read("foo/bar.bin") == b"hello"


async def test_read_missing_key_raises(tmp_path: Path) -> None:
    storage = LocalFilesystemStorage(tmp_path)
    with pytest.raises(FileNotFoundError):
        await storage.read("does/not/exist.bin")


async def test_delete_removes_file(tmp_path: Path) -> None:
    storage = LocalFilesystemStorage(tmp_path)
    await storage.save("a.txt", b"x", content_type="text/plain")
    assert await storage.exists("a.txt") is True

    await storage.delete("a.txt")
    assert await storage.exists("a.txt") is False


async def test_delete_missing_key_is_noop(tmp_path: Path) -> None:
    storage = LocalFilesystemStorage(tmp_path)
    # Should not raise
    await storage.delete("never/existed.bin")


async def test_save_creates_parent_dirs(tmp_path: Path) -> None:
    storage = LocalFilesystemStorage(tmp_path)
    await storage.save(
        "deeply/nested/path/file.stl", b"abc", content_type="model/stl"
    )
    assert (tmp_path / "deeply" / "nested" / "path" / "file.stl").exists()


async def test_rejects_absolute_keys(tmp_path: Path) -> None:
    storage = LocalFilesystemStorage(tmp_path)
    with pytest.raises(ValueError):
        await storage.save("/etc/passwd", b"x", content_type="text/plain")


async def test_rejects_parent_traversal(tmp_path: Path) -> None:
    storage = LocalFilesystemStorage(tmp_path)
    with pytest.raises(ValueError):
        await storage.save("../escape.bin", b"x", content_type="text/plain")


async def test_artifact_storage_key_shape() -> None:
    key = artifact_storage_key(
        session_id="sess",
        artifact_id="art",
        version=3,
        extension="stl",
    )
    assert key == "sessions/sess/artifacts/art-v3.stl"


async def test_artifact_storage_key_normalizes_extension() -> None:
    """Leading dots and uppercase should not affect the resulting key."""
    key = artifact_storage_key(
        session_id="s", artifact_id="a", version=1, extension=".STL"
    )
    assert key == "sessions/s/artifacts/a-v1.stl"


async def test_get_storage_singleton_returns_same_instance() -> None:
    """Confirm the singleton behavior so we don't accidentally re-create the
    backend (which would defeat any in-memory caching/reuse a future backend
    might rely on)."""
    a = get_storage()
    b = get_storage()
    assert a is b
