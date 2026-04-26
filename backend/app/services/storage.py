"""Artifact storage abstraction for M4.

The `Artifact.file_path` column stores a **storage key** (an opaque string scoped
to the active backend). The `StorageBackend` resolves keys to bytes. This way
swapping in S3/R2/Spaces later is a one-class change — no router changes, no
schema changes, no frontend changes.

The frontend never sees storage keys. It uses the artifact ID via the
`/api/v1/artifacts/{id}/{download,preview}` routes; the backend looks up the
artifact, then asks the active storage backend for the bytes.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class StorageObject:
    """Describes a stored artifact's location and metadata."""

    key: str
    size_bytes: int
    content_type: str


class StorageBackend(Protocol):
    """Pluggable backend for artifact bytes.

    All methods operate on opaque keys. Concrete backends decide how keys map to
    physical storage (filesystem path, S3 key, etc.). Keys MUST be stable across
    restarts and unique per artifact version.
    """

    async def save(self, key: str, data: bytes, *, content_type: str) -> StorageObject: ...

    async def read(self, key: str) -> bytes: ...

    async def exists(self, key: str) -> bool: ...

    async def delete(self, key: str) -> None: ...


# ---------------------------------------------------------------------------
# Local filesystem backend
# ---------------------------------------------------------------------------


class LocalFilesystemStorage:
    """Stores artifacts under a single root directory on the local filesystem.

    The root is `settings.storage_dir`. Keys are interpreted as relative paths
    under that root; parent directories are created on save. Used for dev and
    single-node deployments. For multi-node prod, swap in an object store
    backend implementing the same protocol.

    Reads are intentionally simple `Path.read_bytes()` calls — artifacts are
    small (~KB to low MB) for the foreseeable M3-M5 horizon. If artifacts grow
    beyond that, route handlers should switch to streaming via `iter_bytes()`,
    which we'd add to the protocol then.
    """

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def _resolve(self, key: str) -> Path:
        # Defense in depth: reject absolute paths and parent traversals so a
        # malicious or buggy caller can't read arbitrary files via this method.
        key_path = Path(key)
        if not key_path.parts or key_path.is_absolute() or ".." in key_path.parts:
            raise ValueError(f"Invalid storage key: {key!r}")
        path = (self._root / key_path).resolve()
        try:
            path.relative_to(self._root)
        except ValueError as exc:
            raise ValueError(f"Invalid storage key: {key!r}") from exc
        return path

    async def save(self, key: str, data: bytes, *, content_type: str) -> StorageObject:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        logger.debug("Saved %d bytes to %s", len(data), path)
        return StorageObject(key=key, size_bytes=len(data), content_type=content_type)

    async def read(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.exists():
            raise FileNotFoundError(f"Storage key not found: {key}")
        return path.read_bytes()

    async def exists(self, key: str) -> bool:
        return self._resolve(key).exists()

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.exists():
            path.unlink()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


_storage_singleton: StorageBackend | None = None


def get_storage() -> StorageBackend:
    """Return the active storage backend (singleton).

    Reads `settings.storage_backend`; only `"local"` is supported in M4. Future
    backends (`"s3"`, `"r2"`, etc.) plug in here.
    """
    global _storage_singleton
    if _storage_singleton is not None:
        return _storage_singleton

    backend_name = (settings.storage_backend or "local").lower()
    if backend_name == "local":
        _storage_singleton = LocalFilesystemStorage(Path(settings.storage_dir))
    else:
        raise RuntimeError(
            f"Unknown LABSMITH_STORAGE_BACKEND={settings.storage_backend!r}. "
            "Only 'local' is supported in M4."
        )

    return _storage_singleton


def reset_storage_for_testing() -> None:
    """Clear the cached singleton. Tests use this when they swap settings."""
    global _storage_singleton
    _storage_singleton = None


# ---------------------------------------------------------------------------
# Key + filename helpers (used by the chat service and by routers)
# ---------------------------------------------------------------------------


def artifact_storage_key(
    *, session_id: str, artifact_id: str, version: int, extension: str
) -> str:
    """Canonical key scheme for artifact bytes.

    Pattern: `sessions/<session_id>/artifacts/<artifact_id>-v<version>.<ext>`.
    Folding the version into the filename means re-generation creates new files
    instead of overwriting — the frontend's `If-None-Match` cache stays valid.
    """
    ext = extension.lstrip(".").lower()
    return f"sessions/{session_id}/artifacts/{artifact_id}-v{version}.{ext}"


CONTENT_TYPE_BY_EXTENSION = {
    "stl": "model/stl",
    "step": "model/step",
    "json": "application/json",
}
