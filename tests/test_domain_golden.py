from __future__ import annotations

import json
from pathlib import Path

from cubeanim_domain.formula import FormulaConverter
from cubeanim_domain.sandbox import build_sandbox_timeline


FIXTURES_PATH = Path(__file__).parent / "fixtures" / "domain" / "formula_golden.json"


def test_python_domain_matches_golden_fixtures() -> None:
    fixtures = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    assert fixtures

    for fixture in fixtures:
        timeline = build_sandbox_timeline(fixture["formula"], fixture["group"])
        assert timeline.formula == fixture["normalized_formula"]
        assert timeline.move_steps == fixture["move_steps"]
        assert timeline.moves_flat == fixture["moves_flat"]
        assert FormulaConverter.invert_steps(timeline.move_steps) == fixture["inverse_steps"]
        assert timeline.initial_state == fixture["initial_state"]
        assert timeline.states_by_step == fixture["states_by_step"]
        assert timeline.highlight_by_step == fixture["highlight_by_step"]
