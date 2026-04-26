from __future__ import annotations

from typing import Any

from labsmith.models import EstimatedDimensions, PartRequest, PartType


COMMON_DESKTOP_BED = EstimatedDimensions(width_mm=220.0, depth_mm=220.0, height_mm=250.0)
PLA_DENSITY_G_PER_CM3 = 1.24


def estimate_part_dimensions(request: PartRequest) -> EstimatedDimensions:
    """Estimate the printed bounding box using the same assumptions as CAD generation."""
    if request.part_type == PartType.TUBE_RACK:
        rows = request.rows or 4
        cols = request.cols or 6
        diameter = request.diameter_mm or 11.0
        spacing = request.spacing_mm or diameter + 4.0
        height = request.depth_mm or 40.0
        plate_margin = max(6.0, diameter / 2)
        return EstimatedDimensions(
            width_mm=(cols - 1) * spacing + diameter + plate_margin * 2,
            depth_mm=(rows - 1) * spacing + diameter + plate_margin * 2,
            height_mm=height,
        )

    if request.part_type == PartType.GEL_COMB:
        well_count = request.well_count or 10
        tooth_width = request.well_width_mm or 5.0
        spacing = request.spacing_mm or 2.0
        tooth_depth = request.depth_mm or 8.0
        width = well_count * tooth_width + (well_count - 1) * spacing + 16.0
        return EstimatedDimensions(width_mm=width, depth_mm=tooth_depth + 4.0, height_mm=12.0)

    if request.part_type == PartType.PIPETTE_TIP_RACK:
        rows = request.rows or 8
        cols = request.cols or 12
        tip_diameter = request.diameter_mm or 6.5
        spacing = request.spacing_mm or 9.0
        height = request.depth_mm or 50.0
        plate_margin = max(5.0, tip_diameter / 2 + 1.5)
        return EstimatedDimensions(
            width_mm=(cols - 1) * spacing + tip_diameter + plate_margin * 2,
            depth_mm=(rows - 1) * spacing + tip_diameter + plate_margin * 2,
            height_mm=height,
        )

    if request.part_type == PartType.PETRI_DISH_STAND:
        dish_diameter = request.diameter_mm or 90.0
        total_height = request.depth_mm or 100.0
        footprint = dish_diameter + 12.0
        return EstimatedDimensions(width_mm=footprint, depth_mm=footprint, height_mm=total_height)

    return EstimatedDimensions(width_mm=0.0, depth_mm=0.0, height_mm=0.0)


def build_printability_report(request: PartRequest) -> dict[str, Any]:
    dimensions = estimate_part_dimensions(request)
    material = _estimate_material(request, dimensions)
    checks = [
        _bed_fit_check(dimensions),
        _wall_thickness_check(request),
        _support_risk_check(request, dimensions),
        _stability_check(dimensions),
    ]

    return {
        "dimensions_mm": _dimensions_dict(dimensions),
        "bed_mm": _dimensions_dict(COMMON_DESKTOP_BED),
        "material_estimate": material,
        "checks": checks,
    }


def _dimensions_dict(dimensions: EstimatedDimensions) -> dict[str, float]:
    return {
        "width": round(dimensions.width_mm, 2),
        "depth": round(dimensions.depth_mm, 2),
        "height": round(dimensions.height_mm, 2),
    }


def _bed_fit_check(dimensions: EstimatedDimensions) -> dict[str, str]:
    over = []
    if dimensions.width_mm > COMMON_DESKTOP_BED.width_mm:
        over.append("width")
    if dimensions.depth_mm > COMMON_DESKTOP_BED.depth_mm:
        over.append("depth")
    if dimensions.height_mm > COMMON_DESKTOP_BED.height_mm:
        over.append("height")

    if over:
        return {
            "code": "bed_fit",
            "status": "warning",
            "message": (
                "Estimated bounding box exceeds a common "
                f"{COMMON_DESKTOP_BED.width_mm:g} x {COMMON_DESKTOP_BED.depth_mm:g} x "
                f"{COMMON_DESKTOP_BED.height_mm:g} mm desktop printer bed on "
                f"{', '.join(over)}."
            ),
        }

    return {
        "code": "bed_fit",
        "status": "pass",
        "message": (
            "Estimated bounding box fits within a common "
            f"{COMMON_DESKTOP_BED.width_mm:g} x {COMMON_DESKTOP_BED.depth_mm:g} x "
            f"{COMMON_DESKTOP_BED.height_mm:g} mm desktop printer bed."
        ),
    }


def _wall_thickness_check(request: PartRequest) -> dict[str, str]:
    if request.diameter_mm is None or request.spacing_mm is None:
        return {
            "code": "wall_thickness",
            "status": "unknown",
            "message": "Wall thickness cannot be estimated until diameter and spacing are known.",
        }

    wall = request.spacing_mm - request.diameter_mm
    if wall < 0.4:
        return {
            "code": "wall_thickness",
            "status": "error",
            "message": f"Estimated material between openings is {wall:.1f} mm, below 0.4 mm.",
        }
    if wall < 1.0:
        return {
            "code": "wall_thickness",
            "status": "warning",
            "message": f"Estimated material between openings is {wall:.1f} mm; consider at least 1.0 mm.",
        }
    return {
        "code": "wall_thickness",
        "status": "pass",
        "message": f"Estimated material between openings is {wall:.1f} mm.",
    }


def _support_risk_check(request: PartRequest, dimensions: EstimatedDimensions) -> dict[str, str]:
    if request.part_type in {PartType.TUBE_RACK, PartType.PIPETTE_TIP_RACK}:
        if dimensions.height_mm >= 25:
            return {
                "code": "support_risk",
                "status": "warning",
                "message": "Open two-plate rack may need supports under the elevated top plate.",
            }
        return {
            "code": "support_risk",
            "status": "pass",
            "message": "Low rack geometry should have limited support needs.",
        }

    if request.part_type == PartType.PETRI_DISH_STAND:
        return {
            "code": "support_risk",
            "status": "warning",
            "message": "Side slots and overhangs should be checked in the slicer before printing.",
        }

    if request.part_type == PartType.GEL_COMB:
        return {
            "code": "support_risk",
            "status": "pass",
            "message": "Flat comb geometry should print without supports in the default orientation.",
        }

    return {
        "code": "support_risk",
        "status": "unknown",
        "message": "Support risk is not available for this part type yet.",
    }


def _stability_check(dimensions: EstimatedDimensions) -> dict[str, str]:
    smallest_footprint = min(dimensions.width_mm, dimensions.depth_mm)
    if smallest_footprint <= 0:
        return {
            "code": "stability",
            "status": "unknown",
            "message": "Stability cannot be estimated for this part type yet.",
        }
    if dimensions.height_mm > smallest_footprint * 1.25:
        return {
            "code": "stability",
            "status": "warning",
            "message": "Height is large relative to the footprint; consider a wider base.",
        }
    return {
        "code": "stability",
        "status": "pass",
        "message": "Height-to-footprint ratio looks stable for a benchtop part.",
    }


def _estimate_material(request: PartRequest, dimensions: EstimatedDimensions) -> dict[str, Any]:
    fill_ratio_by_part = {
        PartType.TUBE_RACK: 0.18,
        PartType.PIPETTE_TIP_RACK: 0.16,
        PartType.GEL_COMB: 0.55,
        PartType.PETRI_DISH_STAND: 0.22,
    }
    envelope_cm3 = (
        dimensions.width_mm * dimensions.depth_mm * dimensions.height_mm / 1000.0
    )
    ratio = fill_ratio_by_part.get(request.part_type, 0.2)
    material_cm3 = max(0.1, envelope_cm3 * ratio)
    return {
        "volume_cm3": round(material_cm3, 1),
        "mass_g": round(material_cm3 * PLA_DENSITY_G_PER_CM3, 1),
        "method": "rough envelope-based PLA estimate",
    }
