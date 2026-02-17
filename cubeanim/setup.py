from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from manim import DEGREES, ORIGIN, RIGHT, ThreeDScene, Z_AXIS
from manim_rubikscube import RubiksCube

from cubeanim.palette import CONTRAST_SAFE_CUBE_COLORS, validate_cube_palette


@dataclass(frozen=True)
class CubeVisualConfig:
    colors: Sequence[str] = CONTRAST_SAFE_CUBE_COLORS
    background_color: str = "#D4D4D4"
    sticker_stroke_color: str = "#1F2733"
    sticker_stroke_width: float = 3.4
    sticker_sheen_factor: float = 0.08
    sticker_gloss: float = 0.06
    sticker_shadow: float = 0.25
    internal_face_color: str = "#242B35"
    scale: float = 0.9
    # Keep cube notation aligned with visible faces; do not rotate cube itself.
    start_rotation: float = 0.0
    camera_phi_deg: float = 60.0
    # Equivalent view to previous setup, but without remapping R/L/F/B indices.
    camera_theta_deg: float = 213.0
    # Approx "step back by one cubie" for a 3x3 view.
    camera_zoom: float = 0.70
    camera_frame_shift_right: float = 0.0


class SceneSetup:
    @staticmethod
    def _soften_internal_faces(cube: RubiksCube, internal_face_color: str) -> None:
        for cubie in cube.cubies.flatten():
            for face in cubie.faces.values():
                if face.get_fill_color().to_hex().lower() == "#000000":
                    face.set_fill(internal_face_color, opacity=1.0)

    @staticmethod
    def _apply_sticker_finish(
        cube: RubiksCube,
        sheen_factor: float,
        gloss: float,
        shadow: float,
    ) -> None:
        for cubie in cube.cubies.flatten():
            for face in cubie.faces.values():
                face.set_sheen(sheen_factor)
                face.set_gloss(gloss)
                face.set_shadow(shadow)

    @staticmethod
    def apply(scene: ThreeDScene, config: CubeVisualConfig) -> RubiksCube:
        scene.camera.background_color = config.background_color

        validate_cube_palette(config.colors)
        cube = RubiksCube(colors=list(config.colors)).scale(config.scale)
        SceneSetup._soften_internal_faces(cube, config.internal_face_color)
        SceneSetup._apply_sticker_finish(
            cube,
            sheen_factor=config.sticker_sheen_factor,
            gloss=config.sticker_gloss,
            shadow=config.sticker_shadow,
        )
        cube.move_to(ORIGIN)
        cube.rotate(config.start_rotation, axis=Z_AXIS)
        cube.set_stroke(color=config.sticker_stroke_color, width=config.sticker_stroke_width)

        scene.set_camera_orientation(
            phi=config.camera_phi_deg * DEGREES,
            theta=config.camera_theta_deg * DEGREES,
            zoom=config.camera_zoom,
        )
        scene.renderer.camera.frame_center = ORIGIN + RIGHT * config.camera_frame_shift_right

        return cube
