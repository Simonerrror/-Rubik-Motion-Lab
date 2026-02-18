from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from cubeanim.cards.services import CardsService
import scripts.cards_api as cards_api


def _build_client(tmp_path: Path) -> TestClient:
    repo_root = Path(__file__).resolve().parents[1]
    service = CardsService.create(repo_root=repo_root, db_path=tmp_path / "cards.db")
    cards_api.service = service
    return TestClient(cards_api.app)


def test_api_algorithms_filter_and_detail(tmp_path: Path) -> None:
    client = _build_client(tmp_path)

    response = client.get("/api/algorithms", params={"group": "OLL"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]

    first_id = payload["data"][0]["id"]
    detail = client.get(f"/api/algorithms/{first_id}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["ok"] is True
    assert detail_payload["data"]["id"] == first_id


def test_api_progress_and_queue(tmp_path: Path) -> None:
    client = _build_client(tmp_path)

    items = client.get("/api/algorithms", params={"group": "PLL"}).json()["data"]
    algo_id = int(items[0]["id"])

    progress_resp = client.post(
        "/api/progress",
        json={"algorithm_id": algo_id, "status": "IN_PROGRESS"},
    )
    assert progress_resp.status_code == 200
    assert progress_resp.json()["data"]["status"] == "IN_PROGRESS"

    queue_resp = client.post(
        "/api/queue",
        json={"algorithm_id": algo_id, "quality": "draft"},
    )
    assert queue_resp.status_code == 200
    queue_payload = queue_resp.json()
    assert queue_payload["ok"] is True
    assert queue_payload["data"]["job"]["status"] in {"PENDING", "DONE"}

    status_resp = client.get("/api/queue/status", params={"algorithm_id": algo_id})
    assert status_resp.status_code == 200
    status_payload = status_resp.json()
    assert status_payload["ok"] is True
    assert status_payload["data"]["algorithm_id"] == algo_id
    assert isinstance(status_payload["data"]["jobs"], list)


def test_api_cases_and_alternatives_flow(tmp_path: Path) -> None:
    client = _build_client(tmp_path)

    cases_resp = client.get("/api/cases", params={"group": "OLL"})
    assert cases_resp.status_code == 200
    cases_payload = cases_resp.json()
    assert cases_payload["ok"] is True
    assert cases_payload["data"]
    assert "display_name" in cases_payload["data"][0]

    case_id = int(cases_payload["data"][0]["id"])
    detail_before = client.get(f"/api/cases/{case_id}")
    assert detail_before.status_code == 200
    before_payload = detail_before.json()["data"]
    previous_active_id = int(before_payload["active_algorithm_id"])

    custom_resp = client.post(
        f"/api/cases/{case_id}/custom",
        json={"formula": "R U R' U'", "activate": True},
    )
    assert custom_resp.status_code == 200
    custom_payload = custom_resp.json()["data"]
    assert custom_payload["active_formula"] == "R U R' U'"
    assert any(item["formula"] == "R U R' U'" for item in custom_payload["algorithms"])
    new_active_id = int(custom_payload["active_algorithm_id"])
    assert new_active_id != previous_active_id

    queue_resp = client.post(
        f"/api/cases/{case_id}/queue",
        json={"quality": "draft"},
    )
    assert queue_resp.status_code == 200
    queue_payload = queue_resp.json()["data"]
    assert queue_payload["job"]["status"] in {"PENDING", "DONE"}

    status_resp = client.get("/api/queue/status", params={"case_id": case_id})
    assert status_resp.status_code == 200
    status_payload = status_resp.json()["data"]
    assert int(status_payload["algorithm_id"]) == new_active_id

    activate_resp = client.post(
        f"/api/cases/{case_id}/activate",
        json={"algorithm_id": previous_active_id},
    )
    assert activate_resp.status_code == 200
    activate_payload = activate_resp.json()["data"]
    assert int(activate_payload["active_algorithm_id"]) == previous_active_id

    delete_resp = client.delete(f"/api/cases/{case_id}/algorithms/{new_active_id}")
    assert delete_resp.status_code == 200
    delete_payload = delete_resp.json()["data"]
    assert delete_payload["deleted_algorithm_id"] == new_active_id
    assert delete_payload["case"]["active_algorithm_id"] != new_active_id


def test_api_reference_sets(tmp_path: Path) -> None:
    client = _build_client(tmp_path)

    response = client.get("/api/reference/sets", params={"category": "PLL"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]
    assert payload["data"][0]["title"] == "Skip"
    assert any(item["title"] == "G-Perms" for item in payload["data"])


def test_api_admin_reset_runtime(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    response = client.post("/api/admin/reset-runtime")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "db_path" in payload["data"]

    pll_cases = client.get("/api/cases", params={"group": "PLL"}).json()["data"]
    assert len(pll_cases) == 21
