from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class PartType(str, Enum):
    TMA_MOLD = "tma_mold"
    TUBE_RACK = "tube_rack"
    GEL_COMB = "gel_comb"
    MULTI_WELL_MOLD = "multi_well_mold"
    MICROFLUIDIC_CHANNEL_MOLD = "microfluidic_channel_mold"


class ExportFormat(str, Enum):
    STL = "stl"
    STEP = "step"


class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


class ExportStatus(str, Enum):
    PLANNED = "planned"
    GENERATED = "generated"
    BLOCKED = "blocked"


class ParseRequest(BaseModel):
    prompt: str = Field(..., min_length=1, examples=["Create a 96-well TMA mold"])


class PartRequest(BaseModel):
    part_type: PartType
    source_prompt: str | None = None
    rows: int | None = Field(default=None, ge=1)
    cols: int | None = Field(default=None, ge=1)
    well_count: int | None = Field(default=None, ge=1)
    diameter_mm: float | None = Field(default=None, gt=0)
    spacing_mm: float | None = Field(default=None, gt=0)
    depth_mm: float | None = Field(default=None, gt=0)
    well_width_mm: float | None = Field(default=None, gt=0)
    well_height_mm: float | None = Field(default=None, gt=0)
    tube_volume_ml: float | None = Field(default=None, gt=0)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def sync_well_count(self) -> PartRequest:
        if self.rows is not None and self.cols is not None and self.well_count is None:
            self.well_count = self.rows * self.cols
        return self


class ParseResponse(BaseModel):
    part_request: PartRequest


class DesignRequest(BaseModel):
    prompt: str | None = Field(default=None, min_length=1)
    part_request: PartRequest | None = None
    formats: list[ExportFormat] = Field(default_factory=lambda: [ExportFormat.STL, ExportFormat.STEP])

    @model_validator(mode="after")
    def require_prompt_or_part_request(self) -> DesignRequest:
        if self.prompt is None and self.part_request is None:
            raise ValueError("Either prompt or part_request is required.")
        return self


class ValidationIssue(BaseModel):
    severity: ValidationSeverity
    code: str
    message: str
    field: str | None = None


class EstimatedDimensions(BaseModel):
    width_mm: float
    depth_mm: float
    height_mm: float


class TemplateSpec(BaseModel):
    part_type: PartType
    name: str
    description: str
    required_parameters: list[str]
    optional_parameters: list[str] = Field(default_factory=list)
    supported_formats: list[ExportFormat] = Field(
        default_factory=lambda: [ExportFormat.STL, ExportFormat.STEP]
    )


class GeneratedFile(BaseModel):
    format: ExportFormat
    filename: str
    status: ExportStatus
    message: str


class DesignResponse(BaseModel):
    part_request: PartRequest
    validation: list[ValidationIssue]
    template: TemplateSpec
    estimated_dimensions: EstimatedDimensions | None = None
    exports: list[GeneratedFile]


class HealthResponse(BaseModel):
    status: str
    version: str
