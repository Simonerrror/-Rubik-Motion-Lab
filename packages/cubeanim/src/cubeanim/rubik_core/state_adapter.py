from __future__ import annotations

import numpy as np


def apply_state_to_cube(cube, state: str) -> None:
    colors = {
        "U": cube.colors[0],
        "R": cube.colors[1],
        "F": cube.colors[2],
        "D": cube.colors[3],
        "L": cube.colors[4],
        "B": cube.colors[5],
    }
    positions = list(state)

    for cubie in np.rot90(cube.get_face("U", flatten=False), 2).flatten():
        cubie.get_face("U").set_fill(colors[positions.pop(0)], 1)

    for cubie in np.rot90(np.flip(cube.get_face("R", flatten=False), (0, 1)), -1).flatten():
        cubie.get_face("R").set_fill(colors[positions.pop(0)], 1)

    for cubie in np.rot90(np.flip(cube.get_face("F", flatten=False), 0)).flatten():
        cubie.get_face("F").set_fill(colors[positions.pop(0)], 1)

    for cubie in np.rot90(np.flip(cube.get_face("D", flatten=False), 0), 2).flatten():
        cubie.get_face("D").set_fill(colors[positions.pop(0)], 1)

    for cubie in np.rot90(np.flip(cube.get_face("L", flatten=False), 0)).flatten():
        cubie.get_face("L").set_fill(colors[positions.pop(0)], 1)

    for cubie in np.rot90(np.flip(cube.get_face("B", flatten=False), (0, 1)), -1).flatten():
        cubie.get_face("B").set_fill(colors[positions.pop(0)], 1)
