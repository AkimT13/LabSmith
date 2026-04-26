from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from labsmith import __version__
from labsmith.models import HealthResponse

from app.config import settings
from app.routers import (
    artifacts,
    auth,
    chat,
    devices,
    documents,
    labs,
    messages,
    projects,
    sessions,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


OPENAPI_DESCRIPTION = """
LabSmith turns natural-language lab hardware requests into validated CAD specs
and downloadable artifacts. Authenticated v1 routes are scoped through Clerk
users, lab membership, projects, and design sessions.
"""

OPENAPI_TAGS = [
    {
        "name": "auth",
        "description": "Clerk-backed current-user and webhook endpoints.",
    },
    {
        "name": "labs",
        "description": "Laboratory workspaces, memberships, and role-scoped access.",
    },
    {
        "name": "projects",
        "description": "Projects nested under laboratories.",
    },
    {
        "name": "sessions",
        "description": "Design sessions where part-design chat and artifacts live.",
    },
    {
        "name": "chat",
        "description": "Server-Sent Events chat turns for natural-language CAD design.",
    },
    {
        "name": "messages",
        "description": "Persisted chat history for a design session.",
    },
    {
        "name": "artifacts",
        "description": "Authenticated artifact listing, STL preview, and downloads.",
    },
    {
        "name": "documents",
        "description": "Lab-scoped onboarding documents and downloads.",
    },
    {
        "name": "devices",
        "description": "LabSmith Device Protocol — simulated lab devices and print job queues.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("LabSmith starting up")
    yield
    logger.info("LabSmith shutting down")


app = FastAPI(
    title="LabSmith API",
    version="0.1.0",
    summary="Natural-language lab hardware design API.",
    description=OPENAPI_DESCRIPTION,
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["ETag", "Content-Disposition", "Content-Length"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)


app.include_router(auth.router)
app.include_router(labs.router)
app.include_router(projects.router)
app.include_router(sessions.router)
app.include_router(chat.router)
app.include_router(messages.router)
app.include_router(artifacts.router)
app.include_router(documents.router)
app.include_router(devices.router)
