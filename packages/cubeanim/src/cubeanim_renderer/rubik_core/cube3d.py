from __future__ import annotations

import numpy as np
from manim import Mobject, VMobject, WHITE

from .cubie import Cubie
from .state_adapter import apply_state_to_cube


class RubikCube3D(VMobject):
    cubies = np.ndarray
    indices: dict[tuple[float, float, float], np.ndarray]

    def __init__(
        self,
        dim: int = 3,
        colors: tuple[str, str, str, str, str, str] = (
            WHITE,
            "#B90000",
            "#009B48",
            "#FFD500",
            "#FF5900",
            "#0045AD",
        ),
        x_offset: float = 2.1,
        y_offset: float = 2.1,
        z_offset: float = 2.1,
    ):
        if dim < 2:
            raise ValueError("Dimension must be >= 2")
        super().__init__()
        self.dimensions = dim
        self.colors = list(colors)
        self.indices = {}
        self.x_offset = [[Mobject.shift, [x_offset, 0, 0]]]
        self.y_offset = [[Mobject.shift, [0, y_offset, 0]]]
        self.z_offset = [[Mobject.shift, [0, 0, z_offset]]]
        self.cubies = np.ndarray((dim, dim, dim), dtype=object)
        self.generate_cubies()

    def generate_cubies(self) -> None:
        for x in range(self.dimensions):
            for y in range(self.dimensions):
                for z in range(self.dimensions):
                    cubie = Cubie(x, y, z, self.dimensions, self.colors)
                    self.transform_cubie(x, self.x_offset, cubie)
                    self.transform_cubie(y, self.y_offset, cubie)
                    self.transform_cubie(z, self.z_offset, cubie)
                    self.add(cubie)
                    self.cubies[x, y, z] = cubie

    def set_state(self, state: str) -> None:
        apply_state_to_cube(self, state)

    def transform_cubie(self, position: int, offsets, cubie: Cubie) -> None:
        offsets_nr = len(offsets)
        for i in range(offsets_nr):
            for j in range(int(len(offsets[i]) / 2)):
                if position < 0:
                    magnitude = len(range(-i, position, -offsets_nr)) * -1
                    offsets[-1 - i][0 + j * 2](cubie, magnitude * np.array(offsets[-1 - i][1 + j * 2]))
                else:
                    magnitude = len(range(i, position, offsets_nr))
                    offsets[i][0 + j * 2](cubie, magnitude * np.array(offsets[i][1 + j * 2]))

    def get_face(self, face: str, flatten: bool = True):
        if face == "F":
            face_data = self.cubies[0, :, :]
        elif face == "B":
            face_data = self.cubies[self.dimensions - 1, :, :]
        elif face == "U":
            face_data = self.cubies[:, :, self.dimensions - 1]
        elif face == "D":
            face_data = self.cubies[:, :, 0]
        elif face == "L":
            face_data = self.cubies[:, self.dimensions - 1, :]
        elif face == "R":
            face_data = self.cubies[:, 0, :]
        else:
            raise ValueError(f"Unsupported face: {face}")

        return face_data.flatten() if flatten else face_data

    def set_indices(self) -> None:
        self.indices = {}
        for cubie in self.cubies.flatten():
            self.indices[cubie.get_rounded_center()] = cubie.position

    def adjust_indices(self, cubies: np.ndarray) -> None:
        for cubie in cubies.flatten():
            loc = self.indices[cubie.get_rounded_center()]
            self.cubies[loc[0], loc[1], loc[2]] = cubie
