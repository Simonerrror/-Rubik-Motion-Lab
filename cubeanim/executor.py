from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Sequence

from manim import (
    Arrow,
    DR,
    DoubleArrow,
    DOWN,
    LEFT,
    Rectangle,
    RIGHT,
    RoundedRectangle,
    Text,
    ThreeDScene,
    UL,
    UR,
    UP,
    VGroup,
    rate_functions,
)
from manim_rubikscube import RubiksCube

from cubeanim.animations import CubeMoveConcurrent, CubeMoveExtended
from cubeanim.oll import OLLTopViewData
from cubeanim.palette import CONTRAST_SAFE_CUBE_COLORS, FACE_ORDER
from cubeanim.pll import PLLTopViewData
from cubeanim.state import state_string_from_moves
from cubeanim.utils import wrap_formula_for_overlay


@dataclass(frozen=True)
class ExecutionConfig:
    run_time: float = 0.65
    double_turn_multiplier: float = 1.7
    inter_move_pause_ratio: float = 0.05
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
    show_oll_top_view_overlay: bool = True
    oll_top_view_shift_left: float = 0.24
    oll_top_view_shift_down: float = 0.18
    oll_top_view_panel_width: float = 2.45
    oll_top_view_panel_height: float = 2.45
    oll_top_view_panel_corner_radius: float = 0.14
    oll_top_view_panel_fill_color: str = "#EFF1F5"
    oll_top_view_panel_fill_opacity: float = 0.92
    oll_top_view_panel_stroke_color: str = "#B8C0CC"
    oll_top_view_panel_stroke_width: float = 2.0
    oll_top_view_grid_size: float = 1.45
    oll_top_view_grid_stroke_color: str = "#11151B"
    oll_top_view_grid_stroke_width: float = 2.1
    oll_top_view_yellow_color: str = "#FDFF00"
    oll_top_view_gray_color: str = "#8E939B"
    oll_top_view_indicator_side_ratio: float = 0.30
    oll_top_view_indicator_short: float = 0.065
    oll_top_view_indicator_gap: float = 0.105
    oll_top_view_indicator_stroke_width: float = 1.4
    show_pll_top_view_overlay: bool = True
    pll_top_view_shift_left: float = 0.24
    pll_top_view_shift_down: float = 0.18
    pll_top_view_panel_width: float = 2.45
    pll_top_view_panel_height: float = 2.45
    pll_top_view_panel_corner_radius: float = 0.14
    pll_top_view_panel_fill_color: str = "#EFF1F5"
    pll_top_view_panel_fill_opacity: float = 0.92
    pll_top_view_panel_stroke_color: str = "#B8C0CC"
    pll_top_view_panel_stroke_width: float = 2.0
    pll_top_view_grid_size: float = 1.45
    pll_top_view_grid_stroke_color: str = "#11151B"
    pll_top_view_grid_stroke_width: float = 2.1
    pll_top_view_unknown_color: str = "#8E939B"
    pll_top_view_side_strip_side_ratio: float = 0.30
    pll_top_view_side_strip_short: float = 0.085
    pll_top_view_side_strip_gap: float = 0.105
    pll_top_view_side_strip_stroke_width: float = 1.4
    pll_top_view_arrow_color: str = "#11151B"
    pll_top_view_arrow_stroke_width: float = 6.0
    pll_top_view_arrow_buff: float = 0.11
    pll_top_view_arrow_tip_length: float = 0.14


class MoveExecutor:
    DEFAULT_MOVE_RATE_FUNC = rate_functions.ease_in_out_sine

    @staticmethod
    def _is_double_turn(move: str) -> bool:
        return move.endswith("2")

    @staticmethod
    def _step_run_time(step: list[str], config: ExecutionConfig) -> float:
        if step and all(MoveExecutor._is_double_turn(move) for move in step):
            return config.run_time * config.double_turn_multiplier
        return config.run_time

    @staticmethod
    def _inter_move_pause(config: ExecutionConfig) -> float:
        return config.run_time * config.inter_move_pause_ratio

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
    def _face_color_map(cube_face_colors: Sequence[str] | None) -> dict[str, str]:
        colors = cube_face_colors if cube_face_colors and len(cube_face_colors) == 6 else CONTRAST_SAFE_CUBE_COLORS
        return dict(zip(FACE_ORDER, colors, strict=True))

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
    def _add_oll_top_view_overlay(
        scene: ThreeDScene,
        oll_top_view_data: OLLTopViewData | None,
        config: ExecutionConfig,
    ) -> None:
        if not config.show_oll_top_view_overlay or oll_top_view_data is None:
            return

        panel = RoundedRectangle(
            corner_radius=config.oll_top_view_panel_corner_radius,
            width=config.oll_top_view_panel_width,
            height=config.oll_top_view_panel_height,
        )
        panel.set_fill(
            color=config.oll_top_view_panel_fill_color,
            opacity=config.oll_top_view_panel_fill_opacity,
        )
        panel.set_stroke(
            color=config.oll_top_view_panel_stroke_color,
            width=config.oll_top_view_panel_stroke_width,
        )
        panel.to_corner(UR)
        panel.shift(
            LEFT * config.oll_top_view_shift_left
            + DOWN * config.oll_top_view_shift_down
        )
        panel.set_z_index(980)

        grid_size = config.oll_top_view_grid_size
        indicator_long = grid_size * config.oll_top_view_indicator_side_ratio
        cell_size = grid_size / 3.0
        grid_center = panel.get_center()
        col_offsets = (-cell_size, 0.0, cell_size)
        row_offsets = (cell_size, 0.0, -cell_size)

        grid_cells = VGroup()
        for row, row_values in enumerate(oll_top_view_data.u_grid):
            for col, is_yellow in enumerate(row_values):
                cell = Rectangle(width=cell_size, height=cell_size)
                cell.set_fill(
                    color=(
                        config.oll_top_view_yellow_color
                        if is_yellow
                        else config.oll_top_view_gray_color
                    ),
                    opacity=1.0,
                )
                cell.set_stroke(
                    color=config.oll_top_view_grid_stroke_color,
                    width=config.oll_top_view_grid_stroke_width,
                )
                cell.move_to(
                    grid_center
                    + RIGHT * col_offsets[col]
                    + UP * row_offsets[row]
                )
                cell.set_z_index(992)
                grid_cells.add(cell)

        grid_border = Rectangle(width=grid_size, height=grid_size)
        grid_border.set_fill(opacity=0.0)
        grid_border.set_stroke(
            color=config.oll_top_view_grid_stroke_color,
            width=config.oll_top_view_grid_stroke_width + 0.7,
        )
        grid_border.move_to(grid_center)
        grid_border.set_z_index(993)

        indicators = VGroup()
        side_map = (
            ("top_b", "horizontal", +1),
            ("bottom_f", "horizontal", -1),
            ("left_l", "vertical", -1),
            ("right_r", "vertical", +1),
        )
        for attribute, orientation, sign in side_map:
            values = getattr(oll_top_view_data, attribute)
            for index, is_yellow in enumerate(values):
                if not is_yellow:
                    continue

                if orientation == "horizontal":
                    marker = Rectangle(
                        width=indicator_long,
                        height=config.oll_top_view_indicator_short,
                    )
                    marker_x = col_offsets[index]
                    marker_y = (
                        sign * (grid_size / 2.0 + config.oll_top_view_indicator_gap)
                        + sign * (config.oll_top_view_indicator_short / 2.0)
                    )
                else:
                    marker = Rectangle(
                        width=config.oll_top_view_indicator_short,
                        height=indicator_long,
                    )
                    marker_x = (
                        sign * (grid_size / 2.0 + config.oll_top_view_indicator_gap)
                        + sign * (config.oll_top_view_indicator_short / 2.0)
                    )
                    marker_y = row_offsets[index]

                marker.set_fill(color=config.oll_top_view_yellow_color, opacity=1.0)
                marker.set_stroke(
                    color=config.oll_top_view_grid_stroke_color,
                    width=config.oll_top_view_indicator_stroke_width,
                )
                marker.move_to(grid_center + RIGHT * marker_x + UP * marker_y)
                marker.set_z_index(994)
                indicators.add(marker)

        scene.add_fixed_in_frame_mobjects(panel, grid_cells, grid_border, indicators)
        scene.add(panel, grid_cells, grid_border, indicators)

    @staticmethod
    def _add_pll_top_view_overlay(
        scene: ThreeDScene,
        pll_top_view_data: PLLTopViewData | None,
        config: ExecutionConfig,
        cube_face_colors: Sequence[str] | None,
    ) -> None:
        if not config.show_pll_top_view_overlay or pll_top_view_data is None:
            return

        panel = RoundedRectangle(
            corner_radius=config.pll_top_view_panel_corner_radius,
            width=config.pll_top_view_panel_width,
            height=config.pll_top_view_panel_height,
        )
        panel.set_fill(
            color=config.pll_top_view_panel_fill_color,
            opacity=config.pll_top_view_panel_fill_opacity,
        )
        panel.set_stroke(
            color=config.pll_top_view_panel_stroke_color,
            width=config.pll_top_view_panel_stroke_width,
        )
        panel.to_corner(UR)
        panel.shift(
            LEFT * config.pll_top_view_shift_left
            + DOWN * config.pll_top_view_shift_down
        )
        panel.set_z_index(980)

        face_color_map = MoveExecutor._face_color_map(cube_face_colors)
        grid_size = config.pll_top_view_grid_size
        strip_long = grid_size * config.pll_top_view_side_strip_side_ratio
        cell_size = grid_size / 3.0
        grid_center = panel.get_center()
        col_offsets = (-cell_size, 0.0, cell_size)
        row_offsets = (cell_size, 0.0, -cell_size)

        def grid_point(row: int, col: int):
            return grid_center + RIGHT * col_offsets[col] + UP * row_offsets[row]

        grid_cells = VGroup()
        for row, row_values in enumerate(pll_top_view_data.u_grid):
            for col, face_color in enumerate(row_values):
                cell = Rectangle(width=cell_size, height=cell_size)
                cell.set_fill(
                    color=face_color_map.get(face_color, config.pll_top_view_unknown_color),
                    opacity=1.0,
                )
                cell.set_stroke(
                    color=config.pll_top_view_grid_stroke_color,
                    width=config.pll_top_view_grid_stroke_width,
                )
                cell.move_to(grid_point(row, col))
                cell.set_z_index(992)
                grid_cells.add(cell)

        grid_border = Rectangle(width=grid_size, height=grid_size)
        grid_border.set_fill(opacity=0.0)
        grid_border.set_stroke(
            color=config.pll_top_view_grid_stroke_color,
            width=config.pll_top_view_grid_stroke_width + 0.7,
        )
        grid_border.move_to(grid_center)
        grid_border.set_z_index(993)

        side_strips = VGroup()
        side_map = (
            ("top_b", "horizontal", +1),
            ("bottom_f", "horizontal", -1),
            ("left_l", "vertical", -1),
            ("right_r", "vertical", +1),
        )
        for attribute, orientation, sign in side_map:
            values = getattr(pll_top_view_data, attribute)
            for index, face_color in enumerate(values):
                if orientation == "horizontal":
                    strip = Rectangle(
                        width=strip_long,
                        height=config.pll_top_view_side_strip_short,
                    )
                    strip_x = col_offsets[index]
                    strip_y = (
                        sign * (grid_size / 2.0 + config.pll_top_view_side_strip_gap)
                        + sign * (config.pll_top_view_side_strip_short / 2.0)
                    )
                else:
                    strip = Rectangle(
                        width=config.pll_top_view_side_strip_short,
                        height=strip_long,
                    )
                    strip_x = (
                        sign * (grid_size / 2.0 + config.pll_top_view_side_strip_gap)
                        + sign * (config.pll_top_view_side_strip_short / 2.0)
                    )
                    strip_y = row_offsets[index]

                strip.set_fill(
                    color=face_color_map.get(face_color, config.pll_top_view_unknown_color),
                    opacity=1.0,
                )
                strip.set_stroke(
                    color=config.pll_top_view_grid_stroke_color,
                    width=config.pll_top_view_side_strip_stroke_width,
                )
                strip.move_to(grid_center + RIGHT * strip_x + UP * strip_y)
                strip.set_z_index(994)
                side_strips.add(strip)

        arrows = VGroup()
        for arrow_data in (*pll_top_view_data.corner_arrows, *pll_top_view_data.edge_arrows):
            start = grid_point(*arrow_data.start)
            end = grid_point(*arrow_data.end)
            if arrow_data.bidirectional:
                arrow = DoubleArrow(
                    start=start,
                    end=end,
                    buff=config.pll_top_view_arrow_buff,
                    stroke_width=config.pll_top_view_arrow_stroke_width,
                    tip_length=config.pll_top_view_arrow_tip_length,
                )
            else:
                arrow = Arrow(
                    start=start,
                    end=end,
                    buff=config.pll_top_view_arrow_buff,
                    stroke_width=config.pll_top_view_arrow_stroke_width,
                    tip_length=config.pll_top_view_arrow_tip_length,
                )
            arrow.set_color(config.pll_top_view_arrow_color)
            arrow.set_z_index(995)
            arrows.add(arrow)

        scene.add_fixed_in_frame_mobjects(panel, grid_cells, grid_border, side_strips, arrows)
        scene.add(panel, grid_cells, grid_border, side_strips, arrows)

    @staticmethod
    def play(
        scene: ThreeDScene,
        cube: RubiksCube,
        move_steps: list[list[str]],
        config: ExecutionConfig,
        algorithm_name: str | None = None,
        formula_text: str | None = None,
        inverse_steps: list[list[str]] | None = None,
        oll_top_view_data: OLLTopViewData | None = None,
        pll_top_view_data: PLLTopViewData | None = None,
        cube_face_colors: Sequence[str] | None = None,
    ) -> None:
        if config.prepare_case_from_inverse and inverse_steps:
            inverse_flat = [move for step in inverse_steps for move in step]
            cube.set_state(state_string_from_moves(inverse_flat))

        MoveExecutor._add_algorithm_name(scene, algorithm_name, config)
        MoveExecutor._add_formula_overlay(scene, formula_text, config)
        MoveExecutor._add_oll_top_view_overlay(scene, oll_top_view_data, config)
        MoveExecutor._add_pll_top_view_overlay(
            scene,
            pll_top_view_data,
            config,
            cube_face_colors,
        )
        scene.add(cube)
        scene.wait(config.pre_start_wait)

        for index, step in enumerate(move_steps):
            step_run_time = MoveExecutor._step_run_time(step, config)
            if len(step) == 1:
                scene.play(
                    CubeMoveExtended(cube, step[0]),
                    run_time=step_run_time,
                    rate_func=MoveExecutor.DEFAULT_MOVE_RATE_FUNC,
                )
            else:
                scene.play(
                    CubeMoveConcurrent(cube, step),
                    run_time=step_run_time,
                    rate_func=MoveExecutor.DEFAULT_MOVE_RATE_FUNC,
                )

            if index < len(move_steps) - 1:
                scene.wait(MoveExecutor._inter_move_pause(config))

        scene.wait(config.end_wait)
