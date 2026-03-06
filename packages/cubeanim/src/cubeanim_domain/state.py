from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

_FACE_ORDER = "URFDLB"

_NORMAL_TO_FACE = {
    (0, 0, 1): "U",
    (0, -1, 0): "R",
    (-1, 0, 0): "F",
    (0, 0, -1): "D",
    (0, 1, 0): "L",
    (1, 0, 0): "B",
}

_FACE_TO_COLOR = {
    "U": "U",
    "R": "R",
    "F": "F",
    "D": "D",
    "L": "L",
    "B": "B",
}

_MOVE_POSITIVE_BASES = {"R", "F", "D", "E", "S", "r", "f", "d", "x", "z"}


@dataclass
class _Sticker:
    p: tuple[int, int, int]
    n: tuple[int, int, int]
    color: str


def _split_move_modifier(move: str) -> tuple[str, str]:
    if move.endswith("2"):
        return move[:-1], "2"
    if move.endswith("'"):
        return move[:-1], "'"
    return move, ""


def _axis_for_base(base: str) -> str:
    if base in ("F", "B", "S", "f", "b", "z"):
        return "x"
    if base in ("U", "D", "E", "u", "d", "y"):
        return "z"
    if base in ("L", "R", "M", "l", "r", "x"):
        return "y"
    raise ValueError(f"Unsupported move base: {base}")


def _selector_for_base(base: str) -> Callable[[tuple[int, int, int]], bool]:
    if base == "F":
        return lambda p: p[0] == -1
    if base == "B":
        return lambda p: p[0] == 1
    if base == "S":
        return lambda p: p[0] == 0
    if base == "f":
        return lambda p: p[0] in (-1, 0)
    if base == "b":
        return lambda p: p[0] in (0, 1)

    if base == "U":
        return lambda p: p[2] == 1
    if base == "D":
        return lambda p: p[2] == -1
    if base == "E":
        return lambda p: p[2] == 0
    if base == "u":
        return lambda p: p[2] in (0, 1)
    if base == "d":
        return lambda p: p[2] in (-1, 0)

    if base == "L":
        return lambda p: p[1] == 1
    if base == "R":
        return lambda p: p[1] == -1
    if base == "M":
        return lambda p: p[1] == 0
    if base == "l":
        return lambda p: p[1] in (0, 1)
    if base == "r":
        return lambda p: p[1] in (-1, 0)

    if base in ("x", "y", "z"):
        return lambda p: True

    raise ValueError(f"Unsupported move base: {base}")


def _turns_for_move(base: str, modifier: str) -> int:
    turns = 1 if base in _MOVE_POSITIVE_BASES else -1
    if modifier == "'":
        turns *= -1
    elif modifier == "2":
        turns *= 2
    return turns


def _rotate_vec(vec: tuple[int, int, int], axis: str, direction: int) -> tuple[int, int, int]:
    x, y, z = vec
    if axis == "x":
        if direction > 0:
            return (x, -z, y)
        return (x, z, -y)
    if axis == "y":
        if direction > 0:
            return (z, y, -x)
        return (-z, y, x)
    if axis == "z":
        if direction > 0:
            return (-y, x, z)
        return (y, -x, z)
    raise ValueError(f"Unsupported axis: {axis}")


def _solved_stickers() -> list[_Sticker]:
    stickers: list[_Sticker] = []
    for x in (-1, 0, 1):
        for y in (-1, 0, 1):
            for z in (-1, 0, 1):
                p = (x, y, z)
                if z == 1:
                    stickers.append(_Sticker(p=p, n=(0, 0, 1), color="U"))
                if z == -1:
                    stickers.append(_Sticker(p=p, n=(0, 0, -1), color="D"))
                if y == -1:
                    stickers.append(_Sticker(p=p, n=(0, -1, 0), color="R"))
                if y == 1:
                    stickers.append(_Sticker(p=p, n=(0, 1, 0), color="L"))
                if x == -1:
                    stickers.append(_Sticker(p=p, n=(-1, 0, 0), color="F"))
                if x == 1:
                    stickers.append(_Sticker(p=p, n=(1, 0, 0), color="B"))
    return stickers


def _stickers_from_state(state: str) -> list[_Sticker]:
    if len(state) != 54:
        raise ValueError(f"State must contain exactly 54 facelets, got {len(state)}")

    stickers: list[_Sticker] = []
    for (position, face), color in zip(_state_slots(), state, strict=True):
        normal = next((normal for normal, mapped_face in _NORMAL_TO_FACE.items() if mapped_face == face), None)
        if normal is None:
            raise ValueError(f"Unsupported face in state slots: {face}")
        stickers.append(_Sticker(p=position, n=normal, color=color))
    return stickers


def _apply_move(stickers: list[_Sticker], move: str) -> None:
    base, modifier = _split_move_modifier(move)
    axis = _axis_for_base(base)
    selector = _selector_for_base(base)

    turns = _turns_for_move(base, modifier)
    if turns == 0:
        return

    steps = abs(turns)
    direction = 1 if turns > 0 else -1
    for _ in range(steps):
        for sticker in stickers:
            if selector(sticker.p):
                sticker.p = _rotate_vec(sticker.p, axis=axis, direction=direction)
                sticker.n = _rotate_vec(sticker.n, axis=axis, direction=direction)


def _state_slots() -> list[tuple[tuple[int, int, int], str]]:
    # Keep set_state slot order compatible with RubikCube3D.set_state.
    cube_idx: list[list[list[tuple[int, int, int]]]] = [
        [[(-1, -1, -1) for _ in range(3)] for _ in range(3)]
        for _ in range(3)
    ]
    for x in range(3):
        for y in range(3):
            for z in range(3):
                cube_idx[x][y][z] = (x - 1, y - 1, z - 1)

    def _flip(matrix: list[list[tuple[int, int, int]]], axes: tuple[int, ...]) -> list[list[tuple[int, int, int]]]:
        flipped = [list(row) for row in matrix]
        if 0 in axes:
            flipped = list(reversed(flipped))
        if 1 in axes:
            flipped = [list(reversed(row)) for row in flipped]
        return flipped

    def _rot90(matrix: list[list[tuple[int, int, int]]], k: int = 1) -> list[list[tuple[int, int, int]]]:
        turns = k % 4
        rotated = [list(row) for row in matrix]
        for _ in range(turns):
            rotated = [list(row) for row in zip(*rotated[::-1], strict=True)]
        return rotated

    def _flatten(matrix: list[list[tuple[int, int, int]]]) -> list[tuple[int, int, int]]:
        return [item for row in matrix for item in row]

    def _slice_xy(z_index: int) -> list[list[tuple[int, int, int]]]:
        return [[cube_idx[x][y][z_index] for y in range(3)] for x in range(3)]

    def _slice_xz(y_index: int) -> list[list[tuple[int, int, int]]]:
        return [[cube_idx[x][y_index][z] for z in range(3)] for x in range(3)]

    def _slice_yz(x_index: int) -> list[list[tuple[int, int, int]]]:
        return [[cube_idx[x_index][y][z] for z in range(3)] for y in range(3)]

    slots: list[tuple[tuple[int, int, int], str]] = []
    slots.extend((p, "U") for p in _flatten(_rot90(_slice_xy(2), 2)))
    slots.extend((p, "R") for p in _flatten(_rot90(_flip(_slice_xz(0), (0, 1)), -1)))
    slots.extend((p, "F") for p in _flatten(_rot90(_flip(_slice_yz(0), (0,)))))
    slots.extend((p, "D") for p in _flatten(_rot90(_flip(_slice_xy(0), (0,)), 2)))
    slots.extend((p, "L") for p in _flatten(_rot90(_flip(_slice_xz(2), (0,)))))
    slots.extend((p, "B") for p in _flatten(_rot90(_flip(_slice_yz(2), (0, 1)), -1)))
    return slots


def state_slots_metadata() -> list[tuple[tuple[int, int, int], str]]:
    """Returns facelet slots in the exact order expected by RubikCube3D.set_state."""
    return list(_state_slots())


def state_string_from_moves(moves: list[str]) -> str:
    stickers = _solved_stickers()
    for move in moves:
        _apply_move(stickers, move)

    return _state_string_from_stickers(stickers)


def state_string_after_moves(state: str, moves: list[str]) -> str:
    stickers = _stickers_from_state(state)
    for move in moves:
        _apply_move(stickers, move)

    return _state_string_from_stickers(stickers)


def _state_string_from_stickers(stickers: list[_Sticker]) -> str:
    lookup: dict[tuple[tuple[int, int, int], str], str] = {}
    for sticker in stickers:
        face = _NORMAL_TO_FACE[sticker.n]
        lookup[(sticker.p, face)] = _FACE_TO_COLOR[sticker.color]

    state = []
    for slot in _state_slots():
        state.append(lookup[slot])

    return "".join(state)


def solved_state_string() -> str:
    return "".join(face * 9 for face in _FACE_ORDER)
