from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

_EXPORT_MAP = {
    "AlgorithmPreset": ("cubeanim.models", "AlgorithmPreset"),
    "BaseAlgorithmScene": ("cubeanim.scenes", "BaseAlgorithmScene"),
    "BaseRenderer": ("cubeanim.render_base", "BaseRenderer"),
    "CardsService": ("cubeanim.cards", "CardsService"),
    "CONTRAST_SAFE_CUBE_COLORS": ("cubeanim.palette", "CONTRAST_SAFE_CUBE_COLORS"),
    "CubeMoveExtended": ("cubeanim.animations", "CubeMoveExtended"),
    "CubeVisualConfig": ("cubeanim.setup", "CubeVisualConfig"),
    "ExecutionConfig": ("cubeanim.executor", "ExecutionConfig"),
    "FormulaConverter": ("cubeanim.formula", "FormulaConverter"),
    "FormulaScene": ("cubeanim.scenes", "FormulaScene"),
    "FormulaSyntaxError": ("cubeanim.formula", "FormulaSyntaxError"),
    "ManimRenderer": ("cubeanim.render_base", "ManimRenderer"),
    "MoveExecutor": ("cubeanim.executor", "MoveExecutor"),
    "PresetScene": ("cubeanim.scenes", "PresetScene"),
    "RenderGroup": ("cubeanim.models", "RenderGroup"),
    "RenderPlan": ("cubeanim.render_service", "RenderPlan"),
    "RenderRequest": ("cubeanim.render_service", "RenderRequest"),
    "RenderResult": ("cubeanim.render_service", "RenderResult"),
    "SceneSetup": ("cubeanim.setup", "SceneSetup"),
    "get_preset": ("cubeanim.presets", "get_preset"),
    "list_preset_names": ("cubeanim.presets", "list_preset_names"),
    "plan_formula_render": ("cubeanim.render_service", "plan_formula_render"),
    "render_formula": ("cubeanim.render_service", "render_formula"),
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
    from cubeanim.animations import CubeMoveExtended
    from cubeanim.cards import CardsService
    from cubeanim.executor import ExecutionConfig, MoveExecutor
    from cubeanim.formula import FormulaConverter, FormulaSyntaxError
    from cubeanim.models import AlgorithmPreset, RenderGroup
    from cubeanim.palette import CONTRAST_SAFE_CUBE_COLORS, validate_cube_palette
    from cubeanim.presets import get_preset, list_preset_names
    from cubeanim.render_base import BaseRenderer, ManimRenderer
    from cubeanim.render_service import RenderPlan, RenderRequest, RenderResult, plan_formula_render, render_formula
    from cubeanim.scenes import BaseAlgorithmScene, FormulaScene, PresetScene
    from cubeanim.setup import CubeVisualConfig, SceneSetup
    from cubeanim.state import solved_state_string, state_string_from_moves
    from cubeanim.utils import slugify_formula
