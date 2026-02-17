from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

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
    # Reproduce the exact set_state order in manim_rubikscube.cube.RubiksCube.set_state.
    cube_idx = np.empty((3, 3, 3), dtype=object)
    for x in range(3):
        for y in range(3):
            for z in range(3):
                cube_idx[x, y, z] = (x - 1, y - 1, z - 1)

    slots: list[tuple[tuple[int, int, int], str]] = []
    slots.extend((p, "U") for p in np.rot90(cube_idx[:, :, 2], 2).flatten())
    slots.extend((p, "R") for p in np.rot90(np.flip(cube_idx[:, 0, :], (0, 1)), -1).flatten())
    slots.extend((p, "F") for p in np.rot90(np.flip(cube_idx[0, :, :], 0)).flatten())
    slots.extend((p, "D") for p in np.rot90(np.flip(cube_idx[:, :, 0], 0), 2).flatten())
    slots.extend((p, "L") for p in np.rot90(np.flip(cube_idx[:, 2, :], 0)).flatten())
    slots.extend((p, "B") for p in np.rot90(np.flip(cube_idx[2, :, :], (0, 1)), -1).flatten())
    return slots


def state_slots_metadata() -> list[tuple[tuple[int, int, int], str]]:
    """Returns facelet slots in the exact order expected by RubiksCube.set_state."""
    return list(_state_slots())


def state_string_from_moves(moves: list[str]) -> str:
    stickers = _solved_stickers()
    for move in moves:
        _apply_move(stickers, move)

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
