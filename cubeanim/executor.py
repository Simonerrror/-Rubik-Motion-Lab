from __future__ import annotations

from dataclasses import dataclass

from manim import ThreeDScene
from manim_rubikscube import RubiksCube

from cubeanim.animations import CubeMoveExtended


@dataclass(frozen=True)
class ExecutionConfig:
    run_time: float = 0.55
    end_wait: float = 1.0
    pre_start_wait: float = 0.5


class MoveExecutor:
    @staticmethod
    def play(
        scene: ThreeDScene,
        cube: RubiksCube,
        moves: list[str],
        config: ExecutionConfig,
    ) -> None:
        scene.add(cube)
        scene.wait(config.pre_start_wait)

        for move in moves:
            scene.play(CubeMoveExtended(cube, move), run_time=config.run_time)

        scene.wait(config.end_wait)
