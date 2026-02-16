from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from manim import DEGREES, ORIGIN, RIGHT, ThreeDScene, Z_AXIS
from manim_rubikscube import RubiksCube


@dataclass(frozen=True)
class CubeVisualConfig:
    colors: Sequence[str] = (
        "#E8E000",
        "#F43131",
        "#58CC63",
        "#F4F4F4",
        "#F7B126",
        "#2B63E8",
    )
    background_color: str = "#D4D4D4"
    sticker_stroke_color: str = "#1F2733"
    sticker_stroke_width: float = 3.4
    scale: float = 0.9
    start_rotation: float = 0.0
    camera_phi_deg: float = 60.0
    camera_theta_deg: float = 225.0
    camera_zoom: float = 0.75
    camera_frame_shift_right: float = 0.0


class SceneSetup:
    @staticmethod
    def apply(scene: ThreeDScene, config: CubeVisualConfig) -> RubiksCube:
        scene.camera.background_color = config.background_color

        cube = RubiksCube(colors=list(config.colors)).scale(config.scale)
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
