from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
STORE_JS = REPO_ROOT / "apps" / "trainer" / "modules" / "sandbox" / "store.js"


def _run_node(script: str) -> object:
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        text=True,
        capture_output=True,
        check=True,
        cwd=REPO_ROOT,
    )
    return json.loads(completed.stdout)


def test_sandbox_store_tracks_progress_speed_and_queue() -> None:
    script = f"""
const mod = await import('file://{STORE_JS}');
const store = mod.createSandboxStore();
store.dispatch({{
  type: 'LOAD_TIMELINE',
  timeline: {{ move_steps: [['R'], ['U'], ["R'"]] }},
  activeFormula: "R U R'",
  cubeSize: 3,
  timelineModels: [],
  timelineSnapshots: [],
  playbackConfig: {{ run_time_sec: 0.65, double_turn_multiplier: 1.7, inter_move_pause_ratio: 0.05, rate_func: 'ease_in_out_sine' }},
}});
store.dispatch({{ type: 'SET_SPEED', speed: 1.5 }});
store.dispatch({{ type: 'SET_PROGRESS', progress: 1.25 }});
store.dispatch({{ type: 'SET_PLAYBACK_MODE', mode: 'playing' }});
store.dispatch({{ type: 'ENQUEUE_ACTION', payload: 'next' }});
store.dispatch({{ type: 'ENQUEUE_ACTION', payload: 'prev' }});
store.dispatch({{ type: 'BUMP_TOKEN' }});
process.stdout.write(JSON.stringify(store.getState()));
"""
    result = _run_node(script)
    assert result["playbackSpeed"] == 1.5
    assert result["timelineProgress"] == 1.25
    assert result["cursorStepIndex"] == 1
    assert result["cursorStepProgress"] == 0.25
    assert result["playbackMode"] == "playing"
    assert result["pendingActionQueue"] == ["next", "prev"]
    assert result["playbackToken"] >= 2
