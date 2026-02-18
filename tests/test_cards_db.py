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


def test_static_reference_tables_seeded(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "cards.db"
    initialize_database(repo_root=repo_root, db_path=db_path)

    with connect(db_path) as conn:
        set_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM reference_case_sets WHERE category_code = 'PLL'"
            ).fetchone()[0]
        )
        item_count = int(conn.execute("SELECT COUNT(*) FROM reference_case_stats").fetchone()[0])

    assert set_count == 6
    assert item_count == 14


def test_pll_formulas_seeded_from_pll_txt(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    service = CardsService.create(repo_root=repo_root, db_path=tmp_path / "cards.db")

    pll_items = service.list_algorithms(group="PLL")
    pll_by_case = {item["case_code"]: item for item in pll_items}
    assert pll_by_case["PLL_9"]["formula"] == "R U R' F' R U R' U' R' F R2 U' R'"
    assert pll_by_case["PLL_18"]["formula"] == "M2 U M2 U2 M2 U M2"


def test_pll_recognizer_svg_contains_overlay_markers(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "cards.db"
    initialize_database(repo_root=repo_root, db_path=db_path)

    svg_path = tmp_path / "recognizers" / "svg" / "pll_pll_9.svg"
    assert svg_path.exists()
    content = svg_path.read_text(encoding="utf-8")
    assert "recognizer:v3 category=PLL case=PLL_9" in content
    assert "marker-end=\"url(#arrowhead)\"" in content
