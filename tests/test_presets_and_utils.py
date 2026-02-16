from __future__ import annotations

import pytest

from cubeanim.formula import FormulaConverter
from cubeanim.presets import get_preset
from cubeanim.utils import formula_display_chunks, slugify_formula, wrap_formula_for_overlay


def test_sexy_preset_repeat_is_applied() -> None:
    preset = get_preset("Sexy")
    moves = FormulaConverter.convert(preset.formula, repeat=preset.repeat)
    assert preset.repeat == 6
    assert len(moves) == 24


def test_preset_alias_resolves() -> None:
    preset = get_preset("SexyMoveSixTimes")
    assert preset.name == "Sexy"


def test_unknown_preset_fails() -> None:
    with pytest.raises(KeyError):
        get_preset("NotExistingPreset")


def test_formula_slug_generation() -> None:
    slug = slugify_formula("R U R' U'")
    assert slug == "r_u_rp_up"


def test_formula_chunks_keep_parenthesized_groups_together() -> None:
    chunks = formula_display_chunks("R' F' (R U R' U') F (R U2 R')")
    assert chunks == ["R'", "F'", "(R U R' U')", "F", "(R U2 R')"]


def test_formula_overlay_wraps_to_max_two_lines_without_breaking_parentheses() -> None:
    wrapped = wrap_formula_for_overlay(
        "R' F' (R U R' U') F (R U2 R') U",
        max_chars_per_line=18,
        max_lines=2,
    )
    lines = wrapped.splitlines()
    assert len(lines) <= 2
    assert all(line.count("(") == line.count(")") for line in lines)
