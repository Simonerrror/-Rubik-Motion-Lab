from __future__ import annotations

import csv
import hashlib
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path

from cubeanim.formula import FormulaConverter
from cubeanim.oll import OLLTopViewData, build_oll_top_view_data, validate_oll_f2l_start_state
from cubeanim.palette import CONTRAST_SAFE_CUBE_COLORS, FACE_ORDER
from cubeanim.pll import (
    PLLTopViewData,
    balance_pll_formula_rotations,
    build_pll_top_view_data,
    resolve_valid_pll_start_state,
)
from cubeanim.state import state_string_from_moves


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


def _formula_hash(formula: str) -> str:
    normalized = _norm_formula(formula)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:10]


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
    start_state = state_string_from_moves(inverse_flat)
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


@lru_cache(maxsize=4)
def _pll_presets_by_case(repo_root: str) -> dict[str, str]:
    path = Path(repo_root) / "pll.txt"
    if not path.exists():
        return {}
    rows = list(csv.reader(path.read_text(encoding="utf-8-sig").splitlines()))
    if not rows:
        return {}
    presets: dict[str, str] = {}
    for row in rows[1:]:
        if len(row) < 3:
            continue
        raw_index = str(row[0]).strip()
        if not raw_index.isdigit():
            continue
        formula = _norm_formula(str(row[2]))
        if not formula:
            continue
        presets[f"PLL_{int(raw_index)}"] = formula
    return presets


def _resolve_formula_for_recognizer(
    runtime_dir: Path,
    category: str,
    case_code: str,
    formula: str | None,
) -> str:
    normalized = _norm_formula(formula or "")
    if category != "PLL":
        return normalized

    # PLL top cards are canonical per case: never depend on currently selected/custom formula.
    repo_root = str(runtime_dir.resolve().parents[2])
    preset = _pll_presets_by_case(repo_root).get(case_code)
    resolved = _norm_formula(preset or normalized)
    return balance_pll_formula_rotations(resolved)


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
    # OLL keeps formula-hash behavior; PLL stays stable by case_code.
    if category == "OLL" and normalized_formula:
        slug = f"{slug}_{_formula_hash(normalized_formula)}"
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
