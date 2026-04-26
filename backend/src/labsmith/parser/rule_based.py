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

DIMENSION_UNITS_TO_MM: dict[str, float] = {
    "": 1.0,
    "mm": 1.0,
    "millimeter": 1.0,
    "millimeters": 1.0,
    "cm": 10.0,
    "centimeter": 10.0,
    "centimeters": 10.0,
    "m": 1000.0,
    "meter": 1000.0,
    "meters": 1000.0,
    "in": 25.4,
    "inch": 25.4,
    "inches": 25.4,
    "ft": 304.8,
    "foot": 304.8,
    "feet": 304.8,
    "um": 0.001,
    "micron": 0.001,
    "microns": 0.001,
    "micrometer": 0.001,
    "micrometers": 0.001,
    "nm": 0.000001,
    "nanometer": 0.000001,
    "nanometers": 0.000001,
}

DIMENSION_UNIT_PATTERN = (
    r"millimeters?|centimeters?|micrometers?|nanometers?|meters?|"
    r"inches|inch|feet|foot|mm|cm|um|nm|in|ft|m"
)
DIMENSION_END_PATTERN = (
    r"(?=\s*(?:[,.;]|and\b|with\b|tube\b|diameter\b|spacing\b|depth\b|"
    r"width\b|height\b|length\b|tall\b|$))"
)
BOUNDING_CONTEXT_PATTERN = re.compile(
    r"\b(fit|fits|inside|within|drawer|bed|box|space|footprint|envelope|"
    r"maximum|max|under|less than|no larger|no bigger|no wider|no taller|"
    r"no deeper|at most)\b"
)

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
        return self._parse_into_request(normalized, request)

    def parse_update(self, prompt: str, base_request: PartRequest) -> PartRequest:
        text = prompt.strip()
        normalized = text.lower()
        request = base_request.model_copy(deep=True)
        request.source_prompt = text
        updated = self._parse_into_request(normalized, request, require_change=True)
        return updated

    def _parse_into_request(
        self,
        normalized: str,
        request: PartRequest,
        *,
        require_change: bool = False,
    ) -> PartRequest:
        changed = False

        well_count = self._extract_count(normalized, "well")
        rows, cols = self._extract_grid(normalized, well_count)
        if well_count is not None:
            request.well_count = well_count
            changed = True
        if rows is not None or cols is not None:
            request.rows = rows
            request.cols = cols
            changed = True
        if request.rows is not None and request.cols is not None and well_count is None:
            request.well_count = request.rows * request.cols
        diameter = self._extract_dimension(normalized, "diameter")
        spacing = self._extract_dimension(normalized, "spacing")
        depth = self._extract_dimension(normalized, "depth")
        width = self._extract_dimension(normalized, "width")
        height = self._extract_dimension(normalized, "height")
        tube_volume = self._extract_volume(normalized)
        max_width, max_depth, max_height = self._extract_bounding_box(normalized)

        if diameter is not None:
            request.diameter_mm = diameter
            changed = True
        if spacing is not None:
            request.spacing_mm = spacing
            changed = True
        if depth is not None:
            request.depth_mm = depth
            changed = True
        if width is not None:
            request.well_width_mm = width
            changed = True
        if request.part_type == PartType.TUBE_RACK:
            tube_height = height or self._extract_dimension(normalized, "length")
            tube_height = tube_height or self._extract_dimension(normalized, "tall")
            if tube_height is not None:
                request.depth_mm = tube_height
                changed = True
        elif height is not None:
            request.well_height_mm = height
            changed = True
        if tube_volume is not None:
            request.tube_volume_ml = tube_volume
            changed = True
        if max_width is not None:
            request.max_width_mm = max_width
            changed = True
        if max_depth is not None:
            request.max_depth_mm = max_depth
            changed = True
        if max_height is not None:
            request.max_height_mm = max_height
            changed = True

        if require_change and not changed and self._mentions_dimension_label(normalized):
            raise ValueError(
                "I use millimeters by default. Please write tube dimensions as bare "
                "numbers or recognized units, for example 'diameter 11, height 40'."
            )
        if require_change and not changed:
            raise ValueError("Could not identify any supported parameter changes from the prompt.")
        return self._apply_part_defaults(request)

    def _detect_part_type(self, text: str) -> PartType:
        # Check more specific patterns first so "pipette tip rack" doesn't
        # match the generic tube_rack rule.
        if "pipette tip" in text or "tip rack" in text or "tip box" in text:
            return PartType.PIPETTE_TIP_RACK
        if "petri" in text:
            return PartType.PETRI_DISH_STAND
        if "tube rack" in text or ("rack" in text and "tube" in text):
            return PartType.TUBE_RACK
        if "gel" in text and "comb" in text:
            return PartType.GEL_COMB
        if "microfluidic" in text:
            return PartType.MICROFLUIDIC_CHANNEL_MOLD
        raise ValueError("Could not identify a supported lab part type from the prompt.")

    def _extract_count(self, text: str, noun: str) -> int | None:
        match = re.search(rf"(\d+)\s*[- ]?{noun}s?", text)
        return int(match.group(1)) if match else None

    def _extract_grid(self, text: str, count: int | None) -> tuple[int | None, int | None]:
        for grid_match in re.finditer(r"(\d+)\s*(?:x|by)\s*(\d+)", text):
            prefix = text[max(0, grid_match.start() - 40) : grid_match.start()]
            suffix = text[grid_match.end() : grid_match.end() + 24]
            # Dimension constraints like "fit within 120 x 80 x 50 mm" are
            # parsed as a bounding box, not as a 120-by-80 rack grid.
            if re.match(r"\s*(?:x|by)\s*\d", suffix):
                continue
            if re.match(rf"\s*(?:{DIMENSION_UNIT_PATTERN})\b", suffix):
                continue
            if BOUNDING_CONTEXT_PATTERN.search(prefix):
                continue
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
            rf"(\d+(?:\.\d+)?)\s*({DIMENSION_UNIT_PATTERN})?\b\s+{label}\b",
            rf"{label}\s*(?:is|of|=|:)?\s*(\d+(?:\.\d+)?)\s*"
            rf"({DIMENSION_UNIT_PATTERN})?\b{DIMENSION_END_PATTERN}",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                unit = match.group(2) or ""
                return float(match.group(1)) * DIMENSION_UNITS_TO_MM[unit]
        return None

    def _extract_bounding_box(
        self, text: str
    ) -> tuple[float | None, float | None, float | None]:
        max_width = self._extract_dimension_limit(text, "width")
        max_depth = self._extract_dimension_limit(text, "depth")
        max_height = self._extract_dimension_limit(text, "height")
        max_height = max_height or self._extract_dimension_limit(text, "tall")

        for match in re.finditer(
            rf"(\d+(?:\.\d+)?)\s*({DIMENSION_UNIT_PATTERN})?\s*"
            rf"(?:x|by)\s*"
            rf"(\d+(?:\.\d+)?)\s*({DIMENSION_UNIT_PATTERN})?"
            rf"(?:\s*(?:x|by)\s*"
            rf"(\d+(?:\.\d+)?)\s*({DIMENSION_UNIT_PATTERN})?)?",
            text,
        ):
            before = text[max(0, match.start() - 48) : match.start()]
            after = text[match.end() : match.end() + 48]
            has_unit = any(match.group(index) for index in (2, 4, 6))
            has_constraint_before = BOUNDING_CONTEXT_PATTERN.search(before) is not None
            has_constraint_after = (
                BOUNDING_CONTEXT_PATTERN.search(after) is not None
                and (has_unit or match.group(5) is not None)
            )
            if not (has_constraint_before or has_constraint_after):
                continue

            unit = match.group(6) or match.group(4) or match.group(2) or ""
            first_unit = match.group(2) or unit
            second_unit = match.group(4) or unit
            third_unit = match.group(6) or unit

            max_width = max_width or float(match.group(1)) * DIMENSION_UNITS_TO_MM[first_unit]
            max_depth = max_depth or float(match.group(3)) * DIMENSION_UNITS_TO_MM[second_unit]
            if match.group(5) is not None:
                max_height = max_height or float(match.group(5)) * DIMENSION_UNITS_TO_MM[third_unit]
            break

        return max_width, max_depth, max_height

    def _extract_dimension_limit(self, text: str, label: str) -> float | None:
        label_pattern = "height|tall" if label in {"height", "tall"} else label
        patterns = [
            rf"(?:max(?:imum)?|at most|under|less than|no more than|no larger than)\s+"
            rf"(?:{label_pattern})\s*(?:of|is|=|:)?\s*"
            rf"(\d+(?:\.\d+)?)\s*({DIMENSION_UNIT_PATTERN})?\b",
            rf"(?:{label_pattern})\s*(?:must be|should be|is|=|:)?\s*"
            rf"(?:under|less than|no more than|no larger than|at most|<=)\s*"
            rf"(\d+(?:\.\d+)?)\s*({DIMENSION_UNIT_PATTERN})?\b",
        ]
        if label == "width":
            patterns.append(
                rf"no\s+wider\s+than\s*(\d+(?:\.\d+)?)\s*({DIMENSION_UNIT_PATTERN})?\b"
            )
        if label in {"height", "tall"}:
            patterns.append(
                rf"no\s+taller\s+than\s*(\d+(?:\.\d+)?)\s*({DIMENSION_UNIT_PATTERN})?\b"
            )
        if label == "depth":
            patterns.append(
                rf"no\s+deeper\s+than\s*(\d+(?:\.\d+)?)\s*({DIMENSION_UNIT_PATTERN})?\b"
            )

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                unit = match.group(2) or ""
                return float(match.group(1)) * DIMENSION_UNITS_TO_MM[unit]
        return None

    def _mentions_dimension_label(self, text: str) -> bool:
        return any(
            re.search(rf"\b{label}\b", text)
            for label in (
                "diameter",
                "spacing",
                "depth",
                "width",
                "height",
                "length",
                "tall",
                "drawer",
                "bed",
                "footprint",
                "envelope",
            )
        )

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
        if request.part_type == PartType.PIPETTE_TIP_RACK:
            if request.rows is None or request.cols is None:
                request.rows = request.rows or 8
                request.cols = request.cols or 12
                request.well_count = request.rows * request.cols
                request.notes.append("Defaulted pipette tip rack to 8 x 12 (96 tips).")
            if request.diameter_mm is None:
                request.diameter_mm = 6.5
                request.notes.append("Defaulted tip slot diameter to 6.5 mm (200 uL tip).")
            if request.depth_mm is None:
                request.depth_mm = 50.0
                request.notes.append("Defaulted tip rack height to 50.0 mm.")
            if request.spacing_mm is None:
                request.spacing_mm = 9.0
                request.notes.append("Defaulted tip spacing to 9.0 mm (SBS standard).")
        if request.part_type == PartType.PETRI_DISH_STAND:
            if request.well_count is None:
                request.well_count = 5
                request.notes.append("Defaulted to a 5-slot stand.")
            if request.diameter_mm is None:
                request.diameter_mm = 90.0
                request.notes.append("Defaulted dish diameter to 90.0 mm (standard).")
            if request.depth_mm is None:
                # depth_mm here is the total stand height (well_count * slot_height + base)
                request.depth_mm = 100.0
                request.notes.append("Defaulted stand height to 100.0 mm.")
        return request
