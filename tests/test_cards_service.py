from __future__ import annotations

from pathlib import Path

import pytest

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


def test_service_progress_flow(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    case_id = int(service.list_cases(group="PLL")[0]["id"])

    updated = service.set_case_progress(case_id=case_id, status="IN_PROGRESS")
    assert updated["status"] == "IN_PROGRESS"


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


def test_service_reference_sets(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    reference_sets = service.list_reference_sets(category="PLL")
    assert reference_sets
    assert reference_sets[0]["title"] == "Skip"
    assert any(item["title"] == "G-Perms" for item in reference_sets)


def test_service_lists_data_driven_categories_and_zbls_cases(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    categories = service.list_categories(enabled_only=True)
    codes = [item["code"] for item in categories]
    assert codes == ["F2L", "OLL", "ZBLS", "ZBLL", "PLL"]

    zbls_cases = service.list_cases(group="ZBLS")
    assert [case["case_code"] for case in zbls_cases] == ["ZBLS_U01", "ZBLS_U02"]
    assert all(str(case.get("active_formula") or "").strip() for case in zbls_cases)

    zbll_cases = service.list_cases(group="ZBLL")
    assert len(zbll_cases) == 472
    assert zbll_cases[0]["case_code"].startswith("ZBLL_")
    assert all(str(case.get("active_formula") or "").strip() for case in zbll_cases)


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


def test_service_runtime_root_tracks_custom_db_path(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "runtime" / "cards.db"
    service = CardsService.create(repo_root=Path(__file__).resolve().parents[1], db_path=db_path)

    assert service.db_path == db_path
    assert (db_path.parent / "recognizers").exists()


def test_service_rejects_invalid_formula_for_group(tmp_path: Path) -> None:
    service = _build_service(tmp_path)
    case_id = int(service.list_cases(group="PLL")[0]["id"])

    with pytest.raises(Exception):
        service.create_alternative(case_id=case_id, formula="R + F")
