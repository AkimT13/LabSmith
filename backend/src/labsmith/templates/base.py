from __future__ import annotations

from typing import Protocol

from labsmith.models import EstimatedDimensions, PartRequest, TemplateSpec


class PartTemplate(Protocol):
    spec: TemplateSpec

    def estimate_dimensions(self, request: PartRequest) -> EstimatedDimensions:
        """Estimate the bounding box for a requested part before CAD generation."""
