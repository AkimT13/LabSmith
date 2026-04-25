from __future__ import annotations

from labsmith.models import PartRequest, PartType, ValidationIssue, ValidationSeverity


def validate_part_request(request: PartRequest) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    issues.extend(_validate_required(request))
    issues.extend(_validate_spacing(request))
    issues.extend(_validate_size(request))
    return issues


def has_errors(issues: list[ValidationIssue]) -> bool:
    return any(issue.severity == ValidationSeverity.ERROR for issue in issues)


def _validate_required(request: PartRequest) -> list[ValidationIssue]:
    required_by_part = {
        PartType.TMA_MOLD: ["rows", "cols", "diameter_mm", "spacing_mm", "depth_mm"],
        PartType.TUBE_RACK: ["rows", "cols", "diameter_mm", "spacing_mm"],
        PartType.GEL_COMB: ["well_count", "well_width_mm", "well_height_mm", "depth_mm"],
    }
    issues: list[ValidationIssue] = []
    for field in required_by_part.get(request.part_type, []):
        if getattr(request, field) is None:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="missing_parameter",
                    field=field,
                    message=f"{field} is required for {request.part_type.value}.",
                )
            )
    return issues


def _validate_spacing(request: PartRequest) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if request.diameter_mm is None or request.spacing_mm is None:
        return issues

    minimum_spacing = request.diameter_mm + 0.4
    if request.spacing_mm < minimum_spacing:
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="spacing_too_tight",
                field="spacing_mm",
                message=(
                    f"Spacing must be at least {minimum_spacing:.1f} mm for a "
                    f"{request.diameter_mm:g} mm opening."
                ),
            )
        )
    elif request.spacing_mm < request.diameter_mm + 1.0:
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code="thin_wall",
                field="spacing_mm",
                message="Spacing leaves less than 1.0 mm of material between openings.",
            )
        )
    return issues


def _validate_size(request: PartRequest) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if request.well_count and request.well_count > 384:
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code="large_array",
                field="well_count",
                message="Large arrays may exceed common desktop printer bed sizes.",
            )
        )
    if request.depth_mm and request.depth_mm < 0.8:
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code="shallow_feature",
                field="depth_mm",
                message="Features shallower than 0.8 mm may be hard to fabricate reliably.",
            )
        )
    return issues
