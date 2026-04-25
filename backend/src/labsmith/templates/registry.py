from __future__ import annotations

from labsmith.models import PartType
from labsmith.templates.base import PartTemplate
from labsmith.templates.gel_comb import GelCombTemplate
from labsmith.templates.tma_mold import TmaMoldTemplate
from labsmith.templates.tube_rack import TubeRackTemplate


_TEMPLATES: dict[PartType, PartTemplate] = {
    PartType.TMA_MOLD: TmaMoldTemplate(),
    PartType.TUBE_RACK: TubeRackTemplate(),
    PartType.GEL_COMB: GelCombTemplate(),
}


def get_template(part_type: PartType) -> PartTemplate:
    try:
        return _TEMPLATES[part_type]
    except KeyError as exc:
        raise KeyError(f"No CAD template is registered for {part_type.value}.") from exc


def list_templates() -> list[PartTemplate]:
    return list(_TEMPLATES.values())
