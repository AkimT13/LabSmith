"""CadQuery-backed artifact generation for part-design sessions."""
from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from labsmith.models import PartRequest, PartType

from app.models.artifact import ArtifactType


@dataclass(frozen=True)
class GeneratedCadArtifact:
    artifact_type: ArtifactType
    extension: str
    content_type: str
    data: bytes


async def generate_cad_artifacts(part_request: PartRequest) -> list[GeneratedCadArtifact]:
    """Generate real CAD bytes for a validated part request.

    CadQuery is CPU-bound and may touch native OpenCascade code, so keep it out
    of the event loop. M6 requires STL; STEP can be added later by extending the
    returned artifact list without changing the agent/storage contract.
    """

    return await asyncio.to_thread(_generate_cad_artifacts_sync, part_request)


def _generate_cad_artifacts_sync(part_request: PartRequest) -> list[GeneratedCadArtifact]:
    try:
        import cadquery as cq
    except ImportError as exc:  # pragma: no cover - exercised only in misconfigured envs
        raise RuntimeError(
            "CadQuery is required for CAD generation. Install the backend CAD dependency."
        ) from exc

    if part_request.part_type == PartType.TUBE_RACK:
        model = _build_tube_rack(cq, part_request)
    elif part_request.part_type == PartType.GEL_COMB:
        model = _build_gel_comb(cq, part_request)
    elif part_request.part_type == PartType.MULTI_WELL_MOLD:
        model = _build_multi_well_mold(cq, part_request)
    elif part_request.part_type == PartType.PIPETTE_TIP_RACK:
        model = _build_pipette_tip_rack(cq, part_request)
    elif part_request.part_type == PartType.PETRI_DISH_STAND:
        model = _build_petri_dish_stand(cq, part_request)
    else:
        raise ValueError(f"No CAD generator is registered for {part_request.part_type.value}.")

    return [
        GeneratedCadArtifact(
            artifact_type=ArtifactType.STL,
            extension="stl",
            content_type="model/stl",
            data=_export_stl_bytes(cq, model),
        )
    ]


def _build_tube_rack(cq: Any, request: PartRequest) -> Any:
    rows = request.rows or 4
    cols = request.cols or 6
    diameter = request.diameter_mm or 11.0
    spacing = request.spacing_mm or diameter + 4.0
    height = request.depth_mm or 40.0
    plate_margin = max(6.0, diameter / 2)

    width = (cols - 1) * spacing + diameter + plate_margin * 2
    depth = (rows - 1) * spacing + diameter + plate_margin * 2
    hole_points = [
        ((col - (cols - 1) / 2) * spacing, (row - (rows - 1) / 2) * spacing)
        for row in range(rows)
        for col in range(cols)
    ]

    top_thickness = min(4.0, height * 0.3)
    lower_thickness = min(3.0, height * 0.25)
    post_size = max(4.0, min(8.0, diameter * 0.45))

    top_plate = _perforated_plate(
        cq,
        width=width,
        depth=depth,
        thickness=top_thickness,
        z_center=height / 2 - top_thickness / 2,
        hole_diameter=diameter,
        hole_points=hole_points,
    )
    lower_plate = _perforated_plate(
        cq,
        width=width,
        depth=depth,
        thickness=lower_thickness,
        z_center=-(height / 2) + lower_thickness / 2,
        hole_diameter=diameter * 0.25,
        hole_points=hole_points,
    )

    model = top_plate.union(lower_plate)
    for x in (-width / 2 + post_size / 2, width / 2 - post_size / 2):
        for y in (-depth / 2 + post_size / 2, depth / 2 - post_size / 2):
            post = cq.Workplane("XY").box(post_size, post_size, height).translate((x, y, 0))
            model = model.union(post)

    return model


def _perforated_plate(
    cq: Any,
    *,
    width: float,
    depth: float,
    thickness: float,
    z_center: float,
    hole_diameter: float,
    hole_points: list[tuple[float, float]],
) -> Any:
    return (
        cq.Workplane("XY")
        .box(width, depth, thickness)
        .translate((0, 0, z_center))
        .faces(">Z")
        .workplane()
        .pushPoints(hole_points)
        .hole(hole_diameter, thickness + 1.0)
    )


def _build_gel_comb(cq: Any, request: PartRequest) -> Any:
    well_count = request.well_count or 10
    tooth_width = request.well_width_mm or 5.0
    tooth_thickness = request.well_height_mm or 1.5
    tooth_depth = request.depth_mm or 8.0
    spacing = request.spacing_mm or 2.0

    rail_margin = 8.0
    rail_height = 4.0
    rail_thickness = max(3.0, tooth_thickness + 2.0)
    width = well_count * tooth_width + (well_count - 1) * spacing + rail_margin * 2

    model = cq.Workplane("XY").box(width, rail_thickness, rail_height)
    for index in range(well_count):
        x = (index - (well_count - 1) / 2) * (tooth_width + spacing)
        tooth = (
            cq.Workplane("XY")
            .center(x, 0)
            .box(tooth_width, tooth_thickness, tooth_depth)
            .translate((0, 0, -(rail_height / 2 + tooth_depth / 2)))
        )
        model = model.union(tooth)

    return model


def _build_multi_well_mold(cq: Any, request: PartRequest) -> Any:
    """A flat plate with a grid of cylindrical recessed wells.

    Geometry: a single plate with downward-facing wells (cavities), suitable
    for casting agarose, PDMS, or similar materials. The wells don't go through
    — they're blind holes from the top so cast material has a floor.

    Plate thickness is `well_depth + 3 mm` (the floor under each well).
    """
    rows = request.rows or 8
    cols = request.cols or 12
    well_diameter = request.diameter_mm or 6.0
    well_depth = request.depth_mm or 10.0
    spacing = request.spacing_mm or 9.0
    plate_margin = max(6.0, well_diameter / 2 + 2.0)
    floor_thickness = 3.0

    width = (cols - 1) * spacing + well_diameter + plate_margin * 2
    depth = (rows - 1) * spacing + well_diameter + plate_margin * 2
    plate_thickness = well_depth + floor_thickness

    well_points = [
        ((col - (cols - 1) / 2) * spacing, (row - (rows - 1) / 2) * spacing)
        for row in range(rows)
        for col in range(cols)
    ]

    return (
        cq.Workplane("XY")
        .box(width, depth, plate_thickness)
        .faces(">Z")
        .workplane()
        .pushPoints(well_points)
        .hole(well_diameter, well_depth)
    )


def _build_pipette_tip_rack(cq: Any, request: PartRequest) -> Any:
    """Two-plate rack for holding pipette tips upright.

    Top plate has tip-sized through-holes; the bottom plate has smaller drain
    holes so liquid that wicks down doesn't pool. Four corner posts connect
    the plates. Same general shape as `tube_rack` but with the proportions
    tuned for tips (taller, thinner, smaller drain holes).
    """
    rows = request.rows or 8
    cols = request.cols or 12
    tip_diameter = request.diameter_mm or 6.5
    spacing = request.spacing_mm or 9.0
    height = request.depth_mm or 50.0
    plate_margin = max(5.0, tip_diameter / 2 + 1.5)

    width = (cols - 1) * spacing + tip_diameter + plate_margin * 2
    depth = (rows - 1) * spacing + tip_diameter + plate_margin * 2
    hole_points = [
        ((col - (cols - 1) / 2) * spacing, (row - (rows - 1) / 2) * spacing)
        for row in range(rows)
        for col in range(cols)
    ]

    top_thickness = min(3.5, height * 0.2)
    bottom_thickness = min(2.5, height * 0.15)
    post_size = max(4.0, min(7.0, tip_diameter * 0.6))

    top_plate = _perforated_plate(
        cq,
        width=width,
        depth=depth,
        thickness=top_thickness,
        z_center=height / 2 - top_thickness / 2,
        hole_diameter=tip_diameter,
        hole_points=hole_points,
    )
    bottom_plate = _perforated_plate(
        cq,
        width=width,
        depth=depth,
        thickness=bottom_thickness,
        z_center=-(height / 2) + bottom_thickness / 2,
        hole_diameter=max(1.5, tip_diameter * 0.3),
        hole_points=hole_points,
    )

    model = top_plate.union(bottom_plate)
    for x in (-width / 2 + post_size / 2, width / 2 - post_size / 2):
        for y in (-depth / 2 + post_size / 2, depth / 2 - post_size / 2):
            post = cq.Workplane("XY").box(post_size, post_size, height).translate((x, y, 0))
            model = model.union(post)

    return model


def _build_petri_dish_stand(cq: Any, request: PartRequest) -> Any:
    """Vertical stack-style holder for circular petri dishes.

    Construction: a square base with four vertical corner pillars. Each pillar
    has horizontal slots cut into it at evenly spaced heights — one slot per
    dish — so a dish slides in from the side and rests on the lower edges of
    the four matching slots. Open on three sides so dishes are easy to load
    and view.

    `well_count` = number of dishes the stand holds.
    `diameter_mm` = the dish diameter (typically 90 mm or 100 mm).
    `depth_mm` = total stand height.
    """
    slot_count = max(2, request.well_count or 5)
    dish_diameter = request.diameter_mm or 90.0
    total_height = request.depth_mm or 100.0
    dish_thickness = 16.0  # standard petri dish height with lid
    slot_clearance = 2.0

    # The dish needs to rest in slots cut into the corner pillars. Footprint is
    # slightly larger than the dish so it sits comfortably with side clearance.
    footprint = dish_diameter + 12.0
    pillar_size = 8.0
    base_thickness = 4.0

    base = (
        cq.Workplane("XY")
        .box(footprint, footprint, base_thickness)
        .translate((0, 0, -(total_height / 2) + base_thickness / 2))
    )

    # Vertical positions for each slot (centered between base and top).
    usable_height = total_height - base_thickness
    slot_pitch = usable_height / slot_count
    slot_z_centers = [
        -(total_height / 2) + base_thickness + (i + 0.5) * slot_pitch
        for i in range(slot_count)
    ]

    model = base
    pillar_offset = footprint / 2 - pillar_size / 2
    pillar_height = total_height
    for sx in (-pillar_offset, pillar_offset):
        for sy in (-pillar_offset, pillar_offset):
            pillar = (
                cq.Workplane("XY")
                .box(pillar_size, pillar_size, pillar_height)
                .translate((sx, sy, 0))
            )
            # Cut a horizontal notch at each slot height so the dish edge can
            # slide in. The notch is a thin rectangular cavity wider than the
            # pillar so it cleanly intersects.
            for z in slot_z_centers:
                notch = (
                    cq.Workplane("XY")
                    .box(
                        pillar_size + 2.0,
                        pillar_size + 2.0,
                        dish_thickness + slot_clearance,
                    )
                    .translate((sx, sy, z))
                )
                # Trim notch into a "C" so the inner side stays open for the
                # dish to slide through. Shift it outward.
                outward_x = pillar_size if sx > 0 else -pillar_size
                outward_y = pillar_size if sy > 0 else -pillar_size
                notch = notch.translate((outward_x * 0.4, outward_y * 0.4, 0))
                pillar = pillar.cut(notch)
            model = model.union(pillar)

    return model


def _export_stl_bytes(cq: Any, model: Any) -> bytes:
    with tempfile.TemporaryDirectory(prefix="labsmith-cad-") as tmpdir:
        path = Path(tmpdir) / "artifact.stl"
        cq.exporters.export(
            model,
            str(path),
            exportType="STL",
            tolerance=0.5,
            angularTolerance=0.5,
        )
        return path.read_bytes()
