from labsmith.models import PartRequest, PartType, ValidationSeverity
from labsmith.validation import build_printability_report, validate_part_request


def test_valid_tube_rack_request_has_no_issues() -> None:
    request = PartRequest(
        part_type=PartType.TUBE_RACK,
        rows=4,
        cols=6,
        diameter_mm=11.0,
        spacing_mm=15.0,
        depth_mm=50.0,
    )

    assert validate_part_request(request) == []


def test_missing_required_parameter_is_error() -> None:
    request = PartRequest(
        part_type=PartType.TUBE_RACK,
        rows=4,
        cols=6,
        spacing_mm=15.0,
        depth_mm=50.0,
    )

    issues = validate_part_request(request)

    assert issues[0].severity == ValidationSeverity.ERROR
    assert issues[0].field == "diameter_mm"


def test_missing_tube_height_is_error() -> None:
    request = PartRequest(
        part_type=PartType.TUBE_RACK,
        rows=4,
        cols=6,
        diameter_mm=11.0,
        spacing_mm=15.0,
    )

    issues = validate_part_request(request)

    assert any(issue.severity == ValidationSeverity.ERROR for issue in issues)
    assert any(issue.field == "depth_mm" for issue in issues)


def test_spacing_below_minimum_is_error() -> None:
    request = PartRequest(
        part_type=PartType.TUBE_RACK,
        rows=4,
        cols=6,
        diameter_mm=11.0,
        spacing_mm=11.2,
        depth_mm=50.0,
    )

    issues = validate_part_request(request)

    assert any(issue.code == "spacing_too_tight" for issue in issues)


def test_bounding_box_constraint_is_error_when_estimate_exceeds_limit() -> None:
    request = PartRequest(
        part_type=PartType.TUBE_RACK,
        rows=4,
        cols=6,
        diameter_mm=11.0,
        spacing_mm=15.0,
        depth_mm=50.0,
        max_width_mm=90.0,
    )

    issues = validate_part_request(request)

    assert any(issue.code == "exceeds_bounding_box" for issue in issues)
    assert any(issue.field == "max_width_mm" for issue in issues)


def test_bounding_box_constraint_passes_when_estimate_fits() -> None:
    request = PartRequest(
        part_type=PartType.TUBE_RACK,
        rows=4,
        cols=6,
        diameter_mm=11.0,
        spacing_mm=15.0,
        depth_mm=50.0,
        max_width_mm=100.0,
        max_depth_mm=80.0,
        max_height_mm=60.0,
    )

    assert validate_part_request(request) == []


def test_printability_report_includes_dimensions_checks_and_material_estimate() -> None:
    request = PartRequest(
        part_type=PartType.TUBE_RACK,
        rows=4,
        cols=6,
        diameter_mm=11.0,
        spacing_mm=15.0,
        depth_mm=50.0,
    )

    report = build_printability_report(request)

    assert report["dimensions_mm"] == {"width": 98.0, "depth": 68.0, "height": 50.0}
    assert report["material_estimate"]["mass_g"] > 0
    assert {check["code"] for check in report["checks"]} == {
        "bed_fit",
        "wall_thickness",
        "support_risk",
        "stability",
    }
