from __future__ import annotations

import pytest

from cubeanim.formula import FormulaConverter
from cubeanim.oll import build_oll_top_view_data, validate_oll_f2l_start_state
from cubeanim.state import solved_state_string, state_slots_metadata, state_string_from_moves


def _start_state_for_formula(formula: str) -> str:
    moves = FormulaConverter.convert(formula)
    inverse = FormulaConverter.invert_moves(moves)
    return state_string_from_moves(inverse)


def _any_true(values: tuple[bool, bool, bool]) -> bool:
    return any(values)


def test_oll_validation_pass_for_known_oll_formula() -> None:
    state = _start_state_for_formula("R U R' U R U2 R'")
    validate_oll_f2l_start_state(state)


def test_oll_validation_fails_for_non_oll_start_case() -> None:
    state = _start_state_for_formula("R U")
    with pytest.raises(ValueError, match="Invalid OLL start state"):
        validate_oll_f2l_start_state(state)


def test_top_view_on_solved_state_is_full_yellow_and_no_side_indicators() -> None:
    data = build_oll_top_view_data(solved_state_string())
    assert all(all(cell for cell in row) for row in data.u_grid)
    assert not _any_true(data.top_b)
    assert not _any_true(data.right_r)
    assert not _any_true(data.bottom_f)
    assert not _any_true(data.left_l)


def test_top_view_on_oll_start_contains_gray_cells_and_side_indicators() -> None:
    state = _start_state_for_formula("R U R' U R U2 R'")
    data = build_oll_top_view_data(state)

    assert any(not cell for row in data.u_grid for cell in row)
    assert any(
        (
            _any_true(data.top_b),
            _any_true(data.right_r),
            _any_true(data.bottom_f),
            _any_true(data.left_l),
        )
    )


def test_top_view_orientation_is_b_top_f_bottom_l_left_r_right() -> None:
    slots = state_slots_metadata()
    state_chars = list(solved_state_string())

    def set_yellow(face: str, position: tuple[int, int, int]) -> None:
        for index, (slot_position, slot_face) in enumerate(slots):
            if slot_face == face and slot_position == position:
                state_chars[index] = "U"
                return
        raise AssertionError(f"Slot not found for {face} at {position}")

    set_yellow("B", (1, 1, 1))
    set_yellow("F", (-1, -1, 1))
    set_yellow("L", (0, 1, 1))
    set_yellow("R", (1, -1, 1))

    data = build_oll_top_view_data("".join(state_chars))

    assert data.top_b == (True, False, False)
    assert data.bottom_f == (False, False, True)
    assert data.left_l == (False, True, False)
    assert data.right_r == (True, False, False)
