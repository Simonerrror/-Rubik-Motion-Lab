from __future__ import annotations

import numpy as np
from manim import BLACK, DOWN, IN, LEFT, OUT, RIGHT, UP, Square
from manim.mobject.types.vectorized_mobject import VGroup
from manim.utils.space_ops import z_to_vector


def _faces_for_position(dim: int, position: tuple[int, int, int]) -> list[np.ndarray]:
    max_index = dim - 1
    x, y, z = position

    corners = {
        (0, 0, 0): [LEFT, DOWN, IN],
        (0, 0, max_index): [LEFT, DOWN, OUT],
        (0, max_index, 0): [LEFT, UP, IN],
        (0, max_index, max_index): [LEFT, UP, OUT],
        (max_index, 0, 0): [RIGHT, DOWN, IN],
        (max_index, 0, max_index): [RIGHT, DOWN, OUT],
        (max_index, max_index, 0): [RIGHT, UP, IN],
        (max_index, max_index, max_index): [RIGHT, UP, OUT],
    }
    corner = corners.get(position)
    if corner is not None:
        return corner

    if x == 0:
        if y == 0:
            return [DOWN, LEFT]
        if y == max_index:
            return [UP, LEFT]
        if z == 0:
            return [IN, LEFT]
        if z == max_index:
            return [OUT, LEFT]
        return [LEFT]

    if x == max_index:
        if y == 0:
            return [DOWN, RIGHT]
        if y == max_index:
            return [UP, RIGHT]
        if z == 0:
            return [IN, RIGHT]
        if z == max_index:
            return [OUT, RIGHT]
        return [RIGHT]

    if y == 0:
        if z == 0:
            return [IN, DOWN]
        if z == max_index:
            return [OUT, DOWN]
        return [DOWN]

    if y == max_index:
        if z == 0:
            return [IN, UP]
        if z == max_index:
            return [OUT, UP]
        return [UP]

    if z == 0:
        return [IN]
    if z == max_index:
        return [OUT]
    return []


class Cubie(VGroup):
    def __init__(self, x: int, y: int, z: int, dim: int, colors: list[str]):
        self.dimensions = dim
        self.colors = colors
        self.position = np.array([x, y, z])
        self.faces: dict[tuple[float, float, float], Square] = {}
        super().__init__()

    def get_position(self) -> np.ndarray:
        return self.position

    def get_rounded_center(self) -> tuple[float, float, float]:
        return (round(self.get_x(), 3), round(self.get_y(), 3), round(self.get_z(), 3))

    def generate_points(self) -> None:
        visible_faces = np.array(_faces_for_position(self.dimensions, tuple(self.position))).tolist()
        color_index = 0
        for vector in (OUT, DOWN, LEFT, IN, UP, RIGHT):
            face = Square(side_length=2, shade_in_3d=True, stroke_width=3)
            if vector.tolist() in visible_faces:
                face.set_fill(self.colors[color_index], 1)
            else:
                face.set_fill(BLACK, 1)

            face.flip()
            face.shift(OUT)
            face.apply_matrix(z_to_vector(vector))

            key = tuple(float(v) for v in vector.tolist())
            self.faces[key] = face
            self.add(face)
            color_index += 1

    def get_face(self, face: str) -> Square:
        if face == "F":
            return self.faces[tuple(LEFT.tolist())]
        if face == "B":
            return self.faces[tuple(RIGHT.tolist())]
        if face == "R":
            return self.faces[tuple(DOWN.tolist())]
        if face == "L":
            return self.faces[tuple(UP.tolist())]
        if face == "U":
            return self.faces[tuple(OUT.tolist())]
        if face == "D":
            return self.faces[tuple(IN.tolist())]
        raise ValueError(f"Unsupported face: {face}")

    def init_colors(self) -> None:
        self.set_fill(
            color=self.fill_color or self.color,
            opacity=self.fill_opacity,
            family=False,
        )
        self.set_stroke(
            color=self.stroke_color or self.color,
            width=self.stroke_width,
            opacity=self.stroke_opacity,
            family=False,
        )
        self.set_background_stroke(
            color=self.background_stroke_color,
            width=self.background_stroke_width,
            opacity=self.background_stroke_opacity,
            family=False,
        )
