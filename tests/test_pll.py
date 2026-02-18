from __future__ import annotations

import pytest

from cubeanim.formula import FormulaConverter
from cubeanim.pll import build_pll_top_view_data, resolve_valid_pll_start_state, validate_pll_start_state
from cubeanim.state import solved_state_string, state_string_from_moves


def _inverse_moves_for_formula(formula: str) -> list[str]:
    steps = FormulaConverter.convert_steps(formula, repeat=1)
    inverse_steps = FormulaConverter.invert_steps(steps)
    return [move for step in inverse_steps for move in step]


def _start_state_for_formula(formula: str) -> str:
    return state_string_from_moves(_inverse_moves_for_formula(formula))


def test_pll_validation_pass_for_known_pll_formula() -> None:
    state = _start_state_for_formula("M2 U M U2 M' U M2")
    validate_pll_start_state(state)


def test_pll_validation_fails_for_non_pll_start_case() -> None:
    state = _start_state_for_formula("R U")
    with pytest.raises(ValueError, match="Invalid PLL start state"):
        validate_pll_start_state(state)


def test_pll_top_view_on_solved_state_has_no_arrows() -> None:
    data = build_pll_top_view_data(solved_state_string())
    assert all(all(cell == "U" for cell in row) for row in data.u_grid)
    assert len(data.corner_arrows) == 0
    assert len(data.edge_arrows) == 0


def test_ua_has_three_directed_edge_arrows_and_no_corner_arrows() -> None:
    state = _start_state_for_formula("M2 U M U2 M' U M2")
    data = build_pll_top_view_data(state)

    assert len(data.corner_arrows) == 0
    assert len(data.edge_arrows) == 3
    assert all(not arrow.bidirectional for arrow in data.edge_arrows)

    points = {arrow.start for arrow in data.edge_arrows} | {arrow.end for arrow in data.edge_arrows}
    assert points == {(1, 0), (1, 2), (2, 1)}

    outgoing = {point: 0 for point in points}
    incoming = {point: 0 for point in points}
    for arrow in data.edge_arrows:
        outgoing[arrow.start] += 1
        incoming[arrow.end] += 1

    assert all(count == 1 for count in outgoing.values())
    assert all(count == 1 for count in incoming.values())


def test_vperm_has_bidirectional_corner_and_edge_swaps() -> None:
    state = _start_state_for_formula("R' U R' d' R' F' R2 U' R' U R' F R F")
    data = build_pll_top_view_data(state)

    assert len(data.corner_arrows) == 1
    assert len(data.edge_arrows) == 1
    assert data.corner_arrows[0].bidirectional
    assert data.edge_arrows[0].bidirectional

    corner_pair = frozenset((data.corner_arrows[0].start, data.corner_arrows[0].end))
    edge_pair = frozenset((data.edge_arrows[0].start, data.edge_arrows[0].end))
    assert corner_pair == {(0, 0), (2, 2)}
    assert edge_pair == {(0, 1), (1, 2)}


def test_center_relative_piece_identification_handles_global_y_rotation() -> None:
    inverse_moves = _inverse_moves_for_formula("R' U R' d' R' F' R2 U' R' U R' F R F")
    base_state = state_string_from_moves(inverse_moves)
    y_rotated_state = state_string_from_moves(["y", *inverse_moves])

    validate_pll_start_state(base_state)
    validate_pll_start_state(y_rotated_state)

    base_data = build_pll_top_view_data(base_state)
    rotated_data = build_pll_top_view_data(y_rotated_state)

    base_corner_pair = frozenset((base_data.corner_arrows[0].start, base_data.corner_arrows[0].end))
    base_edge_pair = frozenset((base_data.edge_arrows[0].start, base_data.edge_arrows[0].end))
    rotated_corner_pair = frozenset((rotated_data.corner_arrows[0].start, rotated_data.corner_arrows[0].end))
    rotated_edge_pair = frozenset((rotated_data.edge_arrows[0].start, rotated_data.edge_arrows[0].end))

    assert base_corner_pair == rotated_corner_pair
    assert base_edge_pair == rotated_edge_pair


def test_zperm_is_edges_only_with_adjacent_bidirectional_swaps() -> None:
    state = _start_state_for_formula("M2 U M2 U M' U2 M2 U2 M' U2")
    data = build_pll_top_view_data(state)

    assert len(data.corner_arrows) == 0
    assert len(data.edge_arrows) == 2
    assert all(arrow.bidirectional for arrow in data.edge_arrows)

    edge_pairs = {
        frozenset((arrow.start, arrow.end))
        for arrow in data.edge_arrows
    }
    assert edge_pairs == {
        frozenset({(0, 1), (1, 0)}),
        frozenset({(1, 2), (2, 1)}),
    }


def test_resolve_valid_pll_start_state_handles_global_rotation_formulas() -> None:
    # Ab contains cube rotation and should still resolve to a valid PLL start state.
    inverse = _inverse_moves_for_formula("x' L2 D2 L U L' D2 L U' L")
    resolved_state = resolve_valid_pll_start_state(inverse)
    validate_pll_start_state(resolved_state)
