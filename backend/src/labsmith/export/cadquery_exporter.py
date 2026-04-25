from __future__ import annotations

from labsmith.models import ExportFormat, ExportStatus, GeneratedFile, PartRequest, ValidationIssue
from labsmith.validation.rules import has_errors


def build_export_plan(
    request: PartRequest,
    formats: list[ExportFormat],
    validation: list[ValidationIssue],
) -> list[GeneratedFile]:
    status = ExportStatus.BLOCKED if has_errors(validation) else ExportStatus.PLANNED
    message = (
        "Resolve validation errors before generating fabrication files."
        if status == ExportStatus.BLOCKED
        else "CadQuery generation boundary is ready; concrete exporters are the next implementation step."
    )

    safe_part_name = request.part_type.value.replace("_", "-")
    return [
        GeneratedFile(
            format=file_format,
            filename=f"{safe_part_name}.{file_format.value}",
            status=status,
            message=message,
        )
        for file_format in formats
    ]
