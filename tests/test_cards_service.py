from __future__ import annotations

from pathlib import Path

import pytest

from cubeanim.cards import repository
from cubeanim.cards.db import connect
from cubeanim.cards.services import CardsService


def _build_service(tmp_path: Path) -> CardsService:
    repo_root = Path(__file__).resolve().parents[1]
    return CardsService.create(repo_root=repo_root, db_path=tmp_path / "cards.db")


def test_service_cases_detail_and_alternatives_roundtrip(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    cases = service.list_cases(group="OLL")
    assert cases

    first_case_id = int(cases[0]["id"])
    detail = service.get_case(first_case_id)
    assert detail["id"] == first_case_id

    alternatives = service.list_alternatives(first_case_id)
    assert alternatives
    assert sum(1 for item in alternatives if item["is_active"]) == 1


def test_service_progress_and_render_flow(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    case_id = int(service.list_cases(group="PLL")[0]["id"])

    updated = service.set_case_progress(case_id=case_id, status="IN_PROGRESS")
    assert updated["status"] == "IN_PROGRESS"

    queued = service.queue_case_render(case_id=case_id, quality="draft")
    assert queued["job"]["status"] in {"PENDING", "DONE"}

    status = service.case_queue_status(case_id=case_id)
    assert isinstance(status["jobs"], list)
    assert status["algorithm_id"] == updated["active_algorithm_id"]


def test_service_alternatives_crud_flow(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    case_id = int(service.list_cases(group="OLL")[0]["id"])
    before_payload = service.get_case(case_id)
    previous_active_id = int(before_payload["active_algorithm_id"])

    custom_payload = service.create_alternative(
        case_id=case_id,
        formula="R U R' U R U2 R'",
        activate=True,
    )
    assert custom_payload["active_formula"] == "R U R' U R U2 R'"
    new_active_id = int(custom_payload["active_algorithm_id"])
    assert new_active_id != previous_active_id

    alternatives = service.list_alternatives(case_id)
    assert any(item["id"] == new_active_id and item["is_active"] for item in alternatives)

    activate_payload = service.activate_alternative(case_id=case_id, algorithm_id=previous_active_id)
    assert int(activate_payload["active_algorithm_id"]) == previous_active_id

    delete_payload = service.delete_alternative(case_id=case_id, algorithm_id=new_active_id)
    assert delete_payload["deleted_algorithm_id"] == new_active_id
    assert delete_payload["case"]["active_algorithm_id"] != new_active_id


def test_service_reference_sets_and_sandbox_payload(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    reference_sets = service.list_reference_sets(category="PLL")
    assert reference_sets
    assert reference_sets[0]["title"] == "Skip"
    assert any(item["title"] == "G-Perms" for item in reference_sets)

    case_id = int(service.list_cases(group="PLL")[0]["id"])
    payload = service.get_case_sandbox(case_id)
    assert payload["case_id"] == case_id
    assert payload["group"] == "PLL"
    assert payload["step_count"] == len(payload["move_steps"])
    assert len(payload["states_by_step"]) == payload["step_count"] + 1
    assert len(payload["state_slots"]) == 54
    assert all(len(state) == 54 for state in payload["states_by_step"])
    assert payload["playback_config"]["rate_func"] == "ease_in_out_sine"
    assert float(payload["playback_config"]["run_time_sec"]) > 0
    assert float(payload["playback_config"]["double_turn_multiplier"]) > 1
    assert float(payload["playback_config"]["inter_move_pause_ratio"]) >= 0
    assert payload["face_colors"] == {
        "U": "#FDFF00",
        "R": "#C1121F",
        "F": "#2DBE4A",
        "D": "#F4F4F4",
        "L": "#E06A00",
        "B": "#2B63E8",
    }


def test_service_case_sandbox_uses_env_move_runtime(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CUBEANIM_MOVE_RUN_TIME", "1.25")
    service = _build_service(tmp_path)
    case_id = int(service.list_cases(group="PLL")[0]["id"])

    payload = service.get_case_sandbox(case_id)
    assert payload["playback_config"]["run_time_sec"] == pytest.approx(1.25)


def test_service_activate_does_not_reorder_algorithms(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    case_id = int(service.list_cases(group="PLL")[0]["id"])
    before_payload = service.get_case(case_id)
    default_algo_id = int(before_payload["active_algorithm_id"])

    custom_payload = service.create_alternative(
        case_id=case_id,
        formula="R U R' U'",
        activate=True,
    )
    order_with_custom_active = [int(item["id"]) for item in custom_payload["algorithms"]]
    custom_algo_id = int(custom_payload["active_algorithm_id"])
    assert custom_algo_id != default_algo_id

    activate_payload = service.activate_alternative(case_id=case_id, algorithm_id=default_algo_id)
    order_with_default_active = [int(item["id"]) for item in activate_payload["algorithms"]]

    assert order_with_default_active == order_with_custom_active
    assert int(activate_payload["active_algorithm_id"]) == default_algo_id


def test_service_ignores_stale_artifact_paths(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    case_id = int(service.list_cases(group="PLL")[0]["id"])
    detail = service.get_case(case_id)
    algorithm_id = int(detail["active_algorithm_id"])
    formula_norm = " ".join(str(detail["active_formula"]).split())

    with connect(service.db_path) as conn:
        repository.upsert_render_artifact(
            conn,
            algorithm_id=algorithm_id,
            quality="high",
            output_name="stale_high",
            output_path="media/videos/PLL/high/stale_high.mp4",
            formula_norm=formula_norm,
            repeat=1,
        )

    refreshed = service.get_case(case_id)
    assert refreshed["artifacts"]["high"] is None


def test_service_high_queue_rejects_stale_draft_artifact(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    case_id = int(service.list_cases(group="PLL")[0]["id"])
    detail = service.get_case(case_id)
    algorithm_id = int(detail["active_algorithm_id"])
    formula_norm = " ".join(str(detail["active_formula"]).split())

    with connect(service.db_path) as conn:
        repository.upsert_render_artifact(
            conn,
            algorithm_id=algorithm_id,
            quality="draft",
            output_name="stale_draft",
            output_path="media/videos/PLL/draft/stale_draft.mp4",
            formula_norm=formula_norm,
            repeat=1,
        )

    with pytest.raises(ValueError, match="draft artifact"):
        service.queue_case_render(case_id=case_id, quality="high")


def test_service_reset_runtime_reseeds_cases(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    with connect(service.db_path) as conn:
        conn.execute("UPDATE cases SET title = 'BROKEN' WHERE case_code = 'PLL_9'")

    payload = service.reset_runtime()
    assert payload["db_path"] == str(service.db_path)

    pll_cases = service.list_cases(group="PLL")
    assert len(pll_cases) == 21
    oll_cases = service.list_cases(group="OLL")
    assert len(oll_cases) == 57
    assert all(str(item.get("active_formula") or "").strip() for item in oll_cases)
