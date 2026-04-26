from __future__ import annotations

import math
import re

from labsmith.models import PartRequest, PartType


STANDARD_GRIDS: dict[int, tuple[int, int]] = {
    6: (2, 3),
    12: (3, 4),
    24: (4, 6),
    48: (6, 8),
    96: (8, 12),
    384: (16, 24),
}

TUBE_DIAMETER_BY_VOLUME_ML: dict[float, float] = {
    0.2: 6.0,
    0.5: 8.0,
    1.5: 11.0,
    2.0: 11.0,
    5.0: 17.0,
    15.0: 17.0,
    50.0: 30.0,
}


class RuleBasedParser:
    """Small deterministic parser for the initial MVP and test fixtures."""

    def parse(self, prompt: str) -> PartRequest:
        text = prompt.strip()
        normalized = text.lower()
        part_type = self._detect_part_type(normalized)
        request = PartRequest(part_type=part_type, source_prompt=text)

        request.well_count = self._extract_count(normalized, "well")
        request.rows, request.cols = self._extract_grid(normalized, request.well_count)
        if request.rows is not None and request.cols is not None and request.well_count is None:
            request.well_count = request.rows * request.cols
        request.diameter_mm = self._extract_dimension(normalized, "diameter")
        request.spacing_mm = self._extract_dimension(normalized, "spacing")
        request.depth_mm = self._extract_dimension(normalized, "depth")
        request.well_width_mm = self._extract_dimension(normalized, "width")
        request.well_height_mm = self._extract_dimension(normalized, "height")
        request.tube_volume_ml = self._extract_volume(normalized)

        return self._apply_part_defaults(request)

    def _detect_part_type(self, text: str) -> PartType:
        if "tube rack" in text or ("rack" in text and "tube" in text):
            return PartType.TUBE_RACK
        if "gel" in text and "comb" in text:
            return PartType.GEL_COMB
        if "microfluidic" in text:
            return PartType.MICROFLUIDIC_CHANNEL_MOLD
        if "multi-well" in text or "multiwell" in text:
            return PartType.MULTI_WELL_MOLD
        raise ValueError("Could not identify a supported lab part type from the prompt.")

    def _extract_count(self, text: str, noun: str) -> int | None:
        match = re.search(rf"(\d+)\s*[- ]?{noun}s?", text)
        return int(match.group(1)) if match else None

    def _extract_grid(self, text: str, count: int | None) -> tuple[int | None, int | None]:
        grid_match = re.search(r"(\d+)\s*(?:x|by)\s*(\d+)", text)
        if grid_match:
            return int(grid_match.group(1)), int(grid_match.group(2))
        if count in STANDARD_GRIDS:
            return STANDARD_GRIDS[count]
        if count is not None:
            rows = int(math.sqrt(count))
            while rows > 1:
                if count % rows == 0:
                    return rows, count // rows
                rows -= 1
        return None, None

    def _extract_dimension(self, text: str, label: str) -> float | None:
        patterns = [
            rf"(\d+(?:\.\d+)?)\s*mm\s+{label}",
            rf"{label}\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)\s*mm",
            rf"(\d+(?:\.\d+)?)\s*millimeter\s+{label}",
            rf"{label}\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)\s*millimeters?",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return float(match.group(1))
        return None

    def _extract_volume(self, text: str) -> float | None:
        match = re.search(r"(\d+(?:\.\d+)?)\s*ml", text)
        return float(match.group(1)) if match else None

    def _apply_part_defaults(self, request: PartRequest) -> PartRequest:
        if request.part_type == PartType.TUBE_RACK:
            if request.tube_volume_ml and request.diameter_mm is None:
                request.diameter_mm = TUBE_DIAMETER_BY_VOLUME_ML.get(request.tube_volume_ml)
                if request.diameter_mm is not None:
                    request.notes.append(
                        f"Estimated tube opening diameter from {request.tube_volume_ml:g} mL tubes."
                    )
            if request.rows is None or request.cols is None:
                request.rows = request.rows or 4
                request.cols = request.cols or 6
                request.well_count = request.rows * request.cols
                request.notes.append("Defaulted tube rack layout to 4 x 6.")
            if request.spacing_mm is None and request.diameter_mm is not None:
                request.spacing_mm = request.diameter_mm + 4.0
                request.notes.append("Defaulted spacing to tube diameter plus 4.0 mm.")
        if request.part_type == PartType.GEL_COMB:
            request.well_count = request.well_count or 10
            if request.well_width_mm is None:
                request.well_width_mm = 5.0
                request.notes.append("Defaulted gel comb well width to 5.0 mm.")
            if request.well_height_mm is None:
                request.well_height_mm = 1.5
                request.notes.append("Defaulted gel comb tooth thickness to 1.5 mm.")
            if request.depth_mm is None:
                request.depth_mm = 8.0
                request.notes.append("Defaulted gel comb tooth depth to 8.0 mm.")
        return request
