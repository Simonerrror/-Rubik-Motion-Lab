from __future__ import annotations

import json
import subprocess
from pathlib import Path

from cubeanim_domain.state import state_slots_metadata


FIXTURES_PATH = Path(__file__).parent / "fixtures" / "domain" / "formula_golden.json"
REPO_ROOT = Path(__file__).resolve().parents[1]
FORMULA_JS = REPO_ROOT / "apps" / "trainer" / "modules" / "domain" / "formula.js"
TIMELINE_JS = REPO_ROOT / "apps" / "trainer" / "modules" / "domain" / "timeline-builder.js"


def test_trainer_js_matches_domain_golden_fixtures() -> None:
    fixtures = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    state_slots = [
        {"position": [x, y, z], "face": face}
        for (x, y, z), face in state_slots_metadata()
    ]
    payload = json.dumps({"fixtures": fixtures, "state_slots": state_slots})

    script = f"""
import fs from 'node:fs';
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
const formulaMod = await import('file://{FORMULA_JS}');
const timelineMod = await import('file://{TIMELINE_JS}');
const result = payload.fixtures.map((fixture) => {{
  const normalized = formulaMod.normalizeMoveSteps(fixture.formula);
  const timeline = timelineMod.buildLocalSandboxTimeline({{
    initial_state: fixture.initial_state,
    state_slots: payload.state_slots,
    playback_config: {{}}
  }}, fixture.formula, fixture.group);
  return {{
    formula: normalized.formula,
    move_steps: normalized.steps,
    moves_flat: normalized.movesFlat,
    highlight_by_step: normalized.highlights,
    states_by_step: timeline.states_by_step,
  }};
}});
process.stdout.write(JSON.stringify(result));
"""

    completed = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        input=payload,
        text=True,
        capture_output=True,
        check=True,
        cwd=REPO_ROOT,
    )
    js_results = json.loads(completed.stdout)
    assert len(js_results) == len(fixtures)

    for fixture, actual in zip(fixtures, js_results, strict=True):
        assert actual["formula"] == fixture["normalized_formula"]
        assert actual["move_steps"] == fixture["move_steps"]
        assert actual["moves_flat"] == fixture["moves_flat"]
        assert actual["highlight_by_step"] == fixture["highlight_by_step"]
        has_cube_rotations = any(move[:1] in {"x", "y", "z"} for move in fixture["moves_flat"])
        if not has_cube_rotations:
            assert actual["states_by_step"] == fixture["states_by_step"]
        else:
            assert len(actual["states_by_step"]) == len(fixture["states_by_step"])
            assert all(len(state) == 54 for state in actual["states_by_step"])
