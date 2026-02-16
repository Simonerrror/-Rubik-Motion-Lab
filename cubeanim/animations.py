from __future__ import annotations

import numpy as np
from manim import Animation, PI, VGroup, X_AXIS, Y_AXIS, Z_AXIS
from manim_rubikscube import RubiksCube


def _split_move_modifier(move: str) -> tuple[str, str]:
    if move.endswith("2"):
        return move[:-1], "2"
    if move.endswith("'"):
        return move[:-1], "'"
    return move, ""


class CubeMoveExtended(Animation):
    """Move animation that supports faces, slices, wide moves and rotations."""

    def __init__(self, mobject: RubiksCube, move: str, **kwargs):
        self.move = move
        self.base, self.modifier = _split_move_modifier(move)
        self.axis = self._axis_for_base(self.base)
        self.angle = self._angle_for_base(self.base, self.modifier)
        super().__init__(mobject, **kwargs)

    @staticmethod
    def _axis_for_base(base: str):
        if base in ("F", "B", "S", "f", "b", "z"):
            return X_AXIS
        if base in ("U", "D", "E", "u", "d", "y"):
            return Z_AXIS
        if base in ("L", "R", "M", "l", "r", "x"):
            return Y_AXIS
        raise ValueError(f"Unsupported move base: {base}")

    @staticmethod
    def _angle_for_base(base: str, modifier: str) -> float:
        positive_bases = {"R", "F", "D", "E", "S", "r", "f", "d", "x", "z"}
        angle = PI / 2 if base in positive_bases else -PI / 2

        if modifier == "2":
            angle *= 2
        if modifier == "'":
            angle *= -1
        return angle

    def _mid_index(self) -> int:
        dim = self.mobject.dimensions
        if dim % 2 == 0:
            raise ValueError("Slice and wide moves require odd cube dimension")
        return dim // 2

    def _targets(self):
        return self.targets_for_base(self.mobject, self.base)

    @staticmethod
    def targets_for_base(cube: RubiksCube, base: str):
        dim = cube.dimensions
        mid = dim // 2

        if base == "F":
            return cube.cubies[0, :, :].flatten()
        if base == "B":
            return cube.cubies[dim - 1, :, :].flatten()
        if base == "U":
            return cube.cubies[:, :, dim - 1].flatten()
        if base == "D":
            return cube.cubies[:, :, 0].flatten()
        if base == "L":
            return cube.cubies[:, dim - 1, :].flatten()
        if base == "R":
            return cube.cubies[:, 0, :].flatten()

        if base == "M":
            return cube.cubies[:, mid, :].flatten()
        if base == "E":
            return cube.cubies[:, :, mid].flatten()
        if base == "S":
            return cube.cubies[mid, :, :].flatten()

        if base == "f":
            return np.concatenate((cube.cubies[0, :, :].flatten(), cube.cubies[mid, :, :].flatten()))
        if base == "b":
            return np.concatenate((cube.cubies[dim - 1, :, :].flatten(), cube.cubies[mid, :, :].flatten()))
        if base == "u":
            return np.concatenate((cube.cubies[:, :, dim - 1].flatten(), cube.cubies[:, :, mid].flatten()))
        if base == "d":
            return np.concatenate((cube.cubies[:, :, 0].flatten(), cube.cubies[:, :, mid].flatten()))
        if base == "l":
            return np.concatenate((cube.cubies[:, dim - 1, :].flatten(), cube.cubies[:, mid, :].flatten()))
        if base == "r":
            return np.concatenate((cube.cubies[:, 0, :].flatten(), cube.cubies[:, mid, :].flatten()))

        if base in ("x", "y", "z"):
            return cube.cubies.flatten()

        raise ValueError(f"Unsupported move base: {base}")

    def create_starting_mobject(self):
        starting_mobject = self.mobject.copy()
        if starting_mobject.indices == {}:
            starting_mobject.set_indices()
        return starting_mobject

    def interpolate_mobject(self, alpha):
        self.mobject.become(self.starting_mobject)
        VGroup(*self._targets()).rotate(alpha * self.angle, self.axis)

    def finish(self):
        super().finish()
        self.mobject.adjust_indices(np.array(self._targets(), dtype=object))


class CubeMoveConcurrent(Animation):
    """Runs multiple compatible moves as one animation beat."""

    def __init__(self, mobject: RubiksCube, moves: list[str], **kwargs):
        if len(moves) < 2:
            raise ValueError("CubeMoveConcurrent requires at least two moves")

        self.moves = moves
        self._descriptors: list[tuple[str, np.ndarray, float]] = []
        axis_signatures = set()

        for move in moves:
            base, modifier = _split_move_modifier(move)
            axis = CubeMoveExtended._axis_for_base(base)
            angle = CubeMoveExtended._angle_for_base(base, modifier)
            axis_signatures.add(tuple(axis.tolist()))
            self._descriptors.append((base, axis, angle))

        if len(axis_signatures) != 1:
            raise ValueError(
                "Simultaneous moves must rotate around the same axis "
                f"(got: {moves})"
            )

        super().__init__(mobject, **kwargs)

    def create_starting_mobject(self):
        starting_mobject = self.mobject.copy()
        if starting_mobject.indices == {}:
            starting_mobject.set_indices()
        return starting_mobject

    def _targets_for(self, base: str):
        return CubeMoveExtended.targets_for_base(self.mobject, base)

    def interpolate_mobject(self, alpha):
        self.mobject.become(self.starting_mobject)
        for base, axis, angle in self._descriptors:
            VGroup(*self._targets_for(base)).rotate(alpha * angle, axis)

    def finish(self):
        super().finish()
        for base, _, _ in self._descriptors:
            self.mobject.adjust_indices(np.array(self._targets_for(base), dtype=object))
