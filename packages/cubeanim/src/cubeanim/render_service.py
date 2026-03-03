from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from cubeanim.models import RenderGroup
from cubeanim.render_base import (
    BaseRenderer,
    ManimRenderer,
    QUALITY_TO_MANIM_FLAG,
    normalize_group as _normalize_group,
    normalize_quality as _normalize_quality_value,
)
from cubeanim.utils import slugify_formula

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


def normalize_group(raw_group: str | RenderGroup | None) -> str:
    return _normalize_group(raw_group)


def _normalize_quality(raw_quality: str) -> str:
    return _normalize_quality_value(raw_quality)


def _quality_folders(quality: str) -> tuple[str, ...]:
    manim_quality = QUALITY_TO_MANIM_FLAG[quality]
    if manim_quality == quality:
        return (quality,)
    return (quality, manim_quality)


def _canonical_record_quality(raw_quality: str | None) -> str | None:
    if raw_quality is None:
        return None
    try:
        return _normalize_quality(str(raw_quality))
    except ValueError:
        return None


def _normalize_formula(formula: str) -> str:
    return " ".join(formula.split())


def _catalog_path(repo_root: Path) -> Path:
    return repo_root / "media" / "videos" / "render_catalog.json"


def _load_catalog(repo_root: Path) -> dict:
    path = _catalog_path(repo_root)
    if not path.exists():
        return {"version": 1, "records": []}

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if "records" not in data or not isinstance(data["records"], list):
        return {"version": 1, "records": []}

    return data


def _save_catalog(repo_root: Path, data: dict) -> None:
    path = _catalog_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=True, indent=2)


def _find_record(records: list[dict], group: str, quality: str, output_name: str) -> dict | None:
    for record in reversed(records):
        record_quality = _canonical_record_quality(record.get("quality"))
        if (
            record.get("group") == group
            and record_quality == quality
            and record.get("output_name") == output_name
        ):
            return record
    return None


def _next_alternative_name(
    base_name: str,
    group: str,
    quality: str,
    repo_root: Path,
    records: list[dict],
) -> str:
    used = {
        record.get("output_name")
        for record in records
        if record.get("group") == group
        and _canonical_record_quality(record.get("quality")) == quality
    }

    for folder in _quality_folders(quality):
        media_dir = repo_root / "media" / "videos" / group / folder
        if media_dir.exists():
            for mp4 in media_dir.glob("*.mp4"):
                used.add(mp4.stem)

    index = 1
    while True:
        candidate = f"{base_name}__alt{index}"
        if candidate not in used:
            return candidate
        index += 1


def _build_final_path(repo_root: Path, group: str, quality: str, output_name: str) -> Path:
    return repo_root / "media" / "videos" / group / quality / f"{output_name}.mp4"


def _find_existing_video_paths(
    repo_root: Path,
    group: str,
    quality: str,
    output_name: str,
) -> list[Path]:
    paths: list[Path] = []
    for folder in _quality_folders(quality):
        candidate = _build_final_path(repo_root, group, folder, output_name)
        if candidate.exists():
            paths.append(candidate)
    return paths


def plan_formula_render(request: RenderRequest, repo_root: Path) -> RenderPlan:
    formula = _normalize_formula(request.formula)
    if not formula:
        raise ValueError("Formula must be non-empty")

    if request.repeat < 1:
        raise ValueError("repeat must be >= 1")

    group = normalize_group(request.group)
    quality = _normalize_quality(request.quality)
    base_name = request.name.strip() if request.name else ""
    if not base_name:
        base_name = slugify_formula(formula)

    catalog = _load_catalog(repo_root)
    records = catalog["records"]

    final_path = _build_final_path(repo_root, group, quality, base_name)
    record = _find_record(records, group, quality, base_name)

    existing_paths = _find_existing_video_paths(
        repo_root=repo_root,
        group=group,
        quality=quality,
        output_name=base_name,
    )

    if not existing_paths:
        return RenderPlan(
            action="render",
            output_name=base_name,
            final_path=final_path,
            reason="No existing render for this name/group/quality",
        )

    if record is None:
        return RenderPlan(
            action="confirm_rerender",
            output_name=base_name,
            final_path=final_path,
            reason="Render file exists but metadata is missing; confirm overwrite",
        )

    same_formula = (
        record.get("formula") == formula
        and int(record.get("repeat", 1)) == request.repeat
    )

    if same_formula:
        return RenderPlan(
            action="confirm_rerender",
            output_name=base_name,
            final_path=final_path,
            reason="An identical formula already exists",
        )

    alt_name = _next_alternative_name(base_name, group, quality, repo_root, records)
    alt_path = _build_final_path(repo_root, group, quality, alt_name)
    return RenderPlan(
        action="render_alternative",
        output_name=alt_name,
        final_path=alt_path,
        reason="Same name exists with different or unknown formula; saving as alternative",
    )


def _build_manim_command(
    request: RenderRequest,
    repo_root: Path,
    output_name: str,
    media_dir: Path,
) -> tuple[list[str], dict[str, str]]:
    renderer = ManimRenderer()
    return renderer.build_command(request, repo_root, output_name, media_dir)


def _move_rendered_video(temp_media_dir: Path, output_name: str, final_path: Path) -> Path:
    candidates = list(temp_media_dir.rglob(f"{output_name}.mp4"))
    if not candidates:
        raise FileNotFoundError(f"Could not find rendered file for output '{output_name}'")

    source = candidates[0]
    final_path.parent.mkdir(parents=True, exist_ok=True)

    if final_path.exists():
        final_path.unlink()

    shutil.move(str(source), str(final_path))
    return final_path


def _upsert_record(
    repo_root: Path,
    request: RenderRequest,
    output_name: str,
    final_path: Path,
    action: RenderAction,
) -> None:
    catalog = _load_catalog(repo_root)
    records = catalog["records"]

    group = normalize_group(request.group)
    quality = _normalize_quality(request.quality)
    formula = _normalize_formula(request.formula)

    record = {
        "group": group,
        "quality": quality,
        "output_name": output_name,
        "display_name": request.display_name.strip() if request.display_name else output_name,
        "formula": formula,
        "repeat": request.repeat,
        "path": str(final_path.relative_to(repo_root)),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "action": action,
    }

    replaced = False
    for index, existing in enumerate(records):
        existing_quality = _canonical_record_quality(existing.get("quality"))
        if (
            existing.get("group") == group
            and existing_quality == quality
            and existing.get("output_name") == output_name
        ):
            records[index] = record
            replaced = True
            break

    if not replaced:
        records.append(record)

    _save_catalog(repo_root, catalog)


def render_formula(
    request: RenderRequest,
    repo_root: Path,
    allow_rerender: bool = False,
    renderer: BaseRenderer | None = None,
) -> RenderResult:
    plan = plan_formula_render(request, repo_root)

    if plan.action == "confirm_rerender" and not allow_rerender:
        raise RuntimeError(
            "Render already exists for identical formula. "
            "Set allow_rerender=True to overwrite."
        )

    output_name = plan.output_name
    active_renderer = renderer or ManimRenderer()

    with tempfile.TemporaryDirectory(prefix="cubeanim_render_") as tmp_dir:
        temp_media_dir = Path(tmp_dir)
        cmd, env = active_renderer.build_command(request, repo_root, output_name, temp_media_dir)
        active_renderer.run(cmd, cwd=repo_root, env=env)

        final_path = _move_rendered_video(temp_media_dir, output_name, plan.final_path)

    _upsert_record(repo_root, request, output_name, final_path, plan.action)

    return RenderResult(
        output_name=output_name,
        final_path=final_path,
        action=plan.action,
    )
