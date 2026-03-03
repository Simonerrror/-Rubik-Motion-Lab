#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

def _repo_root_from_file() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "db" / "cards" / "schema.sql").exists():
            return parent
    raise RuntimeError("Could not resolve repository root for tools/render_algo.py")


REPO_ROOT = _repo_root_from_file()
PACKAGE_SRC = REPO_ROOT / "packages" / "cubeanim" / "src"
for entry in (REPO_ROOT, PACKAGE_SRC):
    token = str(entry)
    if token not in sys.path:
        sys.path.insert(0, token)

from cubeanim.models import RenderGroup
from cubeanim.presets import get_preset
from cubeanim.render_service import RenderRequest, render_formula
from cubeanim.utils import slugify_formula


def _normalize_group(raw_group: str | None) -> str:
    if not raw_group:
        return RenderGroup.NO_GROUP.value

    normalized = raw_group.strip().upper()
    for group in RenderGroup:
        if group.value == normalized:
            return group.value
    return RenderGroup.NO_GROUP.value


def _resolve_scene_context(args: argparse.Namespace) -> tuple[str, str, str, dict[str, str]]:
    env: dict[str, str] = {}

    if args.scene:
        preset = get_preset(args.scene)
        scene_name = "Preset"
        output_name = preset.name
        group = _normalize_group(args.group) if args.group else preset.group.value
        env["CUBEANIM_PRESET"] = preset.name
        return scene_name, output_name, group, env

    scene_name = "Formula"
    output_name = args.name or slugify_formula(args.formula)
    group = _normalize_group(args.group)

    env["CUBEANIM_FORMULA"] = args.formula
    env["CUBEANIM_GROUP"] = group
    env["CUBEANIM_NAME"] = output_name
    env["CUBEANIM_REPEAT"] = str(args.repeat)

    return scene_name, output_name, group, env


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render cube algorithm scenes with grouped output naming."
    )

    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--scene", help="Preset scene name (e.g. Sexy, Ua, Ub, Vperm)")
    source_group.add_argument("--formula", help="Raw formula string to render")

    parser.add_argument("--name", help="Output name for --formula mode")
    parser.add_argument("--group", help="Render group: F2L, OLL, PLL, ZBLL, NO_GROUP")
    parser.add_argument("--repeat", type=int, default=1, help="Repeat for --formula mode")
    parser.add_argument(
        "--quality",
        default="draft",
        help="Render quality: draft/standard/high/final (or ql/qm/qh/qk)",
    )
    parser.add_argument("--play", action="store_true", help="Play video after render")
    parser.add_argument("--manim-bin", default="manim", help="Path to manim executable")
    parser.add_argument("--manim-file", default="cubist.py", help="Path to manim scenes file")
    parser.add_argument("--manim-threads", type=int, default=1, help="Thread budget for render subprocess")

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.repeat < 1:
        raise ValueError("--repeat must be >= 1")

    scene_name, output_name, group, extra_env = _resolve_scene_context(args)

    if scene_name == "Preset":
        preset = get_preset(extra_env["CUBEANIM_PRESET"])
        request = RenderRequest(
            formula=preset.formula,
            name=output_name,
            group=group,
            quality=args.quality,
            repeat=preset.repeat,
            play=args.play,
            manim_bin=args.manim_bin,
            manim_file=args.manim_file,
            manim_threads=max(int(args.manim_threads), 1),
        )
    else:
        request = RenderRequest(
            formula=args.formula,
            name=output_name,
            group=group,
            quality=args.quality,
            repeat=args.repeat,
            play=args.play,
            manim_bin=args.manim_bin,
            manim_file=args.manim_file,
            manim_threads=max(int(args.manim_threads), 1),
        )

    result = render_formula(request=request, repo_root=REPO_ROOT, allow_rerender=True)
    print(f"Rendered: {result.final_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
