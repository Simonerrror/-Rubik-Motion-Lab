from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TRAINER_ROOT = REPO_ROOT / "apps" / "trainer"
PREVIEW_DIR = TRAINER_ROOT / "assets" / "previews"
INDEX_HTML = TRAINER_ROOT / "index.html"
BASELINE_RENDERER = TRAINER_ROOT / "modules" / "renderer" / "baseline-three-renderer.js"
INSTANCED_RENDERER = TRAINER_ROOT / "modules" / "renderer" / "instanced-three-renderer.js"
PREVIEW_RENDERER = TRAINER_ROOT / "preview-renderer.js"
PREVIEW_TOOL = REPO_ROOT / "tools" / "trainer" / "render_trainer_previews.py"


def test_baked_preview_assets_exist_for_all_groups() -> None:
    for group in ("f2l", "oll", "pll"):
        path = PREVIEW_DIR / f"trainer-preview-{group}.png"
        assert path.exists(), f"Missing preview asset: {path}"
        assert path.stat().st_size > 1024, f"Preview asset is unexpectedly small: {path}"


def test_runtime_and_preview_renderer_share_visual_config_source() -> None:
    baseline_text = BASELINE_RENDERER.read_text(encoding="utf-8")
    instanced_text = INSTANCED_RENDERER.read_text(encoding="utf-8")
    preview_text = PREVIEW_RENDERER.read_text(encoding="utf-8")

    assert "./visual-config.js" in baseline_text
    assert "./visual-config.js" in instanced_text
    assert "modules/renderer/visual-config.js" in preview_text


def test_index_html_lazy_loads_runtime_scripts() -> None:
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    assert "./vendor/three.min.js" not in html_text
    assert "./sandbox3d.js" not in html_text
    assert "./app.js" in html_text


def test_index_html_static_tabs_include_zbls_pilot_category() -> None:
    html_text = INDEX_HTML.read_text(encoding="utf-8")
    assert 'data-testid="tab-zbls"' in html_text


def test_preview_tool_targets_preview_renderer_page() -> None:
    tool_text = PREVIEW_TOOL.read_text(encoding="utf-8")
    assert "preview-renderer.html" in tool_text
    assert "trainer-preview-" in tool_text
