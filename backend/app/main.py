from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import artifacts, auth, chat, labs, legacy, messages, projects, sessions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("LabSmith starting up")
    yield
    logger.info("LabSmith shutting down")


app = FastAPI(
    title="LabSmith API",
    version="0.1.0",
    summary="Natural-language lab hardware design API.",
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


# New v1 routes
app.include_router(auth.router)
app.include_router(labs.router)
app.include_router(projects.router)
app.include_router(sessions.router)
app.include_router(chat.router)
app.include_router(messages.router)
app.include_router(artifacts.router)

# Legacy routes (from original scaffold)
app.include_router(legacy.router)
