from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RENDERER_FILE = REPO_ROOT / "apps" / "trainer" / "modules" / "renderer" / "baseline-three-renderer.js"
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
    renderer_text = RENDERER_FILE.read_text(encoding="utf-8")
    sandbox_text = SANDBOX_FILE.read_text(encoding="utf-8")
    for token in FORBIDDEN_RENDERER_TOKENS:
        assert token not in renderer_text
        assert token not in sandbox_text
