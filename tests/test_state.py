from __future__ import annotations

from cubeanim.formula import FormulaConverter
from cubeanim.state import solved_state_string, state_string_from_moves


def test_solved_state_string_layout() -> None:
    assert solved_state_string() == "U" * 9 + "R" * 9 + "F" * 9 + "D" * 9 + "L" * 9 + "B" * 9


def test_state_from_empty_moves_is_solved() -> None:
    assert state_string_from_moves([]) == solved_state_string()


def test_state_from_formula_has_valid_facelet_string() -> None:
    moves = FormulaConverter.convert("R U R' U'")
    state = state_string_from_moves(moves)
    assert len(state) == 54
    assert set(state) <= set("URFDLB")


def test_moves_followed_by_inverse_return_solved_for_extended_notation() -> None:
    moves = FormulaConverter.convert("R U f r2 M E' x y' z2")
    inverse = FormulaConverter.invert_moves(moves)
    state = state_string_from_moves(moves + inverse)
    assert state == solved_state_string()
