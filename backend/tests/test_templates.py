import pytest

from labsmith.models import PartRequest, PartType
from labsmith.templates import get_template, list_templates


def test_template_registry_lists_initial_cad_templates() -> None:
    part_types = {template.spec.part_type for template in list_templates()}

    assert part_types == {PartType.TMA_MOLD, PartType.TUBE_RACK, PartType.GEL_COMB}


def test_tma_template_estimates_dimensions() -> None:
    template = get_template(PartType.TMA_MOLD)
    request = PartRequest(
        part_type=PartType.TMA_MOLD,
        rows=8,
        cols=12,
        diameter_mm=1.0,
        spacing_mm=2.0,
        depth_mm=3.0,
    )

    dimensions = template.estimate_dimensions(request)

    assert dimensions.width_mm > 20
    assert dimensions.depth_mm > 10
    assert dimensions.height_mm == 5.0


def test_unregistered_template_raises_key_error() -> None:
    with pytest.raises(KeyError):
        get_template(PartType.MICROFLUIDIC_CHANNEL_MOLD)
