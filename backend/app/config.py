from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {
        "env_prefix": "LABSMITH_",
        "env_file": ("backend/.env", ".env"),
        "extra": "ignore",
    }

    # Application
    app_name: str = "LabSmith"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://labsmith:labsmith@localhost:5432/labsmith"

    # Clerk
    clerk_secret_key: str = ""
    clerk_publishable_key: str = ""
    clerk_webhook_secret: str = ""
    # Set to your Clerk instance JWKS URL, e.g. https://<instance>.clerk.accounts.dev/.well-known/jwks.json
    clerk_jwks_url: str = ""

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Chat / M3
    chat_mock: bool = True
    """When true, /sessions/{id}/chat uses scripted text/pacing instead of a real
    LLM. CAD generation still runs through the real CadQuery pipeline."""

    # Storage / M4
    storage_backend: str = "local"
    """Active artifact storage backend. Only "local" is supported in M4. Future
    backends ("s3", etc.) plug into `app/services/storage.py`."""

    storage_dir: str = "./backend/storage"
    """Filesystem root for the local storage backend. Created on startup if
    missing. Tests should override this to a tmp dir to avoid cross-test
    pollution."""

    # LLM / M7 — Smart parsing & iterative refinement
    chat_llm_provider: str = "mock"
    """Which provider produces the assistant's reply text. "mock" emits a canned
    response with no network calls (default — safe for tests). "openai" streams
    via the OpenAI Chat Completions API and requires `openai_api_key`."""

    spec_extractor: str = "rule_based"
    """Which extractor populates `PartRequest` from a user prompt. "rule_based"
    (default) uses the regex parser from `labsmith.parser`. "openai" uses an
    OpenAI structured-output call that also reads conversation history and the
    session's `current_spec`, enabling iterative refinement ("make the wells
    deeper"). On any failure the OpenAI extractor falls back to rule-based, so
    setting this never crashes a chat turn."""

    openai_api_key: str = ""
    """Required when `chat_llm_provider=openai` or `spec_extractor=openai`.
    Stored as a Bearer token; never logged."""

    openai_chat_model: str = "gpt-4o-mini"
    openai_extraction_model: str = "gpt-4o-mini"

    # M8 — deployment hardening
    chat_rate_limit_requests: int = 30
    """Maximum chat turns allowed per user within `chat_rate_limit_window_seconds`.
    This in-process limiter is intended for single-instance deploys and local
    smoke tests. Use a shared store before scaling horizontally."""

    chat_rate_limit_window_seconds: int = 60
    sse_keepalive_interval_seconds: float = 15.0
    """Seconds between SSE comment heartbeats while the backend waits for the
    next generated event. Keeps proxies/browsers from treating long LLM pauses
    as a dead stream."""

    openai_chat_system_prompt: str = (
        "You are LabSmith, an assistant for designing 3D-printable laboratory "
        "hardware (tube racks, gel combs, etc.). The user describes a part "
        "they want; reply in 2-3 short conversational sentences acknowledging "
        "what you understood and any obvious assumptions. A separate parser "
        "extracts numeric parameters — DO NOT include JSON, code, or specific "
        "numbers in your reply unless the user explicitly asked. Keep it warm "
        "and brief."
    )


settings = Settings()
