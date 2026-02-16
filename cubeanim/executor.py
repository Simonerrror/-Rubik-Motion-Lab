from __future__ import annotations

from functools import lru_cache
from dataclasses import dataclass

from manim import DR, DOWN, LEFT, RIGHT, RoundedRectangle, Text, ThreeDScene, UL, UP, VGroup
from manim_rubikscube import RubiksCube

from cubeanim.animations import CubeMoveConcurrent, CubeMoveExtended
from cubeanim.state import state_string_from_moves
from cubeanim.utils import wrap_formula_for_overlay


@dataclass(frozen=True)
class ExecutionConfig:
    run_time: float = 0.55
    end_wait: float = 1.0
    pre_start_wait: float = 0.5
    prepare_case_from_inverse: bool = True
    show_algorithm_name: bool = True
    name_font_size: int = 30
    name_shift_right: float = 0.45
    name_shift_down: float = 0.26
    name_color: str = "#1D2430"
    name_font_candidates: tuple[str, ...] = (
        "Avenir Next",
        "Helvetica Neue",
        "SF Pro Display",
        "DejaVu Sans",
        "Arial",
    )
    name_font_weight: str = "MEDIUM"
    show_formula_overlay: bool = True
    formula_font_size: int = 24
    formula_shift_left: float = 0.06
    formula_shift_up: float = 0.20
    formula_panel_extra_shift_right: float = 0.22
    formula_color: str = "#1D2430"
    formula_max_chars_per_line: int = 32
    formula_max_lines: int = 2
    formula_panel_width: float = 4.2
    formula_panel_height: float = 1.05
    formula_panel_corner_radius: float = 0.16
    formula_panel_fill_color: str = "#EFF1F5"
    formula_panel_fill_opacity: float = 0.90
    formula_panel_stroke_color: str = "#B8C0CC"
    formula_panel_stroke_width: float = 2.2
    formula_panel_text_padding_x: float = 0.22
    formula_panel_text_padding_y: float = 0.16
    formula_text_line_spacing: float = 0.12


class MoveExecutor:
    @staticmethod
    @lru_cache(maxsize=1)
    def _available_fonts() -> set[str]:
        try:
            import manimpango

            return set(manimpango.list_fonts())
        except Exception:
            return set()

    @staticmethod
    def _pick_font(candidates: tuple[str, ...]) -> str | None:
        available = MoveExecutor._available_fonts()
        if not available:
            return None
        for font in candidates:
            if font in available:
                return font
        return None

    @staticmethod
    def _add_algorithm_name(
        scene: ThreeDScene,
        algorithm_name: str | None,
        config: ExecutionConfig,
    ) -> None:
        if not config.show_algorithm_name:
            return

        name_text = (algorithm_name or "").strip()
        if not name_text:
            return

        text_kwargs: dict[str, object] = {
            "font_size": config.name_font_size,
            "color": config.name_color,
            "weight": config.name_font_weight,
        }
        picked_font = MoveExecutor._pick_font(config.name_font_candidates)
        if picked_font:
            text_kwargs["font"] = picked_font

        text = Text(name_text, **text_kwargs)
        text.to_corner(UL)
        text.shift(RIGHT * config.name_shift_right + DOWN * config.name_shift_down)
        text.set_z_index(1000)
        scene.add_fixed_in_frame_mobjects(text)
        scene.add(text)

    @staticmethod
    def _add_formula_overlay(
        scene: ThreeDScene,
        formula_text: str | None,
        config: ExecutionConfig,
    ) -> None:
        if not config.show_formula_overlay:
            return

        formula = (formula_text or "").strip()
        if not formula:
            return

        wrapped = wrap_formula_for_overlay(
            formula=formula,
            max_chars_per_line=config.formula_max_chars_per_line,
            max_lines=config.formula_max_lines,
        )
        if not wrapped:
            return

        panel = RoundedRectangle(
            corner_radius=config.formula_panel_corner_radius,
            width=config.formula_panel_width,
            height=config.formula_panel_height,
        )
        panel.set_fill(
            color=config.formula_panel_fill_color,
            opacity=config.formula_panel_fill_opacity,
        )
        panel.set_stroke(
            color=config.formula_panel_stroke_color,
            width=config.formula_panel_stroke_width,
        )
        panel.to_corner(DR)
        panel.shift(
            LEFT * config.formula_shift_left
            + UP * config.formula_shift_up
            + RIGHT * config.formula_panel_extra_shift_right
        )
        panel.set_z_index(990)

        lines = [line for line in wrapped.splitlines() if line.strip()]
        if not lines:
            return

        text_group = VGroup(
            *[
                Text(
                    line,
                    font_size=config.formula_font_size,
                    color=config.formula_color,
                )
                for line in lines
            ]
        )
        text_group.arrange(
            DOWN,
            aligned_edge=LEFT,
            buff=config.formula_text_line_spacing,
        )

        text_max_width = panel.width - 2 * config.formula_panel_text_padding_x
        text_max_height = panel.height - 2 * config.formula_panel_text_padding_y
        if text_group.width > text_max_width:
            text_group.scale_to_fit_width(text_max_width)
        if text_group.height > text_max_height:
            text_group.scale_to_fit_height(text_max_height)

        target = panel.get_center().copy()
        target[0] = panel.get_left()[0] + config.formula_panel_text_padding_x + text_group.width / 2
        text_group.move_to(target)
        text_group.set_z_index(1000)
        scene.add_fixed_in_frame_mobjects(panel, text_group)
        scene.add(panel, text_group)

    @staticmethod
    def play(
        scene: ThreeDScene,
        cube: RubiksCube,
        move_steps: list[list[str]],
        config: ExecutionConfig,
        algorithm_name: str | None = None,
        formula_text: str | None = None,
        inverse_steps: list[list[str]] | None = None,
    ) -> None:
        if config.prepare_case_from_inverse and inverse_steps:
            inverse_flat = [move for step in inverse_steps for move in step]
            cube.set_state(state_string_from_moves(inverse_flat))

        MoveExecutor._add_algorithm_name(scene, algorithm_name, config)
        MoveExecutor._add_formula_overlay(scene, formula_text, config)
        scene.add(cube)
        scene.wait(config.pre_start_wait)

        for step in move_steps:
            if len(step) == 1:
                scene.play(CubeMoveExtended(cube, step[0]), run_time=config.run_time)
                continue
            scene.play(CubeMoveConcurrent(cube, step), run_time=config.run_time)

        scene.wait(config.end_wait)
