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


def test_step_duration_math_with_custom_runtime_profile() -> None:
    config = ExecutionConfig(run_time=0.8, double_turn_multiplier=1.7, inter_move_pause_ratio=0.05)
    single = MoveExecutor._step_run_time(["R"], config)
    double_step = MoveExecutor._step_run_time(["U2", "D2"], config)
    pause = MoveExecutor._inter_move_pause(config)

    assert single == pytest.approx(0.8)
    assert double_step == pytest.approx(1.36)
    assert pause == pytest.approx(0.04)


def test_play_prefers_explicit_initial_state_over_inverse_steps(monkeypatch) -> None:
    class _DummyCube:
        def __init__(self) -> None:
            self.states: list[str] = []

        def set_state(self, state: str) -> None:
            self.states.append(state)

    class _DummyScene:
        def add_fixed_in_frame_mobjects(self, *args, **kwargs) -> None:
            _ = args, kwargs

        def add(self, *args, **kwargs) -> None:
            _ = args, kwargs

        def wait(self, *args, **kwargs) -> None:
            _ = args, kwargs

        def play(self, *args, **kwargs) -> None:
            _ = args, kwargs

    for name in (
        "_add_algorithm_name",
        "_add_formula_overlay",
        "_add_oll_top_view_overlay",
        "_add_pll_top_view_overlay",
    ):
        monkeypatch.setattr(MoveExecutor, name, staticmethod(lambda *args, **kwargs: None))

    cube = _DummyCube()
    scene = _DummyScene()
    config = ExecutionConfig()

    MoveExecutor.play(
        scene,
        cube,
        move_steps=[],
        config=config,
        initial_state="START_STATE",
        inverse_steps=[["R"], ["U"]],
    )

    assert cube.states == ["START_STATE"]
