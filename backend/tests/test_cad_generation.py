"""Tests for M6 real CadQuery artifact generation."""
from __future__ import annotations

import pytest
from app.models.artifact import ArtifactType
from app.services.cad_generation import generate_cad_artifacts
from app.services.placeholder_stl import get_placeholder_stl_bytes
from labsmith.models import PartRequest, PartType
from stl_helpers import assert_close, assert_valid_stl

pytestmark = pytest.mark.asyncio


async def test_tube_rack_generates_real_stl_with_requested_dimensions() -> None:
    request = PartRequest(
        part_type=PartType.TUBE_RACK,
        rows=4,
        cols=6,
        well_count=24,
        diameter_mm=11.0,
        spacing_mm=15.0,
        depth_mm=20.0,
    )

    artifacts = await generate_cad_artifacts(request)

    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert artifact.artifact_type == ArtifactType.STL
    assert artifact.extension == "stl"
    assert artifact.content_type == "model/stl"
    assert artifact.data != get_placeholder_stl_bytes()

    bounds = assert_valid_stl(artifact.data)
    assert_close(bounds.width, 98.0)
    assert_close(bounds.depth, 68.0)
    assert_close(bounds.height, 20.0)


async def test_tube_rack_uses_taller_default_height() -> None:
    request = PartRequest(
        part_type=PartType.TUBE_RACK,
        rows=4,
        cols=6,
        well_count=24,
        diameter_mm=11.0,
        spacing_mm=15.0,
    )

    artifacts = await generate_cad_artifacts(request)

    bounds = assert_valid_stl(artifacts[0].data)
    assert_close(bounds.height, 40.0)


async def test_gel_comb_generates_real_stl_with_requested_dimensions() -> None:
    request = PartRequest(
        part_type=PartType.GEL_COMB,
        well_count=10,
        well_width_mm=5.0,
        well_height_mm=1.5,
        depth_mm=8.0,
        spacing_mm=2.0,
    )

    artifacts = await generate_cad_artifacts(request)

    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert artifact.artifact_type == ArtifactType.STL
    assert artifact.extension == "stl"
    assert artifact.content_type == "model/stl"
    assert artifact.data != get_placeholder_stl_bytes()

    bounds = assert_valid_stl(artifact.data)
    assert_close(bounds.width, 84.0)
    assert_close(bounds.depth, 3.5)
    assert_close(bounds.height, 12.0)


# ---------------------------------------------------------------------------
# New M9 part types — pipette tip rack, petri dish stand
# ---------------------------------------------------------------------------


async def test_pipette_tip_rack_generates_real_stl() -> None:
    """Standard 96-tip rack: 8x12, 6.5mm slots, 9mm spacing, 50mm tall.
    Width = 11*9 + 6.5 + 2*max(5, 4.75) = 99 + 6.5 + 10 = 115.5.
    Depth = 7*9 + 6.5 + 10 = 79.5.
    """
    request = PartRequest(
        part_type=PartType.PIPETTE_TIP_RACK,
        rows=8,
        cols=12,
        well_count=96,
        diameter_mm=6.5,
        spacing_mm=9.0,
        depth_mm=50.0,
    )

    artifacts = await generate_cad_artifacts(request)
    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert artifact.artifact_type == ArtifactType.STL

    bounds = assert_valid_stl(artifact.data)
    assert_close(bounds.width, 115.5)
    assert_close(bounds.depth, 79.5)
    assert_close(bounds.height, 50.0)


async def test_petri_dish_stand_generates_real_stl() -> None:
    """5-slot stand for 90mm petri dishes, 100mm tall.
    Footprint = 90 + 12 = 102. Total height = 100.
    """
    request = PartRequest(
        part_type=PartType.PETRI_DISH_STAND,
        well_count=5,
        diameter_mm=90.0,
        depth_mm=100.0,
    )

    artifacts = await generate_cad_artifacts(request)
    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert artifact.artifact_type == ArtifactType.STL

    bounds = assert_valid_stl(artifact.data)
    # Footprint can extend slightly past the nominal 102mm because the corner
    # pillar notches push outward — give it a wider tolerance than the others.
    assert_close(bounds.width, 102.0, tolerance=4.0)
    assert_close(bounds.depth, 102.0, tolerance=4.0)
    assert_close(bounds.height, 100.0)
