from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_JS = REPO_ROOT / "apps" / "trainer" / "modules" / "cube-core" / "model.js"


def _run_node(script: str, payload: object | None = None) -> object:
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        input=json.dumps(payload) if payload is not None else None,
        text=True,
        capture_output=True,
        check=True,
        cwd=REPO_ROOT,
    )
    return json.loads(completed.stdout)


def test_cube_core_supports_surface_models_up_to_5x5() -> None:
    script = f"""
const core = await import('file://{CORE_JS}');
const sizes = [3, 4, 5];
const result = sizes.map((size) => {{
  const slots = core.createSurfaceStateSlots(size);
  const state = slots.map((slot) => slot.face).join('');
  const model = core.createCubeModel(size, state, slots);
  const snapshot = core.snapshotForState(model);
  return {{
    size,
    slotCount: slots.length,
    cubieCount: snapshot.cubies.length,
  }};
}});
process.stdout.write(JSON.stringify(result));
"""
    result = _run_node(script)
    assert result == [
        {"size": 3, "slotCount": 54, "cubieCount": 26},
        {"size": 4, "slotCount": 96, "cubieCount": 56},
        {"size": 5, "slotCount": 150, "cubieCount": 98},
    ]


def test_cube_core_move_reversibility_holds_for_3_to_5() -> None:
    script = f"""
const core = await import('file://{CORE_JS}');
const scenarios = [
  {{ size: 3, steps: [['R'], ['U'], ["U'"], ["R'"]] }},
  {{ size: 4, steps: [['f'], ['u'], ["u'"], ["f'"]] }},
  {{ size: 5, steps: [['R'], ['u'], ['f'], ["f'"], ["u'"], ["R'"]] }},
];
const result = scenarios.map((scenario) => {{
  const slots = core.createSurfaceStateSlots(scenario.size);
  const solved = slots.map((slot) => slot.face).join('');
  let model = core.createCubeModel(scenario.size, solved, slots);
  scenario.steps.forEach((step) => {{
    model = core.applyStep(model, step);
  }});
  return {{
    size: scenario.size,
    finalState: core.modelToStateString(model),
    solved,
  }};
}});
process.stdout.write(JSON.stringify(result));
"""
    result = _run_node(script)
    for item in result:
        assert item["finalState"] == item["solved"]


def test_cube_core_interpolation_respects_boundaries_and_midpoint() -> None:
    script = f"""
const core = await import('file://{CORE_JS}');
const slots = core.createSurfaceStateSlots(3);
const solved = slots.map((slot) => slot.face).join('');
const model = core.createCubeModel(3, solved, slots);
const start = core.snapshotForState(model);
const mid = core.interpolateStep(model, ['R'], 0.5);
const end = core.interpolateStep(model, ['R'], 1);
const endModel = core.applyStep(model, ['R']);
const endSnapshot = core.snapshotForState(endModel);
const movedStart = start.cubies.find((cubie) => cubie.worldPos[0] === 1 && cubie.worldPos[1] === 1 && cubie.worldPos[2] === 1);
const movedMid = mid.cubies.find((cubie) => cubie.id === movedStart.id);
process.stdout.write(JSON.stringify({{
  startMatchesBoundary: JSON.stringify(start) === JSON.stringify(core.interpolateStep(model, ['R'], 0)),
  endMatchesBoundary: JSON.stringify(end) === JSON.stringify(endSnapshot),
  midpointMoved: JSON.stringify(movedMid.worldPos) !== JSON.stringify(movedStart.worldPos),
}}));
"""
    result = _run_node(script)
    assert result["startMatchesBoundary"] is True
    assert result["endMatchesBoundary"] is True
    assert result["midpointMoved"] is True
