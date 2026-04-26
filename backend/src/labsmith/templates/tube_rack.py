from __future__ import annotations

from labsmith.models import EstimatedDimensions, PartRequest, PartType, TemplateSpec


class TubeRackTemplate:
    spec = TemplateSpec(
        part_type=PartType.TUBE_RACK,
        name="Tube rack",
        description="Grid rack for microcentrifuge, PCR, or conical tubes.",
        required_parameters=["rows", "cols", "diameter_mm", "spacing_mm"],
        optional_parameters=["tube_volume_ml", "depth_mm"],
    )

    def estimate_dimensions(self, request: PartRequest) -> EstimatedDimensions:
        rows = request.rows or 4
        cols = request.cols or 6
        diameter = request.diameter_mm or 11.0
        spacing = request.spacing_mm or diameter + 4.0
        plate_margin = max(6.0, diameter / 2)
        width = (cols - 1) * spacing + diameter + plate_margin * 2
        depth = (rows - 1) * spacing + diameter + plate_margin * 2
        return EstimatedDimensions(
            width_mm=width,
            depth_mm=depth,
            height_mm=request.depth_mm or 40.0,
        )
