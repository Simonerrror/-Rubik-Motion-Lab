from __future__ import annotations

import hashlib
import sqlite3
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path

from cubeanim.formula import FormulaConverter
from cubeanim.oll import (
    OLLTopViewData,
    build_oll_top_view_data,
    resolve_valid_oll_start_state,
    validate_oll_f2l_start_state,
)
from cubeanim.palette import CONTRAST_SAFE_CUBE_COLORS, FACE_ORDER
from cubeanim.pll import (
    PLLTopViewData,
    balance_pll_formula_rotations,
    build_pll_top_view_data,
    resolve_valid_pll_start_state,
)
from cubeanim.state import state_slots_metadata, state_string_from_moves


@dataclass(frozen=True)
class RecognizerPaths:
    svg_rel_path: str
    png_rel_path: str | None


_CANVAS_SIZE = 128
_BG_COLOR = "#D8DADF"
_GRID_STROKE = "#11151B"
_GRID_CELL_YELLOW = "#FDFF00"
_GRID_CELL_GRAY = "#8E939B"
_ARROW_COLOR = "#11151B"
_ARROW_STROKE_WIDTH = 1.7
_ARROW_INSET = 5.4
_ARROW_HEAD_LENGTH = 7.4
_ARROW_HEAD_WIDTH = 4.8

_GRID_CELL = 24
_GRID_SIZE = _GRID_CELL * 3
_GRID_X = (_CANVAS_SIZE - _GRID_SIZE) // 2
_GRID_Y = (_CANVAS_SIZE - _GRID_SIZE) // 2

_SIDE_LONG = 18
_SIDE_SHORT = 4
_SIDE_GAP = 6

_COL_CENTERS = [_GRID_X + (index + 0.5) * _GRID_CELL for index in range(3)]
_ROW_CENTERS = [_GRID_Y + (index + 0.5) * _GRID_CELL for index in range(3)]


def _slug(category: str, case_code: str) -> str:
    return f"{category.lower()}_{case_code.lower().replace(' ', '_')}"


def _norm_formula(formula: str) -> str:
    return " ".join(formula.split())


def _face_color_map() -> dict[str, str]:
    return dict(zip(FACE_ORDER, CONTRAST_SAFE_CUBE_COLORS, strict=True))


def _pattern_bits(category: str, case_code: str) -> list[int]:
    payload = f"{category}:{case_code}".encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    bits: list[int] = []
    for byte in digest:
        for shift in range(8):
            bits.append((byte >> shift) & 1)
    return bits


def _pll_data_from_formula(formula: str) -> PLLTopViewData:
    move_steps = FormulaConverter.convert_steps(formula, repeat=1)
    inverse_steps = FormulaConverter.invert_steps(move_steps)
    inverse_flat = [move for step in inverse_steps for move in step]
    start_state = resolve_valid_pll_start_state(inverse_flat)
    return build_pll_top_view_data(start_state)


def _oll_data_from_formula(formula: str) -> OLLTopViewData:
    move_steps = FormulaConverter.convert_steps(formula, repeat=1)
    inverse_steps = FormulaConverter.invert_steps(move_steps)
    inverse_flat = [move for step in inverse_steps for move in step]
    start_state = resolve_valid_oll_start_state(inverse_flat)
    validate_oll_f2l_start_state(start_state)
    return build_oll_top_view_data(start_state)


def _grid_point(row: int, col: int) -> tuple[float, float]:
    return (_GRID_X + (col + 0.5) * _GRID_CELL, _GRID_Y + (row + 0.5) * _GRID_CELL)


def _arrow_svg(start: tuple[int, int], end: tuple[int, int], bidirectional: bool) -> str:
    x1, y1 = _grid_point(*start)
    x2, y2 = _grid_point(*end)
    dx = x2 - x1
    dy = y2 - y1
    length = (dx * dx + dy * dy) ** 0.5
    if length < 0.1:
        return ""

    ux = dx / length
    uy = dy / length
    px = -uy
    py = ux

    line_inset = min(_ARROW_INSET, max((length - 8.0) / 2.0, 0.0))
    sx = x1 + ux * line_inset
    sy = y1 + uy * line_inset
    ex = x2 - ux * line_inset
    ey = y2 - uy * line_inset

    line_length = max(((ex - sx) ** 2 + (ey - sy) ** 2) ** 0.5, 0.0)
    if line_length < 8.0:
        return ""
    head_len = min(_ARROW_HEAD_LENGTH, line_length * 0.46)
    head_w = min(_ARROW_HEAD_WIDTH, head_len * 0.9)

    def arrow_head(tip_x: float, tip_y: float, dir_x: float, dir_y: float) -> str:
        base_x = tip_x - dir_x * head_len
        base_y = tip_y - dir_y * head_len
        left_x = base_x + px * (head_w * 0.5)
        left_y = base_y + py * (head_w * 0.5)
        right_x = base_x - px * (head_w * 0.5)
        right_y = base_y - py * (head_w * 0.5)
        return (
            f'<polygon points="{tip_x:.2f},{tip_y:.2f} {left_x:.2f},{left_y:.2f} {right_x:.2f},{right_y:.2f}" '
            f'fill="{_ARROW_COLOR}" />'
        )

    # Prevent tiny anti-alias protrusion of the line past the arrowhead tip.
    tip_trim = max(head_len * 0.22, _ARROW_STROKE_WIDTH * 0.55)
    line_sx = sx + (ux * tip_trim if bidirectional else 0.0)
    line_sy = sy + (uy * tip_trim if bidirectional else 0.0)
    line_ex = ex - ux * tip_trim
    line_ey = ey - uy * tip_trim

    trimmed_len = ((line_ex - line_sx) ** 2 + (line_ey - line_sy) ** 2) ** 0.5
    if trimmed_len < 4.0:
        return ""

    parts = [
        (
            f'<line x1="{line_sx:.2f}" y1="{line_sy:.2f}" x2="{line_ex:.2f}" y2="{line_ey:.2f}" '
            f'stroke="{_ARROW_COLOR}" stroke-width="{_ARROW_STROKE_WIDTH:.1f}" stroke-linecap="butt" />'
        ),
        arrow_head(ex, ey, ux, uy),
    ]

    if bidirectional:
        parts.append(arrow_head(sx, sy, -ux, -uy))

    return "".join(parts)


def _canonical_presets_by_case(runtime_dir: Path, category: str) -> dict[str, str]:
    db_path = runtime_dir / "cards.db"
    if not db_path.exists():
        return {}
    try:
        mtime_ns = db_path.stat().st_mtime_ns
    except OSError:
        return {}
    return _canonical_presets_by_case_cached(str(db_path), mtime_ns, category)


@lru_cache(maxsize=16)
def _canonical_presets_by_case_cached(db_path: str, _mtime_ns: int, category: str) -> dict[str, str]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
                cc.case_code,
                ca.formula
            FROM canonical_cases cc
            LEFT JOIN canonical_algorithms ca ON ca.id = (
                SELECT cca.id
                FROM canonical_algorithms cca
                WHERE cca.canonical_case_id = cc.id
                ORDER BY cca.is_primary DESC, cca.sort_order ASC, cca.id ASC
                LIMIT 1
            )
            WHERE cc.category_code = ?
            """,
            (category,),
        ).fetchall()
    finally:
        conn.close()

    presets: dict[str, str] = {}
    for row in rows:
        case_code = str(row["case_code"] or "").strip()
        if not case_code:
            continue
        formula = _norm_formula(str(row["formula"] or ""))
        if not formula:
            continue
        if category == "PLL":
            formula = balance_pll_formula_rotations(formula)
        presets[case_code] = formula
    return presets


def _resolve_formula_for_recognizer(
    runtime_dir: Path,
    category: str,
    case_code: str,
    formula: str | None,
) -> str:
    normalized = _norm_formula(formula or "")
    if category == "F2L":
        # F2L cards should be stable per case: do not depend on selected/custom formula.
        preset = _canonical_presets_by_case(runtime_dir, category).get(case_code)
        return _norm_formula(preset or normalized)
    if category == "PLL":
        # PLL top cards are canonical per case: never depend on currently selected/custom formula.
        preset = _canonical_presets_by_case(runtime_dir, category).get(case_code)
        resolved = _norm_formula(preset or normalized)
        return balance_pll_formula_rotations(resolved)
    if category == "OLL":
        # OLL top cards are canonical per case as well.
        preset = _canonical_presets_by_case(runtime_dir, category).get(case_code)
        return _norm_formula(preset or normalized)
    return normalized


def _base_svg_lines(version: str, category: str, case_code: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_CANVAS_SIZE} {_CANVAS_SIZE}">',
        f'<!-- recognizer:{version} category={category} case={case_code} -->',
        f'<rect x="0" y="0" width="{_CANVAS_SIZE}" height="{_CANVAS_SIZE}" fill="{_BG_COLOR}"/>',
    ]


def _draw_grid(lines: list[str], u_grid_colors: list[list[str]]) -> None:
    for row in range(3):
        for col in range(3):
            color = u_grid_colors[row][col]
            lines.append(
                (
                    f'<rect x="{_GRID_X + col * _GRID_CELL}" y="{_GRID_Y + row * _GRID_CELL}" '
                    f'width="{_GRID_CELL}" height="{_GRID_CELL}" fill="{color}" '
                    f'stroke="{_GRID_STROKE}" stroke-width="1.4"/>'
                )
            )

    lines.append(
        (
            f'<rect x="{_GRID_X}" y="{_GRID_Y}" width="{_GRID_SIZE}" height="{_GRID_SIZE}" '
            f'fill="none" stroke="{_GRID_STROKE}" stroke-width="1.9"/>'
        )
    )


def _draw_oll_side_markers(
    lines: list[str],
    top_b: tuple[bool, bool, bool],
    right_r: tuple[bool, bool, bool],
    bottom_f: tuple[bool, bool, bool],
    left_l: tuple[bool, bool, bool],
) -> None:
    for index, value in enumerate(top_b):
        if not value:
            continue
        lines.append(
            (
                f'<rect x="{_COL_CENTERS[index] - _SIDE_LONG / 2:.2f}" '
                f'y="{_GRID_Y - _SIDE_GAP - _SIDE_SHORT:.2f}" '
                f'width="{_SIDE_LONG:.2f}" height="{_SIDE_SHORT:.2f}" '
                f'fill="{_GRID_CELL_YELLOW}" stroke="{_GRID_STROKE}" stroke-width="1.0"/>'
            )
        )

    for index, value in enumerate(bottom_f):
        if not value:
            continue
        lines.append(
            (
                f'<rect x="{_COL_CENTERS[index] - _SIDE_LONG / 2:.2f}" '
                f'y="{_GRID_Y + _GRID_SIZE + _SIDE_GAP:.2f}" '
                f'width="{_SIDE_LONG:.2f}" height="{_SIDE_SHORT:.2f}" '
                f'fill="{_GRID_CELL_YELLOW}" stroke="{_GRID_STROKE}" stroke-width="1.0"/>'
            )
        )

    for index, value in enumerate(left_l):
        if not value:
            continue
        lines.append(
            (
                f'<rect x="{_GRID_X - _SIDE_GAP - _SIDE_SHORT:.2f}" '
                f'y="{_ROW_CENTERS[index] - _SIDE_LONG / 2:.2f}" '
                f'width="{_SIDE_SHORT:.2f}" height="{_SIDE_LONG:.2f}" '
                f'fill="{_GRID_CELL_YELLOW}" stroke="{_GRID_STROKE}" stroke-width="1.0"/>'
            )
        )

    for index, value in enumerate(right_r):
        if not value:
            continue
        lines.append(
            (
                f'<rect x="{_GRID_X + _GRID_SIZE + _SIDE_GAP:.2f}" '
                f'y="{_ROW_CENTERS[index] - _SIDE_LONG / 2:.2f}" '
                f'width="{_SIDE_SHORT:.2f}" height="{_SIDE_LONG:.2f}" '
                f'fill="{_GRID_CELL_YELLOW}" stroke="{_GRID_STROKE}" stroke-width="1.0"/>'
            )
        )


def _draw_pll_side_strips(
    lines: list[str],
    colors: dict[str, str],
    top_b: tuple[str, str, str],
    right_r: tuple[str, str, str],
    bottom_f: tuple[str, str, str],
    left_l: tuple[str, str, str],
) -> None:
    for index, face in enumerate(top_b):
        lines.append(
            (
                f'<rect x="{_COL_CENTERS[index] - _SIDE_LONG / 2:.2f}" '
                f'y="{_GRID_Y - _SIDE_GAP - _SIDE_SHORT:.2f}" '
                f'width="{_SIDE_LONG:.2f}" height="{_SIDE_SHORT:.2f}" '
                f'fill="{colors.get(face, _GRID_CELL_GRAY)}" stroke="{_GRID_STROKE}" stroke-width="1.0"/>'
            )
        )

    for index, face in enumerate(bottom_f):
        lines.append(
            (
                f'<rect x="{_COL_CENTERS[index] - _SIDE_LONG / 2:.2f}" '
                f'y="{_GRID_Y + _GRID_SIZE + _SIDE_GAP:.2f}" '
                f'width="{_SIDE_LONG:.2f}" height="{_SIDE_SHORT:.2f}" '
                f'fill="{colors.get(face, _GRID_CELL_GRAY)}" stroke="{_GRID_STROKE}" stroke-width="1.0"/>'
            )
        )

    for index, face in enumerate(left_l):
        lines.append(
            (
                f'<rect x="{_GRID_X - _SIDE_GAP - _SIDE_SHORT:.2f}" '
                f'y="{_ROW_CENTERS[index] - _SIDE_LONG / 2:.2f}" '
                f'width="{_SIDE_SHORT:.2f}" height="{_SIDE_LONG:.2f}" '
                f'fill="{colors.get(face, _GRID_CELL_GRAY)}" stroke="{_GRID_STROKE}" stroke-width="1.0"/>'
            )
        )

    for index, face in enumerate(right_r):
        lines.append(
            (
                f'<rect x="{_GRID_X + _GRID_SIZE + _SIDE_GAP:.2f}" '
                f'y="{_ROW_CENTERS[index] - _SIDE_LONG / 2:.2f}" '
                f'width="{_SIDE_SHORT:.2f}" height="{_SIDE_LONG:.2f}" '
                f'fill="{colors.get(face, _GRID_CELL_GRAY)}" stroke="{_GRID_STROKE}" stroke-width="1.0"/>'
            )
        )


def _build_pll_svg(case_code: str, formula: str) -> str:
    data = _pll_data_from_formula(formula)
    colors = _face_color_map()

    lines = _base_svg_lines(version="v4", category="PLL", case_code=case_code)

    u_grid_colors = [[colors.get(face, _GRID_CELL_GRAY) for face in row] for row in data.u_grid]
    _draw_grid(lines, u_grid_colors)
    _draw_pll_side_strips(lines, colors, data.top_b, data.right_r, data.bottom_f, data.left_l)

    for arrow in (*data.corner_arrows, *data.edge_arrows):
        svg_arrow = _arrow_svg(start=arrow.start, end=arrow.end, bidirectional=arrow.bidirectional)
        if svg_arrow:
            lines.append(svg_arrow)

    lines.append("</svg>")
    return "\n".join(lines)


def _build_oll_svg(case_code: str, formula: str) -> str:
    data = _oll_data_from_formula(formula)
    lines = _base_svg_lines(version="v4", category="OLL", case_code=case_code)

    u_grid_colors = [
        [_GRID_CELL_YELLOW if value else _GRID_CELL_GRAY for value in row]
        for row in data.u_grid
    ]
    _draw_grid(lines, u_grid_colors)
    _draw_oll_side_markers(lines, data.top_b, data.right_r, data.bottom_f, data.left_l)

    lines.append("</svg>")
    return "\n".join(lines)


def _state_color_by_face_and_pos(state: str) -> dict[tuple[str, tuple[int, int, int]], str]:
    if len(state) != 54:
        raise ValueError(f"State must contain exactly 54 facelets, got {len(state)}")
    lookup: dict[tuple[str, tuple[int, int, int]], str] = {}
    for (position, face), color in zip(state_slots_metadata(), state, strict=True):
        x, y, z = position
        lookup[(face, (int(x), int(y), int(z)))] = str(color)
    return lookup


def _build_f2l_svg(case_code: str, formula: str) -> str:
    move_steps = FormulaConverter.convert_steps(formula, repeat=1)
    inverse_steps = FormulaConverter.invert_steps(move_steps)
    inverse_flat = [move for step in inverse_steps for move in step]
    start_state = state_string_from_moves(inverse_flat)
    color_by_face_and_pos = _state_color_by_face_and_pos(start_state)
    masked_positions: set[tuple[int, int, int]] = set()
    for (position, _face), color_code in zip(state_slots_metadata(), start_state, strict=True):
        if color_code != "U":
            continue
        masked_positions.add((int(position[0]), int(position[1]), int(position[2])))

    colors = _face_color_map()
    stickerless_u = "#0B1220"
    stroke = _GRID_STROKE
    stroke_w = 1.25

    center_x = _CANVAS_SIZE / 2.0
    center_y = _CANVAS_SIZE / 2.0
    proj_ax = 20.0
    proj_ay = 11.0
    proj_az = 22.0

    def face_color(face: str, pos: tuple[int, int, int]) -> str:
        if pos in masked_positions:
            return stickerless_u
        code = color_by_face_and_pos[(face, pos)]
        return colors.get(code, _GRID_CELL_GRAY)

    def project(x: float, y: float, z: float) -> tuple[float, float]:
        return (
            center_x + (x - y) * proj_ax,
            center_y + (x + y) * proj_ay - z * proj_az,
        )

    def polygon(points: list[tuple[float, float]], fill: str, stroke_color: str = stroke) -> str:
        points_attr = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
        return (
            f'<polygon points="{points_attr}" fill="{fill}" '
            f'stroke="{stroke_color}" stroke-width="{stroke_w:.2f}" stroke-linejoin="round"/>'
        )

    def draw_u_face() -> None:
        for row in range(3):  # B -> F
            x_hi = 1.0 - (2.0 * row) / 3.0
            x_lo = 1.0 - (2.0 * (row + 1)) / 3.0
            x_idx = 1 - row
            for col in range(3):  # L -> R
                y_hi = 1.0 - (2.0 * col) / 3.0
                y_lo = 1.0 - (2.0 * (col + 1)) / 3.0
                y_idx = 1 - col
                points = [
                    project(x_hi, y_hi, 1.0),
                    project(x_hi, y_lo, 1.0),
                    project(x_lo, y_lo, 1.0),
                    project(x_lo, y_hi, 1.0),
                ]
                lines.append(polygon(points, face_color("U", (x_idx, y_idx, 1))))

    def draw_f_face() -> None:
        for row in range(3):  # z=+1 -> -1
            z_hi = 1.0 - (2.0 * row) / 3.0
            z_lo = 1.0 - (2.0 * (row + 1)) / 3.0
            z_idx = 1 - row
            for col in range(3):  # y=+1 -> -1
                y_hi = 1.0 - (2.0 * col) / 3.0
                y_lo = 1.0 - (2.0 * (col + 1)) / 3.0
                y_idx = 1 - col
                points = [
                    project(-1.0, y_hi, z_hi),
                    project(-1.0, y_lo, z_hi),
                    project(-1.0, y_lo, z_lo),
                    project(-1.0, y_hi, z_lo),
                ]
                lines.append(polygon(points, face_color("F", (-1, y_idx, z_idx))))

    def draw_r_face() -> None:
        for row in range(3):  # z=+1 -> -1
            z_hi = 1.0 - (2.0 * row) / 3.0
            z_lo = 1.0 - (2.0 * (row + 1)) / 3.0
            z_idx = 1 - row
            for col in range(3):  # x=-1 -> +1
                x_lo = -1.0 + (2.0 * col) / 3.0
                x_hi = -1.0 + (2.0 * (col + 1)) / 3.0
                x_idx = -1 + col
                points = [
                    project(x_lo, -1.0, z_hi),
                    project(x_hi, -1.0, z_hi),
                    project(x_hi, -1.0, z_lo),
                    project(x_lo, -1.0, z_lo),
                ]
                lines.append(polygon(points, face_color("R", (x_idx, -1, z_idx))))

    lines = _base_svg_lines(version="v8-f2l", category="F2L", case_code=case_code)
    body_fill = stickerless_u
    lines.append(
        polygon(
            [
                project(1.0, 1.0, 1.0),
                project(1.0, -1.0, 1.0),
                project(-1.0, -1.0, 1.0),
                project(-1.0, 1.0, 1.0),
            ],
            body_fill,
        )
    )
    lines.append(
        polygon(
            [
                project(-1.0, 1.0, 1.0),
                project(-1.0, -1.0, 1.0),
                project(-1.0, -1.0, -1.0),
                project(-1.0, 1.0, -1.0),
            ],
            body_fill,
        )
    )
    lines.append(
        polygon(
            [
                project(-1.0, -1.0, 1.0),
                project(1.0, -1.0, 1.0),
                project(1.0, -1.0, -1.0),
                project(-1.0, -1.0, -1.0),
            ],
            body_fill,
        )
    )
    draw_f_face()
    draw_r_face()
    draw_u_face()
    lines.append("</svg>")
    return "\n".join(lines)


def _build_fallback_svg(category: str, case_code: str) -> str:
    bits = _pattern_bits(category, case_code)
    lines = _base_svg_lines(version="v4-fallback", category=category, case_code=case_code)

    u_grid_colors = []
    pointer = 0
    for _ in range(3):
        row: list[str] = []
        for _ in range(3):
            row.append(_GRID_CELL_YELLOW if bits[pointer] else _GRID_CELL_GRAY)
            pointer += 1
        u_grid_colors.append(row)

    _draw_grid(lines, u_grid_colors)

    def next_triplet() -> tuple[bool, bool, bool]:
        nonlocal pointer
        values = (bool(bits[pointer]), bool(bits[pointer + 1]), bool(bits[pointer + 2]))
        pointer += 3
        return values

    top_b = next_triplet()
    right_r = next_triplet()
    bottom_f = next_triplet()
    left_l = next_triplet()

    if category == "PLL":
        colors = _face_color_map()

        def bool_to_face(values: tuple[bool, bool, bool], fallback_face: str) -> tuple[str, str, str]:
            pool = ("B", "R", "F") if fallback_face in {"B", "F"} else ("L", "R", "B")
            return tuple(pool[index] if flag else fallback_face for index, flag in enumerate(values))

        _draw_pll_side_strips(
            lines,
            colors,
            bool_to_face(top_b, "B"),
            bool_to_face(right_r, "R"),
            bool_to_face(bottom_f, "F"),
            bool_to_face(left_l, "L"),
        )
    else:
        _draw_oll_side_markers(lines, top_b, right_r, bottom_f, left_l)

    lines.append("</svg>")
    return "\n".join(lines)


def _build_svg(category: str, case_code: str, formula: str | None = None) -> str:
    normalized_formula = _norm_formula(formula or "")
    if category == "F2L" and normalized_formula:
        try:
            return _build_f2l_svg(case_code=case_code, formula=normalized_formula)
        except Exception:
            pass
    if category == "PLL" and normalized_formula:
        try:
            return _build_pll_svg(case_code=case_code, formula=normalized_formula)
        except Exception:
            pass

    if category == "OLL" and normalized_formula:
        try:
            return _build_oll_svg(case_code=case_code, formula=normalized_formula)
        except Exception:
            pass

    return _build_fallback_svg(category, case_code)


def _render_png_from_svg(svg_content: str, output_path: Path) -> bool:
    _ = svg_content
    _ = output_path
    return False


def ensure_recognizer_assets(
    runtime_dir: Path,
    category: str,
    case_code: str,
    formula: str | None = None,
) -> RecognizerPaths:
    category_dir = category.strip().lower() or "misc"
    svg_dir = runtime_dir / "recognizers" / category_dir / "svg"
    png_dir = runtime_dir / "recognizers" / category_dir / "png"
    svg_dir.mkdir(parents=True, exist_ok=True)
    png_dir.mkdir(parents=True, exist_ok=True)

    normalized_formula = _resolve_formula_for_recognizer(
        runtime_dir=runtime_dir,
        category=category,
        case_code=case_code,
        formula=formula,
    )
    slug = _slug(category, case_code)
    svg_name = f"{slug}.svg"
    png_name = f"{slug}.png"

    svg_path = svg_dir / svg_name
    svg_content = _build_svg(category=category, case_code=case_code, formula=normalized_formula)
    if not svg_path.exists() or svg_path.read_text(encoding="utf-8") != svg_content:
        svg_path.write_text(svg_content, encoding="utf-8")

    png_path = png_dir / png_name
    png_rel: str | None = None
    if png_path.exists() or _render_png_from_svg(svg_content, png_path):
        png_rel = f"recognizers/{category_dir}/png/{png_name}"

    return RecognizerPaths(
        svg_rel_path=f"recognizers/{category_dir}/svg/{svg_name}",
        png_rel_path=png_rel,
    )
