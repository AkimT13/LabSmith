from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from labsmith import __version__
from labsmith.export import build_export_plan
from labsmith.models import (
    DesignRequest,
    DesignResponse,
    HealthResponse,
    ParseRequest,
    ParseResponse,
    TemplateSpec,
    ValidationSeverity,
)
from labsmith.parser import RuleBasedParser
from labsmith.templates import get_template, list_templates
from labsmith.validation import validate_part_request

app = FastAPI(
    title="LabSmith API",
    version=__version__,
    summary="Natural-language lab hardware design API.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

parser = RuleBasedParser()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)


@app.get("/templates", response_model=list[TemplateSpec])
def templates() -> list[TemplateSpec]:
    return [template.spec for template in list_templates()]


@app.post("/parse", response_model=ParseResponse)
def parse_prompt(request: ParseRequest) -> ParseResponse:
    try:
        return ParseResponse(part_request=parser.parse(request.prompt))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/design", response_model=DesignResponse)
def design(request: DesignRequest) -> DesignResponse:
    try:
        part_request = request.part_request or parser.parse(request.prompt or "")
        template = get_template(part_request.part_type)
    except (KeyError, ValueError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    validation = validate_part_request(part_request)
    estimated_dimensions = None
    if not any(issue.severity == ValidationSeverity.ERROR for issue in validation):
        estimated_dimensions = template.estimate_dimensions(part_request)

    return DesignResponse(
        part_request=part_request,
        validation=validation,
        template=template.spec,
        estimated_dimensions=estimated_dimensions,
        exports=build_export_plan(part_request, request.formats, validation),
    )
