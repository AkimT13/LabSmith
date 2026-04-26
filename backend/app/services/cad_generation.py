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
