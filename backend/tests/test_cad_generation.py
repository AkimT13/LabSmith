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
