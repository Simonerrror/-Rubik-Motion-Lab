from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

_EXPORT_MAP = {
    "AlgorithmPreset": ("cubeanim.models", "AlgorithmPreset"),
    "CardsService": ("cubeanim.cards", "CardsService"),
    "CONTRAST_SAFE_CUBE_COLORS": ("cubeanim.palette", "CONTRAST_SAFE_CUBE_COLORS"),
    "FormulaConverter": ("cubeanim.formula", "FormulaConverter"),
    "FormulaSyntaxError": ("cubeanim.formula", "FormulaSyntaxError"),
    "RenderGroup": ("cubeanim.models", "RenderGroup"),
    "get_preset": ("cubeanim.presets", "get_preset"),
    "list_preset_names": ("cubeanim.presets", "list_preset_names"),
    "slugify_formula": ("cubeanim.utils", "slugify_formula"),
    "solved_state_string": ("cubeanim.state", "solved_state_string"),
    "state_string_from_moves": ("cubeanim.state", "state_string_from_moves"),
    "validate_cube_palette": ("cubeanim.palette", "validate_cube_palette"),
}

__all__ = sorted(_EXPORT_MAP.keys())


def __getattr__(name: str):
    target = _EXPORT_MAP.get(name)
    if target is None:
        raise AttributeError(f"module 'cubeanim' has no attribute {name!r}")
    module_name, attr_name = target
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals().keys()) | set(__all__))


if TYPE_CHECKING:
    from cubeanim.cards import CardsService
    from cubeanim.formula import FormulaConverter, FormulaSyntaxError
    from cubeanim.models import AlgorithmPreset, RenderGroup
    from cubeanim.palette import CONTRAST_SAFE_CUBE_COLORS, validate_cube_palette
    from cubeanim.presets import get_preset, list_preset_names
    from cubeanim.state import solved_state_string, state_string_from_moves
    from cubeanim.utils import slugify_formula
