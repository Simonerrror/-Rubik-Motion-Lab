from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cubeanim.formula import FormulaConverter
from cubeanim.oll import resolve_valid_oll_start_state
from cubeanim.pll import resolve_valid_pll_start_state
from cubeanim.state import state_slots_metadata, state_string_from_moves

_SUPPORTED_GROUPS = {"F2L", "OLL", "PLL"}


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
        return resolve_valid_oll_start_state(inverse_moves)
    if group == "PLL":
        return resolve_valid_pll_start_state(inverse_moves)
    return state_string_from_moves(inverse_moves)


def _serialize_state_slots() -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for position, face in state_slots_metadata():
        x, y, z = position
        serialized.append({"position": [x, y, z], "face": face})
    return serialized


def build_sandbox_timeline(formula: str, group: str) -> SandboxTimeline:
    normalized_group = group.strip().upper()
    if normalized_group not in _SUPPORTED_GROUPS:
        raise ValueError(f"group must be one of {sorted(_SUPPORTED_GROUPS)}")

    normalized_formula = _normalize_formula(formula)
    if not normalized_formula:
        raise ValueError("Formula must be non-empty")

    move_steps = FormulaConverter.convert_steps(normalized_formula, repeat=1)
    moves_flat = [move for step in move_steps for move in step]
    inverse_steps = FormulaConverter.invert_steps(move_steps)
    inverse_flat = [move for step in inverse_steps for move in step]
    initial_state = _resolve_initial_state(normalized_group, inverse_flat)

    states_by_step = [initial_state]
    executed_moves: list[str] = []
    for step in move_steps:
        executed_moves.extend(step)
        states_by_step.append(state_string_from_moves(inverse_flat + executed_moves))

    highlight_by_step = ["+".join(step) for step in move_steps]

    return SandboxTimeline(
        formula=normalized_formula,
        group=normalized_group,
        move_steps=[step[:] for step in move_steps],
        moves_flat=moves_flat,
        initial_state=initial_state,
        states_by_step=states_by_step,
        highlight_by_step=highlight_by_step,
        state_slots=_serialize_state_slots(),
    )
