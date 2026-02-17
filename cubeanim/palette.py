from __future__ import annotations

from itertools import combinations
from typing import Sequence

FACE_ORDER = "URFDLB"

# High-contrast palette tuned for the current light-gray background and shadows.
CONTRAST_SAFE_CUBE_COLORS: tuple[str, ...] = (
    "#FDFF00",  # U - yellow
    "#C1121F",  # R - red (deeper crimson to separate from orange)
    "#2DBE4A",  # F - green
    "#F4F4F4",  # D - white
    "#FF7A00",  # L - orange (warmer, less red overlap)
    "#2B63E8",  # B - blue
)

_CRITICAL_PAIR_MIN_DISTANCE = {
    ("R", "L"): 95.0,  # red vs orange
    ("U", "L"): 90.0,  # yellow vs orange
}


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    color = hex_color.strip()
    if color.startswith("#"):
        color = color[1:]
    if len(color) != 6:
        raise ValueError(f"Invalid color '{hex_color}' (expected #RRGGBB)")
    return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16))


def _rgb_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    dr = a[0] - b[0]
    dg = a[1] - b[1]
    db = a[2] - b[2]
    return (dr * dr + dg * dg + db * db) ** 0.5


def validate_cube_palette(colors: Sequence[str]) -> None:
    if len(colors) != 6:
        raise ValueError("Cube palette must contain exactly 6 face colors (U,R,F,D,L,B)")

    colors_by_face = dict(zip(FACE_ORDER, colors, strict=True))
    rgb_by_face = {face: _hex_to_rgb(color) for face, color in colors_by_face.items()}

    for (face_a, face_b), min_distance in _CRITICAL_PAIR_MIN_DISTANCE.items():
        distance = _rgb_distance(rgb_by_face[face_a], rgb_by_face[face_b])
        if distance < min_distance:
            raise ValueError(
                "Cube palette contrast is too low for critical pair "
                f"{face_a}/{face_b}: distance={distance:.1f} < {min_distance:.1f}"
            )


def palette_diagnostics(colors: Sequence[str]) -> list[str]:
    if len(colors) != 6:
        return ["invalid length"]
    colors_by_face = dict(zip(FACE_ORDER, colors, strict=True))
    rgb_by_face = {face: _hex_to_rgb(color) for face, color in colors_by_face.items()}
    lines: list[str] = []
    for a, b in combinations(FACE_ORDER, 2):
        lines.append(f"{a}-{b}: {_rgb_distance(rgb_by_face[a], rgb_by_face[b]):.1f}")
    return lines
