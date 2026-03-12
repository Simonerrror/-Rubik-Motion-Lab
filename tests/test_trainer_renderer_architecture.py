from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RENDERER_FILES = [
    REPO_ROOT / "apps" / "trainer" / "modules" / "renderer" / "baseline-three-renderer.js",
    REPO_ROOT / "apps" / "trainer" / "modules" / "renderer" / "instanced-three-renderer.js",
]
SANDBOX_FILE = REPO_ROOT / "apps" / "trainer" / "sandbox3d.js"


FORBIDDEN_RENDERER_TOKENS = [
    "splitMove",
    "moveAxis",
    "moveTurns",
    "parseFormulaSteps",
    "normalizeMoveSteps",
    "buildLocalSandboxTimeline",
    "collectMoveParts",
]


def test_renderer_adapter_has_no_formula_or_timeline_math() -> None:
    sandbox_text = SANDBOX_FILE.read_text(encoding="utf-8")
    for renderer_file in RENDERER_FILES:
        renderer_text = renderer_file.read_text(encoding="utf-8")
        for token in FORBIDDEN_RENDERER_TOKENS:
            assert token not in renderer_text
    for token in FORBIDDEN_RENDERER_TOKENS:
        assert token not in sandbox_text


def test_instanced_renderer_keeps_instanced_path_for_bodies_and_stickers() -> None:
    instanced_text = (
        REPO_ROOT
        / "apps"
        / "trainer"
        / "modules"
        / "renderer"
        / "instanced-three-renderer.js"
    ).read_text(encoding="utf-8")
    assert instanced_text.count("new THREE.InstancedMesh") >= 2
    assert "new THREE.Mesh(stickerGeometry" not in instanced_text
