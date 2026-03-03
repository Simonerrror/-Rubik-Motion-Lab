from __future__ import annotations

import numpy as np
import pytest
from manim import PI, Y_AXIS, Z_AXIS, ManimColor, VGroup

from cubeanim.animations import CubeMoveExtended
from cubeanim.rubik_core import RubikCube3D
from cubeanim.state import state_slots_metadata, state_string_from_moves


def _cube_state_string(cube: RubikCube3D) -> str:
    color_lookup = {
        ManimColor(cube.colors[index]).to_hex().lower(): face
        for index, face in enumerate(("U", "R", "F", "D", "L", "B"))
    }
    chars: list[str] = []
    for (x, y, z), face in state_slots_metadata():
        cubie = cube.cubies[x + 1, y + 1, z + 1]
        color_hex = cubie.get_face(face).get_fill_color().to_hex().lower()
        chars.append(color_lookup[color_hex])
    return "".join(chars)


def _assert_cubies_match_indices(cube: RubikCube3D, moved_targets: np.ndarray) -> None:
    for cubie in moved_targets.flatten():
        expected_index = cube.indices[cubie.get_rounded_center()]
        actual = cube.cubies[expected_index[0], expected_index[1], expected_index[2]]
        assert actual is cubie


def test_rubik_core_set_state_matches_state_slots_order() -> None:
    cube = RubikCube3D()
    expected_state = state_string_from_moves(["R", "U", "R'", "F2"])
    cube.set_state(expected_state)
    assert _cube_state_string(cube) == expected_state


@pytest.mark.parametrize(
    ("move", "expected_count"),
    [
        ("F", 9),
        ("B", 9),
        ("U", 9),
        ("D", 9),
        ("L", 9),
        ("R", 9),
        ("M", 9),
        ("E", 9),
        ("S", 9),
        ("f", 18),
        ("b", 18),
        ("u", 18),
        ("d", 18),
        ("l", 18),
        ("r", 18),
        ("x", 27),
        ("y", 27),
        ("z", 27),
    ],
)
def test_rubik_core_targets_count_parity(move: str, expected_count: int) -> None:
    cube = RubikCube3D()
    targets = CubeMoveExtended.targets_for_base(cube, move)
    assert len(targets) == expected_count


def test_rubik_core_adjust_indices_after_single_move() -> None:
    cube = RubikCube3D()
    cube.set_indices()
    targets = np.array(CubeMoveExtended.targets_for_base(cube, "R"), dtype=object)
    VGroup(*targets).rotate(PI / 2, Y_AXIS)
    cube.adjust_indices(targets)
    _assert_cubies_match_indices(cube, targets)


def test_rubik_core_adjust_indices_after_two_same_axis_layers() -> None:
    cube = RubikCube3D()
    cube.set_indices()
    targets_u = np.array(CubeMoveExtended.targets_for_base(cube, "U"), dtype=object)
    targets_d = np.array(CubeMoveExtended.targets_for_base(cube, "D"), dtype=object)
    VGroup(*targets_u).rotate(PI / 2, Z_AXIS)
    VGroup(*targets_d).rotate(-PI / 2, Z_AXIS)
    cube.adjust_indices(targets_u)
    cube.adjust_indices(targets_d)
    _assert_cubies_match_indices(cube, targets_u)
    _assert_cubies_match_indices(cube, targets_d)
