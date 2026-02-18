from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from functools import lru_cache

from cubeanim.formula import FormulaConverter
from cubeanim.state import state_slots_metadata, state_string_from_moves

_VALID_FACE_COLORS = set("URFDLB")
_SIDE_FACES = ("F", "R", "B", "L")
_X_ORDER = (1, 0, -1)  # B -> F
_Y_ORDER = (1, 0, -1)  # L -> R

_CENTER_POSITIONS = {
    "U": (0, 0, 1),
    "R": (0, -1, 0),
    "F": (-1, 0, 0),
    "D": (0, 0, -1),
    "L": (0, 1, 0),
    "B": (1, 0, 0),
}

_CORNER_POSITIONS = (
    (1, 1, 1),
    (1, -1, 1),
    (-1, -1, 1),
    (-1, 1, 1),
)
_EDGE_POSITIONS = (
    (1, 0, 1),
    (0, -1, 1),
    (-1, 0, 1),
    (0, 1, 1),
)

_ROW_BY_X = {1: 0, 0: 1, -1: 2}
_COL_BY_Y = {1: 0, 0: 1, -1: 2}


@dataclass(frozen=True)
class PLLArrow:
    start: tuple[int, int]
    end: tuple[int, int]
    bidirectional: bool
    piece_type: str  # "corner" | "edge"


@dataclass(frozen=True)
class PLLTopViewData:
    u_grid: tuple[tuple[str, str, str], tuple[str, str, str], tuple[str, str, str]]
    top_b: tuple[str, str, str]
    right_r: tuple[str, str, str]
    bottom_f: tuple[str, str, str]
    left_l: tuple[str, str, str]
    corner_arrows: tuple[PLLArrow, ...]
    edge_arrows: tuple[PLLArrow, ...]


@dataclass(frozen=True)
class _FaceletState:
    index: int
    position: tuple[int, int, int]
    face: str
    color: str


def _facelets_from_state(state: str) -> list[_FaceletState]:
    if len(state) != 54:
        raise ValueError(f"State must contain exactly 54 facelets, got {len(state)}")
    if not set(state) <= _VALID_FACE_COLORS:
        raise ValueError(
            "State must contain only face colors URFDLB "
            f"(got: {''.join(sorted(set(state)))})"
        )

    slots = state_slots_metadata()
    if len(slots) != 54:
        raise ValueError("Internal state slot metadata is invalid")

    return [
        _FaceletState(index=index, position=slot[0], face=slot[1], color=color)
        for index, (slot, color) in enumerate(zip(slots, state, strict=True))
    ]


def _color_by_face_and_pos(facelets: list[_FaceletState]) -> dict[tuple[str, tuple[int, int, int]], str]:
    return {(facelet.face, facelet.position): facelet.color for facelet in facelets}


def _center_colors(color_lookup: dict[tuple[str, tuple[int, int, int]], str]) -> dict[str, str]:
    return {
        face: color_lookup[(face, center_position)]
        for face, center_position in _CENTER_POSITIONS.items()
    }


def validate_pll_start_state(state: str) -> None:
    facelets = _facelets_from_state(state)
    color_lookup = _color_by_face_and_pos(facelets)
    centers = _center_colors(color_lookup)

    for facelet in facelets:
        x, y, z = facelet.position
        if facelet.face == "U" and facelet.color != "U":
            raise ValueError(
                "Invalid PLL start state: U face must be solved, "
                f"but index {facelet.index} at (x={x}, y={y}, z={z}) is {facelet.color}"
            )

        if facelet.face == "D" and facelet.color != "D":
            raise ValueError(
                "Invalid PLL start state: D face must be solved, "
                f"but index {facelet.index} at (x={x}, y={y}, z={z}) is {facelet.color}"
            )

        if facelet.face in _SIDE_FACES and z != 1 and facelet.color != centers[facelet.face]:
            raise ValueError(
                "Invalid PLL start state: F2L must match side centers, "
                f"but {facelet.face} face index {facelet.index} "
                f"at (x={x}, y={y}, z={z}) is {facelet.color} "
                f"(expected {centers[facelet.face]})"
            )


@lru_cache(maxsize=1)
def _pll_orientation_corrections() -> tuple[tuple[str, ...], ...]:
    rotations = ("x", "x'", "y", "y'", "z", "z'")
    queue: deque[tuple[str, ...]] = deque([tuple()])
    seen_states = {state_string_from_moves([])}
    sequences: list[tuple[str, ...]] = [tuple()]

    while queue and len(seen_states) < 24:
        current = queue.popleft()
        for move in rotations:
            candidate = (*current, move)
            signature = state_string_from_moves(list(candidate))
            if signature in seen_states:
                continue
            seen_states.add(signature)
            sequences.append(candidate)
            queue.append(candidate)
            if len(seen_states) >= 24:
                break

    sequences.sort(key=len)
    return tuple(sequences)


def resolve_valid_pll_start_state(inverse_moves: list[str]) -> str:
    for correction in _pll_orientation_corrections():
        state = state_string_from_moves(inverse_moves + list(correction))
        try:
            validate_pll_start_state(state)
            return state
        except ValueError:
            continue
    for correction in _pll_orientation_corrections():
        state = state_string_from_moves(list(correction) + inverse_moves)
        try:
            validate_pll_start_state(state)
            return state
        except ValueError:
            continue
    return state_string_from_moves(inverse_moves)


def _is_rotation_move(move: str) -> bool:
    base = move[:-1] if move.endswith(("'", "2")) else move
    return base in {"x", "y", "z"}


def balance_pll_formula_rotations(formula: str) -> str:
    normalized = " ".join(formula.split())
    if not normalized:
        return normalized

    steps = FormulaConverter.convert_steps(normalized, repeat=1)
    flat = [move for step in steps for move in step]
    rotation_moves = [move for move in flat if _is_rotation_move(move)]
    if not rotation_moves:
        return normalized

    for correction in _pll_orientation_corrections():
        signature = state_string_from_moves(rotation_moves + list(correction))
        if signature == state_string_from_moves([]):
            if not correction:
                return normalized
            return " ".join([normalized, *correction])
    return normalized


def _position_to_grid(position: tuple[int, int, int]) -> tuple[int, int]:
    x, y, _ = position
    return (_ROW_BY_X[x], _COL_BY_Y[y])


def _side_signature_for_position(position: tuple[int, int, int]) -> tuple[str, ...]:
    x, y, _ = position
    sides: list[str] = []
    if x == -1:
        sides.append("F")
    if x == 1:
        sides.append("B")
    if y == -1:
        sides.append("R")
    if y == 1:
        sides.append("L")
    return tuple(sorted(sides))


def _signature_from_state(
    position: tuple[int, int, int],
    color_lookup: dict[tuple[str, tuple[int, int, int]], str],
    color_to_side: dict[str, str],
) -> tuple[str, ...]:
    x, y, _ = position
    sides: list[str] = []

    if x == -1:
        sides.append(color_to_side[color_lookup[("F", position)]])
    if x == 1:
        sides.append(color_to_side[color_lookup[("B", position)]])
    if y == -1:
        sides.append(color_to_side[color_lookup[("R", position)]])
    if y == 1:
        sides.append(color_to_side[color_lookup[("L", position)]])

    return tuple(sorted(sides))


def _cycles_from_permutation(
    permutation: dict[tuple[int, int, int], tuple[int, int, int]],
    order: tuple[tuple[int, int, int], ...],
) -> list[list[tuple[int, int, int]]]:
    remaining = {position: target for position, target in permutation.items() if position != target}
    cycles: list[list[tuple[int, int, int]]] = []

    while remaining:
        start = next(position for position in order if position in remaining)
        cycle = [start]
        current = remaining.pop(start)
        while current != start:
            cycle.append(current)
            current = remaining.pop(current)
        cycles.append(cycle)

    return cycles


def _arrows_from_cycles(
    cycles: list[list[tuple[int, int, int]]],
    piece_type: str,
) -> tuple[PLLArrow, ...]:
    arrows: list[PLLArrow] = []

    for cycle in cycles:
        if len(cycle) == 2:
            arrows.append(
                PLLArrow(
                    start=_position_to_grid(cycle[0]),
                    end=_position_to_grid(cycle[1]),
                    bidirectional=True,
                    piece_type=piece_type,
                )
            )
            continue

        for index, start in enumerate(cycle):
            end = cycle[(index + 1) % len(cycle)]
            arrows.append(
                PLLArrow(
                    start=_position_to_grid(start),
                    end=_position_to_grid(end),
                    bidirectional=False,
                    piece_type=piece_type,
                )
            )

    return tuple(arrows)


def _permutation_for_positions(
    positions: tuple[tuple[int, int, int], ...],
    color_lookup: dict[tuple[str, tuple[int, int, int]], str],
    color_to_side: dict[str, str],
) -> dict[tuple[int, int, int], tuple[int, int, int]]:
    solved_lookup = {
        _side_signature_for_position(position): position
        for position in positions
    }
    return {
        position: solved_lookup[_signature_from_state(position, color_lookup, color_to_side)]
        for position in positions
    }


def build_pll_top_view_data(state: str) -> PLLTopViewData:
    facelets = _facelets_from_state(state)
    color_lookup = _color_by_face_and_pos(facelets)
    centers = _center_colors(color_lookup)
    color_to_side = {centers[face]: face for face in _SIDE_FACES}

    if len(color_to_side) != 4:
        raise ValueError("Invalid PLL start state: side center colors must be unique")

    def color_at(face: str, position: tuple[int, int, int]) -> str:
        return color_lookup[(face, position)]

    u_grid = tuple(
        tuple(color_at("U", (x, y, 1)) for y in _Y_ORDER)
        for x in _X_ORDER
    )
    top_b = tuple(color_at("B", (1, y, 1)) for y in _Y_ORDER)
    right_r = tuple(color_at("R", (x, -1, 1)) for x in _X_ORDER)
    bottom_f = tuple(color_at("F", (-1, y, 1)) for y in _Y_ORDER)
    left_l = tuple(color_at("L", (x, 1, 1)) for x in _X_ORDER)

    corner_permutation = _permutation_for_positions(_CORNER_POSITIONS, color_lookup, color_to_side)
    edge_permutation = _permutation_for_positions(_EDGE_POSITIONS, color_lookup, color_to_side)

    corner_cycles = _cycles_from_permutation(corner_permutation, _CORNER_POSITIONS)
    edge_cycles = _cycles_from_permutation(edge_permutation, _EDGE_POSITIONS)

    return PLLTopViewData(
        u_grid=u_grid,
        top_b=top_b,
        right_r=right_r,
        bottom_f=bottom_f,
        left_l=left_l,
        corner_arrows=_arrows_from_cycles(corner_cycles, piece_type="corner"),
        edge_arrows=_arrows_from_cycles(edge_cycles, piece_type="edge"),
    )
