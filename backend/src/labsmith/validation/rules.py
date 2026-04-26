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
        PartType.TUBE_RACK: ["rows", "cols", "diameter_mm", "depth_mm"],
        PartType.GEL_COMB: ["well_count", "well_width_mm", "well_height_mm", "depth_mm"],
        PartType.PIPETTE_TIP_RACK: ["rows", "cols", "diameter_mm", "depth_mm"],
        PartType.PETRI_DISH_STAND: ["well_count", "diameter_mm", "depth_mm"],
    }
    issues: list[ValidationIssue] = []
    for field in required_by_part.get(request.part_type, []):
        if getattr(request, field) is None:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="missing_parameter",
                    field=field,
                    message=_missing_parameter_message(request.part_type, field),
                )
            )
    return issues


def _missing_parameter_message(part_type: PartType, field: str) -> str:
    if part_type == PartType.TUBE_RACK:
        if field == "diameter_mm":
            return "Tube diameter is required. What is the tube diameter in mm?"
        if field == "depth_mm":
            return "Tube height is required. How tall is the tube in mm?"
    if part_type == PartType.PIPETTE_TIP_RACK:
        if field == "diameter_mm":
            return "Tip slot diameter is required. What's the tip's outer diameter in mm?"
        if field == "depth_mm":
            return "Rack height is required. How tall should the rack be in mm?"
    if part_type == PartType.PETRI_DISH_STAND:
        if field == "diameter_mm":
            return "Dish diameter is required. What is the petri dish diameter in mm?"
        if field == "depth_mm":
            return "Stand height is required. How tall should the stand be in mm?"
        if field == "well_count":
            return "Slot count is required. How many dishes should it hold?"
    return f"{field} is required for {part_type.value}."


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
