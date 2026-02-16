from __future__ import annotations

import os

from manim import ThreeDScene

from cubeanim.executor import ExecutionConfig, MoveExecutor
from cubeanim.formula import FormulaConverter
from cubeanim.models import AlgorithmPreset, RenderGroup
from cubeanim.presets import get_preset
from cubeanim.setup import CubeVisualConfig, SceneSetup
from cubeanim.utils import normalize_formula_text


def _parse_group(value: str | None) -> RenderGroup:
    if not value:
        return RenderGroup.NO_GROUP

    normalized = value.strip().upper()
    for group in RenderGroup:
        if group.value == normalized:
            return group
    return RenderGroup.NO_GROUP


class BaseAlgorithmScene(ThreeDScene):
    PRESET_NAME: str | None = None
    FORMULA: str | None = None
    NAME: str | None = None
    GROUP: RenderGroup = RenderGroup.NO_GROUP
    REPEAT: int = 1

    VISUAL_CONFIG = CubeVisualConfig()
    EXECUTION_CONFIG = ExecutionConfig()

    def resolve_algorithm(self) -> AlgorithmPreset:
        if self.PRESET_NAME:
            return get_preset(self.PRESET_NAME)

        if self.FORMULA:
            return AlgorithmPreset(
                name=self.NAME or "Formula",
                formula=self.FORMULA,
                group=self.GROUP,
                repeat=self.REPEAT,
            )

        raise ValueError("Scene must define PRESET_NAME or FORMULA")

    def construct(self) -> None:
        preset = self.resolve_algorithm()
        cube = SceneSetup.apply(self, self.VISUAL_CONFIG)
        moves = FormulaConverter.convert(preset.formula, repeat=preset.repeat)
        inverse_moves = FormulaConverter.invert_moves(moves)
        display_formula = normalize_formula_text(preset.formula)
        if preset.repeat > 1:
            display_formula = f"({display_formula})^{preset.repeat}"
        MoveExecutor.play(
            self,
            cube,
            moves,
            self.EXECUTION_CONFIG,
            algorithm_name=preset.name,
            formula_text=display_formula,
            inverse_moves=inverse_moves,
        )


class PresetScene(BaseAlgorithmScene):
    ENV_PRESET = "CUBEANIM_PRESET"

    def resolve_algorithm(self) -> AlgorithmPreset:
        if self.PRESET_NAME:
            return get_preset(self.PRESET_NAME)

        preset_name = os.environ.get(self.ENV_PRESET, "").strip()
        if not preset_name:
            raise ValueError(
                f"Environment variable {self.ENV_PRESET} must be set for PresetScene"
            )
        return get_preset(preset_name)


class FormulaScene(BaseAlgorithmScene):
    ENV_FORMULA = "CUBEANIM_FORMULA"
    ENV_GROUP = "CUBEANIM_GROUP"
    ENV_NAME = "CUBEANIM_NAME"
    ENV_REPEAT = "CUBEANIM_REPEAT"

    def resolve_algorithm(self) -> AlgorithmPreset:
        formula = os.environ.get(self.ENV_FORMULA, "").strip()
        if not formula:
            raise ValueError(
                f"Environment variable {self.ENV_FORMULA} must be set for FormulaScene"
            )

        name = os.environ.get(self.ENV_NAME, "").strip() or "Formula"
        group = _parse_group(os.environ.get(self.ENV_GROUP))

        repeat_raw = os.environ.get(self.ENV_REPEAT, "1").strip() or "1"
        try:
            repeat = int(repeat_raw)
        except ValueError as exc:
            raise ValueError(
                f"Environment variable {self.ENV_REPEAT} must be an integer"
            ) from exc

        return AlgorithmPreset(
            name=name,
            formula=formula,
            group=group,
            repeat=repeat,
        )
