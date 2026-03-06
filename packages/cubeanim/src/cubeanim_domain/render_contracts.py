from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from cubeanim_domain.models import RenderGroup

RenderAction = Literal["render", "confirm_rerender", "render_alternative"]


@dataclass(frozen=True)
class RenderRequest:
    formula: str
    name: str | None = None
    display_name: str | None = None
    group: str | RenderGroup = RenderGroup.NO_GROUP
    quality: str = "draft"
    repeat: int = 1
    play: bool = False
    manim_bin: str = "manim"
    manim_file: str = "cubist.py"
    manim_threads: int | None = None


@dataclass(frozen=True)
class RenderPlan:
    action: RenderAction
    output_name: str
    final_path: Path
    reason: str


@dataclass(frozen=True)
class RenderResult:
    output_name: str
    final_path: Path
    action: RenderAction
