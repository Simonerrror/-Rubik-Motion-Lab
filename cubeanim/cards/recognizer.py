from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RecognizerPaths:
    svg_rel_path: str
    png_rel_path: str | None


def _slug(category: str, case_code: str) -> str:
    return f"{category.lower()}_{case_code.lower().replace(' ', '_')}"


def _pattern_bits(category: str, case_code: str) -> list[int]:
    payload = f"{category}:{case_code}".encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    bits: list[int] = []
    for byte in digest:
        for shift in range(8):
            bits.append((byte >> shift) & 1)
    return bits


def _build_svg(category: str, case_code: str) -> str:
    bits = _pattern_bits(category, case_code)

    width = 220
    height = 150
    cell = 20
    x0 = 25
    y0 = 25

    lines: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">',
        '<rect x="0" y="0" width="100%" height="100%" fill="#EFF1F5"/>',
        '<rect x="12" y="12" width="196" height="126" rx="10" fill="#FFFFFF" stroke="#B8C0CC" stroke-width="2"/>',
    ]

    bit_index = 0
    for row in range(3):
        for col in range(3):
            fill = "#FDFF00" if bits[bit_index] == 1 else "#8E939B"
            lines.append(
                f'<rect x="{x0 + col * cell}" y="{y0 + row * cell}" width="{cell}" height="{cell}" fill="{fill}" stroke="#1D2430" stroke-width="1.2"/>'
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


def _render_png_from_svg(svg_content: str, output_path: Path) -> bool:
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return False

    # Lightweight fallback preview (not full SVG rasterization).
    image = Image.new("RGB", (220, 150), "#EFF1F5")
    draw = ImageDraw.Draw(image)
    draw.rectangle((12, 12, 208, 138), fill="#FFFFFF", outline="#B8C0CC", width=2)
    image.save(output_path)
    return True


def ensure_recognizer_assets(
    runtime_dir: Path,
    category: str,
    case_code: str,
) -> RecognizerPaths:
    svg_dir = runtime_dir / "recognizers" / "svg"
    png_dir = runtime_dir / "recognizers" / "png"
    svg_dir.mkdir(parents=True, exist_ok=True)
    png_dir.mkdir(parents=True, exist_ok=True)

    slug = _slug(category, case_code)
    svg_name = f"{slug}.svg"
    png_name = f"{slug}.png"

    svg_path = svg_dir / svg_name
    if not svg_path.exists():
        svg_path.write_text(_build_svg(category, case_code), encoding="utf-8")

    png_path = png_dir / png_name
    png_rel: str | None = None
    if png_path.exists() or _render_png_from_svg(svg_path.read_text(encoding="utf-8"), png_path):
        png_rel = f"recognizers/png/{png_name}"

    return RecognizerPaths(
        svg_rel_path=f"recognizers/svg/{svg_name}",
        png_rel_path=png_rel,
    )
