from __future__ import annotations

import pytest

from cubeanim.palette import CONTRAST_SAFE_CUBE_COLORS, validate_cube_palette


def test_contrast_safe_palette_passes_validation() -> None:
    validate_cube_palette(CONTRAST_SAFE_CUBE_COLORS)


def test_validation_fails_when_red_and_orange_are_too_close() -> None:
    low_contrast = list(CONTRAST_SAFE_CUBE_COLORS)
    low_contrast[1] = "#FF6900"  # push red near orange

    with pytest.raises(ValueError, match="R/L"):
        validate_cube_palette(tuple(low_contrast))


def test_validation_fails_when_yellow_and_orange_are_too_close() -> None:
    low_contrast = list(CONTRAST_SAFE_CUBE_COLORS)
    low_contrast[4] = "#F6F000"  # push orange near yellow

    with pytest.raises(ValueError, match="U/L"):
        validate_cube_palette(tuple(low_contrast))
