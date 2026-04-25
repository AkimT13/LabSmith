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
    """Master mock flag for the M3 chat pipeline.

    When True, /sessions/{id}/chat uses the mock LLM provider AND skips real CAD
    generation (artifact bytes are fake). When False, both subsystems try to use
    real backends — but `chat_llm_provider` and (later) the CAD provider can be
    overridden independently below. Tests rely on this defaulting to True."""

    chat_llm_provider: str = "mock"
    """Which LLM provider to use for assistant text streaming. "mock" emits a
    canned response (no network call). "openai" streams via the OpenAI Chat
    Completions API and requires `openai_api_key`. Default "mock" so accidentally
    hitting /chat without an API key never costs money."""

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_system_prompt: str = (
        "You are LabSmith, an assistant for designing 3D-printable laboratory "
        "hardware (TMA molds, tube racks, gel combs, etc.). The user will describe "
        "a part they want. Respond in 2-3 short sentences acknowledging what you "
        "understood, the part type, and any obvious assumptions. A separate "
        "deterministic parser will extract numeric parameters — DO NOT include "
        "JSON, code, or specific dimensions in your reply unless the user "
        "explicitly asked. Keep it conversational."
    )


settings = Settings()
