from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cubeanim_domain.formula import FormulaConverter
from cubeanim_domain.oll import resolve_valid_oll_start_state, validate_oll_f2l_start_state
from cubeanim_domain.pll import resolve_valid_pll_start_state
from cubeanim_domain.state import state_slots_metadata, state_string_after_moves, state_string_from_moves

_SUPPORTED_GROUPS = {"F2L", "OLL", "PLL"}
_AUTO_MERGE_UD_PAIRS = {
    ("U", "D'"),
    ("D'", "U"),
    ("U'", "D"),
    ("D", "U'"),
}


@dataclass(frozen=True)
class SandboxTimeline:
    formula: str
    group: str
    move_steps: list[list[str]]
    moves_flat: list[str]
    initial_state: str
    states_by_step: list[str]
    highlight_by_step: list[str]
    state_slots: list[dict[str, Any]]


def _normalize_formula(formula: str) -> str:
    return " ".join(formula.split())


def _resolve_initial_state(group: str, inverse_moves: list[str]) -> str:
    if group == "OLL":
        state = resolve_valid_oll_start_state(inverse_moves)
        validate_oll_f2l_start_state(state)
        return state
    if group == "PLL":
        return resolve_valid_pll_start_state(inverse_moves)
    return state_string_from_moves(inverse_moves)


def resolve_start_state(group: str, inverse_moves: list[str]) -> str:
    normalized_group = group.strip().upper()
    if normalized_group not in _SUPPORTED_GROUPS:
        raise ValueError(f"group must be one of {sorted(_SUPPORTED_GROUPS)}")
    return _resolve_initial_state(normalized_group, inverse_moves)


def _serialize_state_slots() -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for position, face in state_slots_metadata():
        x, y, z = position
        serialized.append({"position": [x, y, z], "face": face})
    return serialized


def _should_merge_adjacent_steps(first_step: list[str], second_step: list[str]) -> bool:
    if len(first_step) != 1 or len(second_step) != 1:
        return False
    return (first_step[0], second_step[0]) in _AUTO_MERGE_UD_PAIRS


def _merge_parallel_ud_steps(move_steps: list[list[str]]) -> list[list[str]]:
    merged: list[list[str]] = []
    index = 0
    while index < len(move_steps):
        current = move_steps[index]
        if index + 1 < len(move_steps):
            next_step = move_steps[index + 1]
            if _should_merge_adjacent_steps(current, next_step):
                merged.append([current[0], next_step[0]])
                index += 2
                continue
        merged.append(current[:])
        index += 1
    return merged


def build_sandbox_timeline(formula: str, group: str) -> SandboxTimeline:
    normalized_group = group.strip().upper()
    if normalized_group not in _SUPPORTED_GROUPS:
        raise ValueError(f"group must be one of {sorted(_SUPPORTED_GROUPS)}")

    normalized_formula = _normalize_formula(formula)
    if not normalized_formula:
        raise ValueError("Formula must be non-empty")

    parsed_steps = FormulaConverter.convert_steps(normalized_formula, repeat=1)
    move_steps = _merge_parallel_ud_steps(parsed_steps)
    moves_flat = [move for step in move_steps for move in step]
    inverse_steps = FormulaConverter.invert_steps(move_steps)
    inverse_flat = [move for step in inverse_steps for move in step]
    initial_state = resolve_start_state(normalized_group, inverse_flat)

    states_by_step = [initial_state]
    current_state = initial_state
    for step in move_steps:
        current_state = state_string_after_moves(current_state, step)
        states_by_step.append(current_state)

    highlight_by_step = ["+".join(step) for step in move_steps]

    normalized_beats = " ".join(highlight_by_step)

    return SandboxTimeline(
        formula=normalized_beats,
        group=normalized_group,
        move_steps=[step[:] for step in move_steps],
        moves_flat=moves_flat,
        initial_state=initial_state,
        states_by_step=states_by_step,
        highlight_by_step=highlight_by_step,
        state_slots=_serialize_state_slots(),
    )
