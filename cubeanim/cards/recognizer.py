from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from cubeanim.formula import FormulaConverter
from cubeanim.palette import CONTRAST_SAFE_CUBE_COLORS, FACE_ORDER
from cubeanim.pll import PLLTopViewData, build_pll_top_view_data, validate_pll_start_state
from cubeanim.state import state_string_from_moves


@dataclass(frozen=True)
class RecognizerPaths:
    svg_rel_path: str
    png_rel_path: str | None


def _slug(category: str, case_code: str) -> str:
    return f"{category.lower()}_{case_code.lower().replace(' ', '_')}"


def _norm_formula(formula: str) -> str:
    return " ".join(formula.split())


def _pattern_bits(category: str, case_code: str) -> list[int]:
    payload = f"{category}:{case_code}".encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    bits: list[int] = []
    for byte in digest:
        for shift in range(8):
            bits.append((byte >> shift) & 1)
    return bits


def _formula_hash(formula: str) -> str:
    normalized = _norm_formula(formula)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _face_color_map() -> dict[str, str]:
    return dict(zip(FACE_ORDER, CONTRAST_SAFE_CUBE_COLORS, strict=True))


def _pll_data_from_formula(formula: str) -> PLLTopViewData:
    move_steps = FormulaConverter.convert_steps(formula, repeat=1)
    inverse_steps = FormulaConverter.invert_steps(move_steps)
    inverse_flat = [move for step in inverse_steps for move in step]
    start_state = state_string_from_moves(inverse_flat)
    validate_pll_start_state(start_state)
    return build_pll_top_view_data(start_state)


def _grid_point(row: int, col: int, x0: float, y0: float, cell: float) -> tuple[float, float]:
    return (x0 + (col + 0.5) * cell, y0 + (row + 0.5) * cell)


def _arrow_svg(
    start: tuple[int, int],
    end: tuple[int, int],
    bidirectional: bool,
    x0: float,
    y0: float,
    cell: float,
) -> str:
    x1, y1 = _grid_point(start[0], start[1], x0, y0, cell)
    x2, y2 = _grid_point(end[0], end[1], x0, y0, cell)
    if abs(x1 - x2) < 0.1 and abs(y1 - y2) < 0.1:
        return ""

    marker_start = ' marker-start="url(#arrowhead)"' if bidirectional else ""
    marker_end = ' marker-end="url(#arrowhead)"'
    return (
        f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
        f'stroke="#11151B" stroke-width="2.6" stroke-linecap="round"{marker_start}{marker_end} />'
    )


def _build_pll_svg(case_code: str, formula: str) -> str:
    data = _pll_data_from_formula(formula)
    colors = _face_color_map()
    formula_sig = _formula_hash(formula)

    width = 220
    height = 150
    panel_x = 12
    panel_y = 12
    panel_w = 196
    panel_h = 126
    x0 = 70
    y0 = 40
    cell = 20
    grid_size = cell * 3
    strip_long = 12
    strip_short = 6
    strip_gap = 5

    col_centers = [x0 + (idx + 0.5) * cell for idx in range(3)]
    row_centers = [y0 + (idx + 0.5) * cell for idx in range(3)]

    lines: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">',
        f"<!-- recognizer:v3 category=PLL case={case_code} formula={formula_sig} -->",
        "<defs>",
        '<marker id="arrowhead" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">',
        '<polygon points="0 0, 8 3, 0 6" fill="#11151B" />',
        "</marker>",
        "</defs>",
        '<rect x="0" y="0" width="100%" height="100%" fill="#EFF1F5"/>',
        (
            f'<rect x="{panel_x}" y="{panel_y}" width="{panel_w}" height="{panel_h}" rx="10" '
            'fill="#FFFFFF" stroke="#B8C0CC" stroke-width="2"/>'
        ),
    ]

    for row, values in enumerate(data.u_grid):
        for col, face in enumerate(values):
            lines.append(
                (
                    f'<rect x="{x0 + col * cell:.2f}" y="{y0 + row * cell:.2f}" width="{cell:.2f}" '
                    f'height="{cell:.2f}" fill="{colors.get(face, "#8E939B")}" '
                    'stroke="#11151B" stroke-width="1.6"/>'
                )
            )

    lines.append(
        (
            f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{grid_size:.2f}" height="{grid_size:.2f}" '
            'fill="none" stroke="#11151B" stroke-width="2.2"/>'
        )
    )

    def add_horizontal(values: tuple[str, str, str], y_center: float) -> None:
        for idx, face in enumerate(values):
            lines.append(
                (
                    f'<rect x="{col_centers[idx] - strip_long / 2:.2f}" y="{y_center - strip_short / 2:.2f}" '
                    f'width="{strip_long:.2f}" height="{strip_short:.2f}" fill="{colors.get(face, "#8E939B")}" '
                    'stroke="#11151B" stroke-width="1.1"/>'
                )
            )

    def add_vertical(values: tuple[str, str, str], x_center: float) -> None:
        for idx, face in enumerate(values):
            lines.append(
                (
                    f'<rect x="{x_center - strip_short / 2:.2f}" y="{row_centers[idx] - strip_long / 2:.2f}" '
                    f'width="{strip_short:.2f}" height="{strip_long:.2f}" fill="{colors.get(face, "#8E939B")}" '
                    'stroke="#11151B" stroke-width="1.1"/>'
                )
            )

    add_horizontal(data.top_b, y0 - strip_gap - strip_short / 2)
    add_horizontal(data.bottom_f, y0 + grid_size + strip_gap + strip_short / 2)
    add_vertical(data.left_l, x0 - strip_gap - strip_short / 2)
    add_vertical(data.right_r, x0 + grid_size + strip_gap + strip_short / 2)

    for arrow in (*data.corner_arrows, *data.edge_arrows):
        svg_line = _arrow_svg(
            start=arrow.start,
            end=arrow.end,
            bidirectional=arrow.bidirectional,
            x0=x0,
            y0=y0,
            cell=cell,
        )
        if svg_line:
            lines.append(svg_line)

    lines.extend(
        [
            f'<text x="146" y="52" font-family="Avenir Next, Arial" font-size="16" font-weight="700" fill="#1D2430">PLL</text>',
            f'<text x="146" y="74" font-family="Avenir Next, Arial" font-size="14" fill="#1D2430">{case_code}</text>',
            f'<text x="146" y="95" font-family="Avenir Next, Arial" font-size="11" fill="#71717A">{formula_sig}</text>',
        ]
    )

    lines.append("</svg>")
    return "\n".join(lines)


def _build_fallback_svg(category: str, case_code: str) -> str:
    bits = _pattern_bits(category, case_code)
    width = 220
    height = 150
    cell = 20
    x0 = 25
    y0 = 25

    lines: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">',
        f"<!-- recognizer:v2 category={category} case={case_code} -->",
        '<rect x="0" y="0" width="100%" height="100%" fill="#EFF1F5"/>',
        '<rect x="12" y="12" width="196" height="126" rx="10" fill="#FFFFFF" stroke="#B8C0CC" stroke-width="2"/>',
    ]

    bit_index = 0
    for row in range(3):
        for col in range(3):
            fill = "#FDFF00" if bits[bit_index] == 1 else "#8E939B"
            lines.append(
                (
                    f'<rect x="{x0 + col * cell}" y="{y0 + row * cell}" width="{cell}" height="{cell}" '
                    f'fill="{fill}" stroke="#1D2430" stroke-width="1.2"/>'
                )
            )
            bit_index += 1

    marker = "#2DBE4A" if category == "PLL" else "#FF7A00"
    lines.extend(
        [
            f'<text x="105" y="58" font-family="Avenir Next, Arial" font-size="17" font-weight="700" fill="#1D2430">{category}</text>',
            f'<text x="105" y="82" font-family="Avenir Next, Arial" font-size="15" fill="#1D2430">{case_code}</text>',
            f'<circle cx="188" cy="36" r="8" fill="{marker}"/>',
        ]
    )
    lines.append("</svg>")
    return "\n".join(lines)


def _build_svg(category: str, case_code: str, formula: str | None = None) -> str:
    if category == "PLL" and formula:
        try:
            return _build_pll_svg(case_code=case_code, formula=formula)
        except Exception:
            pass
    return _build_fallback_svg(category, case_code)


def _render_png_from_svg(svg_content: str, output_path: Path) -> bool:
    # Keep SVG as the primary recognizer format.
    # PNG is optional and may not be available in minimal environments.
    _ = svg_content
    _ = output_path
    return False


def ensure_recognizer_assets(
    runtime_dir: Path,
    category: str,
    case_code: str,
    formula: str | None = None,
) -> RecognizerPaths:
    svg_dir = runtime_dir / "recognizers" / "svg"
    png_dir = runtime_dir / "recognizers" / "png"
    svg_dir.mkdir(parents=True, exist_ok=True)
    png_dir.mkdir(parents=True, exist_ok=True)

    slug = _slug(category, case_code)
    svg_name = f"{slug}.svg"
    png_name = f"{slug}.png"

    svg_path = svg_dir / svg_name
    svg_content = _build_svg(category=category, case_code=case_code, formula=formula)
    if not svg_path.exists() or svg_path.read_text(encoding="utf-8") != svg_content:
        svg_path.write_text(svg_content, encoding="utf-8")

    png_path = png_dir / png_name
    png_rel: str | None = None
    if png_path.exists() or _render_png_from_svg(svg_content, png_path):
        png_rel = f"recognizers/png/{png_name}"

    return RecognizerPaths(
        svg_rel_path=f"recognizers/svg/{svg_name}",
        png_rel_path=png_rel,
    )
