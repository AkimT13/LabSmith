from labsmith.models import PartType
from labsmith.parser import RuleBasedParser


def test_parser_extracts_tube_rack_parameters() -> None:
    parser = RuleBasedParser()

    result = parser.parse(
        "Create a 4 x 6 tube rack with 11 mm diameter, 15 mm spacing, and 50 mm height"
    )

    assert result.part_type == PartType.TUBE_RACK
    assert result.rows == 4
    assert result.cols == 6
    assert result.well_count == 24
    assert result.diameter_mm == 11.0
    assert result.spacing_mm == 15.0
    assert result.depth_mm == 50.0


def test_parser_extracts_tube_rack_defaults_from_volume() -> None:
    parser = RuleBasedParser()

    result = parser.parse("Design a rack for 1.5 mL tubes that fits in a standard ice bucket")

    assert result.part_type == PartType.TUBE_RACK
    assert result.rows == 4
    assert result.cols == 6
    assert result.diameter_mm == 11.0
    assert result.spacing_mm == 15.0
    assert result.depth_mm is None


def test_parser_updates_existing_tube_rack_from_dimension_reply() -> None:
    parser = RuleBasedParser()
    base = parser.parse("Create a 4 x 6 tube rack with 15 mm spacing")

    result = parser.parse_update("The tubes are 11 mm diameter and 50 mm tall", base)

    assert result.part_type == PartType.TUBE_RACK
    assert result.rows == 4
    assert result.cols == 6
    assert result.diameter_mm == 11.0
    assert result.spacing_mm == 15.0
    assert result.depth_mm == 50.0


def test_parser_extracts_gel_comb_defaults() -> None:
    parser = RuleBasedParser()

    result = parser.parse("Make a gel electrophoresis comb with 10 wells")

    assert result.part_type == PartType.GEL_COMB
    assert result.well_count == 10
    assert result.well_width_mm == 5.0
    assert result.well_height_mm == 1.5
    assert result.depth_mm == 8.0


def test_parser_rejects_unknown_part_type() -> None:
    parser = RuleBasedParser()

    try:
        parser.parse("Make a bracket for a microscope camera")
    except ValueError as exc:
        assert "supported lab part type" in str(exc)
    else:
        raise AssertionError("Expected parser to reject unknown part type.")


def test_parser_detects_pipette_tip_rack() -> None:
    """'tip rack' should be PIPETTE_TIP_RACK, NOT generic tube_rack — order
    of detection matters because both contain the word 'rack'."""
    parser = RuleBasedParser()

    result = parser.parse("Design a 96-tip pipette tip rack")

    assert result.part_type == PartType.PIPETTE_TIP_RACK
    assert result.rows == 8
    assert result.cols == 12
    assert result.well_count == 96


def test_parser_detects_petri_dish_stand() -> None:
    parser = RuleBasedParser()

    result = parser.parse("I need a petri dish stand for my incubator")

    assert result.part_type == PartType.PETRI_DISH_STAND
    assert result.well_count == 5  # default
    assert result.diameter_mm == 90.0  # default


def test_parser_detects_multi_well_mold() -> None:
    parser = RuleBasedParser()

    result = parser.parse("Design a 96 well plate mold")

    assert result.part_type == PartType.MULTI_WELL_MOLD
    assert result.rows == 8
    assert result.cols == 12
