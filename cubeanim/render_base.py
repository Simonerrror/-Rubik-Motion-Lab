from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Mapping

from cubeanim.models import RenderGroup

if TYPE_CHECKING:
    from cubeanim.render_service import RenderRequest

QUALITY_ALIASES = {
    "ql": "draft",
    "draft": "draft",
    "fast": "draft",
    "low": "draft",
    "qm": "standard",
    "standard": "standard",
    "normal": "standard",
    "medium": "standard",
    "qh": "high",
    "high": "high",
    "hq": "high",
    "qk": "final",
    "final": "final",
    "ultra": "final",
    "production": "final",
}

QUALITY_TO_MANIM_FLAG = {
    "draft": "ql",
    "standard": "qm",
    "high": "qh",
    "final": "qk",
}


def normalize_group(raw_group: str | RenderGroup | None) -> str:
    if raw_group is None:
        return RenderGroup.NO_GROUP.value

    if isinstance(raw_group, RenderGroup):
        return raw_group.value

    normalized = raw_group.strip().upper()
    for group in RenderGroup:
        if group.value == normalized:
            return group.value
    return RenderGroup.NO_GROUP.value


def normalize_quality(raw_quality: str) -> str:
    quality = raw_quality.strip().lower()
    normalized = QUALITY_ALIASES.get(quality)
    if normalized is None:
        raise ValueError(
            "quality must be one of: draft/standard/high/final (or ql/qm/qh/qk)"
        )
    return normalized


def normalize_formula(formula: str) -> str:
    return " ".join(formula.split())


class BaseRenderer(ABC):
    @abstractmethod
    def build_command(
        self,
        request: RenderRequest,
        repo_root: Path,
        output_name: str,
        media_dir: Path,
    ) -> tuple[list[str], dict[str, str]]:
        raise NotImplementedError

    def run(self, cmd: list[str], *, cwd: Path, env: Mapping[str, str]) -> None:
        subprocess.run(cmd, check=True, cwd=cwd, env=dict(env))


class ManimRenderer(BaseRenderer):
    def build_command(
        self,
        request: RenderRequest,
        repo_root: Path,
        output_name: str,
        media_dir: Path,
    ) -> tuple[list[str], dict[str, str]]:
        manim_file = Path(request.manim_file)
        if not manim_file.is_absolute():
            manim_file = repo_root / manim_file

        if not manim_file.exists():
            raise FileNotFoundError(f"Manim scene file not found: {manim_file}")

        group = normalize_group(request.group)
        quality = normalize_quality(request.quality)
        manim_quality_flag = QUALITY_TO_MANIM_FLAG[quality]

        raw_manim_bin = request.manim_bin.strip() if request.manim_bin else "manim"
        manim_bin_parts = shlex.split(raw_manim_bin) if raw_manim_bin else ["manim"]
        if len(manim_bin_parts) == 1 and manim_bin_parts[0] == "manim":
            # Prefer module execution to avoid broken venv shims after worktree/path moves.
            manim_bin_parts = [sys.executable, "-m", "manim"]
        elif len(manim_bin_parts) == 1 and shutil.which(manim_bin_parts[0]) is None:
            raise FileNotFoundError(f"Manim executable not found: {manim_bin_parts[0]}")

        cmd = [
            *manim_bin_parts,
            f"-{manim_quality_flag}",
            str(manim_file),
            "Formula",
            "--output_file",
            output_name,
            "--media_dir",
            str(media_dir),
        ]

        if request.play:
            cmd.insert(1, "-p")

        env = os.environ.copy()
        env["CUBEANIM_FORMULA"] = normalize_formula(request.formula)
        display_name = request.display_name.strip() if request.display_name else ""
        env["CUBEANIM_NAME"] = display_name or output_name
        env["CUBEANIM_GROUP"] = group
        env["CUBEANIM_REPEAT"] = str(request.repeat)
        if request.manim_threads is not None:
            threads = max(1, int(request.manim_threads))
            for env_key in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            ):
                env[env_key] = str(threads)
            env["CUBEANIM_MANIM_THREADS"] = str(threads)

        return cmd, env
