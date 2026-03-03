from __future__ import annotations

import pytest

from cubeanim.cards.sandbox import build_sandbox_timeline
from cubeanim.oll import validate_oll_f2l_start_state
from cubeanim.pll import validate_pll_start_state


def test_build_sandbox_timeline_lengths_and_shapes() -> None:
    timeline = build_sandbox_timeline("R U R' U'", "PLL")
    assert timeline.formula == "R U R' U'"
    assert timeline.group == "PLL"
    assert len(timeline.move_steps) == 4
    assert len(timeline.moves_flat) == 4
    assert len(timeline.states_by_step) == len(timeline.move_steps) + 1
    assert len(timeline.state_slots) == 54
    assert all(len(state) == 54 for state in timeline.states_by_step)


def test_build_sandbox_timeline_keeps_plus_as_single_beat() -> None:
    timeline = build_sandbox_timeline("U+D R U'+D'", "PLL")
    assert timeline.move_steps[0] == ["U", "D"]
    assert timeline.highlight_by_step[0] == "U+D"
    assert timeline.highlight_by_step[-1] == "U'+D'"
    assert len(timeline.states_by_step) == 4


def test_build_sandbox_timeline_auto_merges_ud_prime_pairs() -> None:
    timeline = build_sandbox_timeline("U D' R U' D", "PLL")
    assert timeline.move_steps == [["U", "D'"], ["R"], ["U'", "D"]]
    assert timeline.highlight_by_step == ["U+D'", "R", "U'+D"]
    assert len(timeline.states_by_step) == len(timeline.move_steps) + 1


def test_build_sandbox_timeline_does_not_merge_other_ud_pairs() -> None:
    timeline = build_sandbox_timeline("U D U2 D2", "PLL")
    assert timeline.move_steps == [["U"], ["D"], ["U2"], ["D2"]]


def test_build_sandbox_timeline_uses_oll_start_resolver() -> None:
    timeline = build_sandbox_timeline("R' F R U R' F' R (y') R U' R'", "OLL")
    validate_oll_f2l_start_state(timeline.initial_state)


def test_build_sandbox_timeline_rejects_invalid_oll_start_formula() -> None:
    with pytest.raises(ValueError, match="Invalid OLL start state"):
        build_sandbox_timeline("M U (R U R' U') M2 (U R U' R') U' M", "OLL")


def test_build_sandbox_timeline_uses_pll_start_resolver() -> None:
    timeline = build_sandbox_timeline("x' L2 D2 L U L' D2 L U' L", "PLL")
    validate_pll_start_state(timeline.initial_state)


def test_build_sandbox_timeline_rejects_empty_formula() -> None:
    with pytest.raises(ValueError, match="Formula must be non-empty"):
        build_sandbox_timeline("   ", "PLL")
