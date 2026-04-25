from __future__ import annotations

from labsmith.models import EstimatedDimensions, PartRequest, PartType, TemplateSpec


class GelCombTemplate:
    spec = TemplateSpec(
        part_type=PartType.GEL_COMB,
        name="Gel electrophoresis comb",
        description="Parametric comb for casting wells in agarose or PAGE gels.",
        required_parameters=["well_count", "well_width_mm", "well_height_mm", "depth_mm"],
        optional_parameters=["spacing_mm"],
    )

    def estimate_dimensions(self, request: PartRequest) -> EstimatedDimensions:
        well_count = request.well_count or 10
        well_width = request.well_width_mm or 5.0
        spacing = request.spacing_mm or 2.0
        tooth_depth = request.depth_mm or 8.0
        rail_margin = 8.0
        width = well_count * well_width + (well_count - 1) * spacing + rail_margin * 2
        return EstimatedDimensions(width_mm=width, depth_mm=tooth_depth + 4.0, height_mm=12.0)
