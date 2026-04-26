import pytest
from labsmith.models import PartRequest, PartType
from labsmith.templates import get_template, list_templates


def test_template_registry_lists_initial_cad_templates() -> None:
    part_types = {template.spec.part_type for template in list_templates()}

    assert part_types == {PartType.TUBE_RACK, PartType.GEL_COMB}


def test_tube_rack_template_estimates_dimensions() -> None:
    template = get_template(PartType.TUBE_RACK)
    request = PartRequest(
        part_type=PartType.TUBE_RACK,
        rows=4,
        cols=6,
        diameter_mm=11.0,
        spacing_mm=15.0,
    )

    dimensions = template.estimate_dimensions(request)

    assert dimensions.width_mm > 80
    assert dimensions.depth_mm > 50
    assert dimensions.height_mm == 40.0


def test_unregistered_template_raises_key_error() -> None:
    with pytest.raises(KeyError):
        get_template(PartType.MICROFLUIDIC_CHANNEL_MOLD)
