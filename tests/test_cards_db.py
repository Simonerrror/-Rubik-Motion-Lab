from __future__ import annotations

from pathlib import Path

from cubeanim.cards.db import connect, initialize_database
from cubeanim.cards.services import CardsService


def test_initialize_database_is_idempotent(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "cards.db"

    initialize_database(repo_root=repo_root, db_path=db_path)
    initialize_database(repo_root=repo_root, db_path=db_path)

    with connect(db_path) as conn:
        case_count = int(conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0])
        algo_count = int(conn.execute("SELECT COUNT(*) FROM algorithms").fetchone()[0])

    assert case_count == 88
    assert algo_count == 88


def test_progress_status_update_roundtrip(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    service = CardsService.create(repo_root=repo_root, db_path=tmp_path / "cards.db")

    algorithms = service.list_algorithms(group="PLL")
    assert algorithms

    algo_id = int(algorithms[0]["id"])
    updated = service.set_progress(algo_id, "IN_PROGRESS")
    assert updated["status"] == "IN_PROGRESS"

    updated = service.set_progress(algo_id, "LEARNED")
    assert updated["status"] == "LEARNED"
