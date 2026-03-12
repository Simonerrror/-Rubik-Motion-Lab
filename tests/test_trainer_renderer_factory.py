from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FACTORY_JS = REPO_ROOT / "apps" / "trainer" / "modules" / "renderer" / "factory.js"


def test_renderer_factory_switches_to_instanced_for_4x4_and_5x5() -> None:
    script = f"""
const mod = await import('file://{FACTORY_JS}');
const result = [3, 4, 5].map((size) => [size, mod.pickRendererBackend(size)]);
process.stdout.write(JSON.stringify(result));
"""
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        text=True,
        capture_output=True,
        check=True,
        cwd=REPO_ROOT,
    )
    assert json.loads(completed.stdout) == [[3, "baseline"], [4, "instanced"], [5, "instanced"]]
