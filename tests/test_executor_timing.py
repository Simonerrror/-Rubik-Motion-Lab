from __future__ import annotations

import pytest

from cubeanim.executor import ExecutionConfig, MoveExecutor


def test_single_turn_uses_base_runtime() -> None:
    config = ExecutionConfig(run_time=0.65, double_turn_multiplier=1.7)
    assert MoveExecutor._step_run_time(["R"], config) == 0.65


def test_double_turn_uses_multiplier_of_base_runtime() -> None:
    config = ExecutionConfig(run_time=0.65, double_turn_multiplier=1.7)
    assert MoveExecutor._step_run_time(["R2"], config) == pytest.approx(1.105)


def test_simultaneous_double_turns_use_multiplier_of_base_runtime() -> None:
    config = ExecutionConfig(run_time=0.65, double_turn_multiplier=1.7)
    assert MoveExecutor._step_run_time(["U2", "D2"], config) == pytest.approx(1.105)


def test_inter_move_pause_is_five_percent_of_single_runtime() -> None:
    config = ExecutionConfig(run_time=0.65, inter_move_pause_ratio=0.05)
    assert MoveExecutor._inter_move_pause(config) == pytest.approx(0.0325)
