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


settings = Settings()
