from __future__ import annotations

import csv
from pathlib import Path
import re

import pytest

from cubeanim.animations import CubeMoveConcurrent
from cubeanim.formula import FormulaConverter, FormulaSyntaxError
from cubeanim.oll import resolve_valid_oll_start_state, validate_oll_f2l_start_state
from cubeanim.pll import resolve_valid_pll_start_state, validate_pll_start_state
from cubeanim.state import solved_state_string, state_string_from_moves


def _inverse_moves_for_formula(formula: str) -> list[str]:
    steps = FormulaConverter.convert_steps(formula, repeat=1)
    inverse_steps = FormulaConverter.invert_steps(steps)
    return [move for step in inverse_steps for move in step]


def _assert_roundtrip(formula: str) -> None:
    moves = FormulaConverter.convert(formula)
    inverse = FormulaConverter.invert_moves(moves)
    assert state_string_from_moves(moves + inverse) == solved_state_string()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _contains_rotation_move(formula: str) -> bool:
    return re.search(r"(?<![A-Za-z0-9_])[xyz](?:2|')?(?![A-Za-z0-9_])", formula) is not None


def _oll_rotation_formulas() -> list[str]:
    formulas: list[str] = []
    with (_repo_root() / "oll.txt").open("r", encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        next(reader, None)
        for row in reader:
            if len(row) < 3:
                continue
            formula = " ".join(str(row[2]).split())
            if not formula:
                continue
            if _contains_rotation_move(formula):
                formulas.append(formula)
    return formulas


@pytest.mark.parametrize("formula", ["x", "x'", "x2", "y", "y'", "y2", "z", "z'", "z2"])
def test_single_rotations_roundtrip(formula: str) -> None:
    _assert_roundtrip(formula)


@pytest.mark.parametrize(
    "formula",
    [
        "R U f r2 M E' x y' z2",
        "(R U x')2 y2",
        "z (R U R' U') x' F2 d",
    ],
)
def test_mixed_formulas_with_rotations_roundtrip(formula: str) -> None:
    _assert_roundtrip(formula)


def test_parser_allows_simultaneous_moves_on_same_axis() -> None:
    assert FormulaConverter.convert_steps("U+D")[0] == ["U", "D"]
    assert FormulaConverter.convert_steps("R+M")[0] == ["R", "M"]
    assert FormulaConverter.convert_steps("x+R")[0] == ["x", "R"]


@pytest.mark.parametrize("formula", ["U+R", "F+U", "x+U"])
def test_parser_rejects_simultaneous_moves_on_different_axes(formula: str) -> None:
    with pytest.raises(FormulaSyntaxError, match="Simultaneous moves must share axis"):
        FormulaConverter.convert_steps(formula)


def test_runtime_safety_net_rejects_simultaneous_moves_on_different_axes() -> None:
    with pytest.raises(ValueError, match="Simultaneous moves must rotate around the same axis"):
        CubeMoveConcurrent(None, ["U", "R"])  # type: ignore[arg-type]


def test_oll_rotation_formulas_from_catalog_resolve_valid_start_state() -> None:
    formulas = _oll_rotation_formulas()
    assert formulas, "Expected at least one OLL formula with x/y/z rotations in oll.txt"

    for formula in formulas:
        inverse = _inverse_moves_for_formula(formula)
        resolved_state = resolve_valid_oll_start_state(inverse)
        validate_oll_f2l_start_state(resolved_state)


def test_pll_rotation_formula_resolves_valid_start_state() -> None:
    inverse = _inverse_moves_for_formula("x' L2 D2 L U L' D2 L U' L")
    resolved_state = resolve_valid_pll_start_state(inverse)
    validate_pll_start_state(resolved_state)
