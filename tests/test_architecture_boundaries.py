from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PRODUCT_FILES = [
    REPO_ROOT / "apps" / "trainer" / "app.js",
    REPO_ROOT / "packages" / "cubeanim" / "src" / "cubeanim" / "cards" / "recognizer.py",
    REPO_ROOT / "packages" / "cubeanim" / "src" / "cubeanim" / "cards" / "sandbox.py",
    REPO_ROOT / "tools" / "trainer" / "build_trainer_catalog.py",
]
FORBIDDEN_TOKENS = [
    "cubeanim.render_service",
    "cubeanim_renderer",
    "cubeanim.scenes",
    "cubeanim.executor",
    "cubeanim.rubik_core",
    "from manim import",
]


def test_product_files_do_not_directly_import_renderer_or_manim() -> None:
    for path in PRODUCT_FILES:
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_TOKENS:
            assert token not in text, f"{path} must not import {token}"
