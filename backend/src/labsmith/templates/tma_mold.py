from __future__ import annotations

from labsmith.models import EstimatedDimensions, PartRequest, PartType, TemplateSpec


class TmaMoldTemplate:
    spec = TemplateSpec(
        part_type=PartType.TMA_MOLD,
        name="Tissue microarray mold",
        description="Grid mold for arranging cylindrical tissue cores.",
        required_parameters=["rows", "cols", "diameter_mm", "spacing_mm", "depth_mm"],
    )

    def estimate_dimensions(self, request: PartRequest) -> EstimatedDimensions:
        rows = request.rows or 1
        cols = request.cols or 1
        diameter = request.diameter_mm or 1.0
        spacing = request.spacing_mm or diameter + 1.0
        depth = request.depth_mm or 3.0
        margin = max(3.0, diameter * 2)
        width = (cols - 1) * spacing + diameter + margin * 2
        height = (rows - 1) * spacing + diameter + margin * 2
        return EstimatedDimensions(width_mm=width, depth_mm=height, height_mm=depth + 2.0)
