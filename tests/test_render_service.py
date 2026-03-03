from __future__ import annotations

from pathlib import Path

from cubeanim.render_base import BaseRenderer
from cubeanim.render_service import RenderRequest, _build_manim_command, plan_formula_render, render_formula


def test_plan_render_for_new_name(tmp_path: Path) -> None:
    request = RenderRequest(
        formula="R U",
        name="MyAlgo",
        group="PLL",
        quality="ql",
    )

    plan = plan_formula_render(request=request, repo_root=tmp_path)
    assert plan.action == "render"
    assert plan.output_name == "MyAlgo"


def test_plan_confirm_rerender_for_identical_formula(tmp_path: Path) -> None:
    videos_dir = tmp_path / "media" / "videos" / "PLL" / "ql"
    videos_dir.mkdir(parents=True, exist_ok=True)
    (videos_dir / "MyAlgo.mp4").write_bytes(b"fake")

    catalog = tmp_path / "media" / "videos" / "render_catalog.json"
    catalog.write_text(
        '{"version":1,"records":[{"group":"PLL","quality":"ql","output_name":"MyAlgo","formula":"R U","repeat":1}]}',
        encoding="utf-8",
    )

    request = RenderRequest(
        formula="R U",
        name="MyAlgo",
        group="PLL",
        quality="ql",
    )

    plan = plan_formula_render(request=request, repo_root=tmp_path)
    assert plan.action == "confirm_rerender"
    assert plan.output_name == "MyAlgo"


def test_plan_alternative_for_same_name_different_formula(tmp_path: Path) -> None:
    videos_dir = tmp_path / "media" / "videos" / "PLL" / "ql"
    videos_dir.mkdir(parents=True, exist_ok=True)
    (videos_dir / "MyAlgo.mp4").write_bytes(b"fake")

    catalog = tmp_path / "media" / "videos" / "render_catalog.json"
    catalog.write_text(
        '{"version":1,"records":[{"group":"PLL","quality":"ql","output_name":"MyAlgo","formula":"R U","repeat":1}]}',
        encoding="utf-8",
    )

    request = RenderRequest(
        formula="R U2",
        name="MyAlgo",
        group="PLL",
        quality="ql",
    )

    plan = plan_formula_render(request=request, repo_root=tmp_path)
    assert plan.action == "render_alternative"
    assert plan.output_name.startswith("MyAlgo__alt")


def test_plan_confirm_when_file_exists_without_catalog_record(tmp_path: Path) -> None:
    videos_dir = tmp_path / "media" / "videos" / "PLL" / "ql"
    videos_dir.mkdir(parents=True, exist_ok=True)
    (videos_dir / "MyAlgo.mp4").write_bytes(b"fake")

    request = RenderRequest(
        formula="R U",
        name="MyAlgo",
        group="PLL",
        quality="ql",
    )

    plan = plan_formula_render(request=request, repo_root=tmp_path)
    assert plan.action == "confirm_rerender"


def test_quality_alias_standard_maps_to_readable_path(tmp_path: Path) -> None:
    request = RenderRequest(
        formula="R U",
        name="MyAlgo",
        group="PLL",
        quality="standard",
    )

    plan = plan_formula_render(request=request, repo_root=tmp_path)
    assert plan.action == "render"
    assert "/PLL/standard/" in str(plan.final_path)


def test_build_command_uses_display_name_for_overlay(tmp_path: Path) -> None:
    manim_file = tmp_path / "cubist.py"
    manim_file.write_text("from manim import *\n", encoding="utf-8")

    request = RenderRequest(
        formula="R U",
        name="pll_pll_9_hash",
        display_name="Jb-perm",
        group="PLL",
        quality="draft",
        manim_file=str(manim_file),
    )

    cmd, env = _build_manim_command(
        request=request,
        repo_root=tmp_path,
        output_name="pll_pll_9_hash",
        media_dir=tmp_path / "media_tmp",
    )
    assert cmd
    assert env["CUBEANIM_NAME"] == "Jb-perm"


class _StubRenderer(BaseRenderer):
    def __init__(self) -> None:
        self.output_name = ""
        self.media_dir = Path(".")

    def build_command(
        self,
        request: RenderRequest,
        repo_root: Path,
        output_name: str,
        media_dir: Path,
    ) -> tuple[list[str], dict[str, str]]:
        _ = request
        _ = repo_root
        self.output_name = output_name
        self.media_dir = media_dir
        return ["stub-render"], {"STUB": "1"}

    def run(self, cmd: list[str], *, cwd: Path, env: dict[str, str]) -> None:
        _ = cmd
        _ = cwd
        _ = env
        rendered = self.media_dir / "videos" / f"{self.output_name}.mp4"
        rendered.parent.mkdir(parents=True, exist_ok=True)
        rendered.write_bytes(b"fake")


def test_render_formula_supports_custom_renderer(tmp_path: Path) -> None:
    request = RenderRequest(
        formula="R U",
        name="custom_renderer_case",
        group="PLL",
        quality="draft",
    )

    result = render_formula(
        request=request,
        repo_root=tmp_path,
        renderer=_StubRenderer(),
    )
    assert result.output_name == "custom_renderer_case"
    assert result.action == "render"
    assert result.final_path.exists()
