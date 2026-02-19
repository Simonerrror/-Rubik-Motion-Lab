from __future__ import annotations

import re
from pathlib import Path

from cubeanim.cards.db import _load_oll_seed_cases, connect, initialize_database, reset_runtime_state
from cubeanim.cards.services import CardsService
from cubeanim.pll import balance_pll_formula_rotations


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
    assert pll_by_case["PLL_21"]["formula"] == "M2 U M2 U M' U2 M2 U2 M' U2"


def test_oll_seed_source_is_complete_and_strict() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    oll_cases = _load_oll_seed_cases(repo_root)
    assert len(oll_cases) == 57

    for index in range(1, 58):
        case_code = f"OLL_{index}"
        assert case_code in oll_cases
        item = oll_cases[case_code]
        assert item.case_title == f"OLL #{index}"
        assert item.formula
        assert re.fullmatch(r"\d+/\d+", item.probability_text)
        assert item.subgroup_title


def test_oll_formulas_seeded_from_oll_txt(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    service = CardsService.create(repo_root=repo_root, db_path=tmp_path / "cards.db")

    oll_items = service.list_algorithms(group="OLL")
    assert len(oll_items) == 57
    assert all(str(item["formula"]).strip() for item in oll_items if not item.get("is_custom"))

    oll_by_case = {item["case_code"]: item for item in oll_items}
    assert oll_by_case["OLL_26"]["formula"] == "R U2 R' U' R U' R'"
    assert oll_by_case["OLL_27"]["formula"] == "R U R' U R U2 R'"
    assert oll_by_case["OLL_57"]["formula"] == "(R U R' U') M' (U R U' r')"


def test_seeded_pll_formulas_are_rotation_balanced(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    service = CardsService.create(repo_root=repo_root, db_path=tmp_path / "cards.db")

    pll_items = service.list_algorithms(group="PLL")
    for item in pll_items:
        if item.get("is_custom"):
            continue
        formula = str(item["formula"] or "")
        assert balance_pll_formula_rotations(formula) == formula


def test_pll_recognizer_svg_contains_overlay_markers(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "cards.db"
    initialize_database(repo_root=repo_root, db_path=db_path)

    svg_dir = tmp_path / "recognizers" / "pll" / "svg"
    matches = sorted(svg_dir.glob("pll_pll_9*.svg"))
    assert matches
    content = matches[0].read_text(encoding="utf-8")
    assert "recognizer:v4 category=PLL case=PLL_9" in content
    assert "<polygon points=" in content
    assert "marker-end=\"url(#arrowhead)\"" not in content
    assert "<text" not in content
    assert "rx=\"10\"" not in content
    assert content.count("<line ") >= 1

    # Guard against malformed arrows leaving canvas bounds.
    geom_values = [
        float(value)
        for value in re.findall(
            r'(?:x|y|x1|y1|x2|y2|width|height)="([0-9]+(?:\.[0-9]+)?)"',
            content,
        )
    ]
    polygon_tokens = re.findall(r'points="([^"]+)"', content)
    for token in polygon_tokens:
        for pair in token.split():
            px, py = pair.split(",")
            geom_values.extend([float(px), float(py)])
    assert geom_values
    assert min(geom_values) >= 0.0
    assert max(geom_values) <= 128.0


def test_oll_recognizer_svg_is_minimal_top_card(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "cards.db"
    initialize_database(repo_root=repo_root, db_path=db_path)

    svg_dir = tmp_path / "recognizers" / "oll" / "svg"
    matches = sorted(svg_dir.glob("oll_oll_26*.svg"))
    assert matches
    content = matches[0].read_text(encoding="utf-8")
    assert "recognizer:v4 category=OLL case=OLL_26" in content
    assert "<text" not in content
    assert "rx=\"10\"" not in content


def test_oll_recognizer_path_is_case_stable(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    service = CardsService.create(repo_root=repo_root, db_path=tmp_path / "cards.db")

    case = next(item for item in service.list_cases("OLL") if item["case_code"] == "OLL_26")
    before_url = case["recognizer_url"] or ""
    assert before_url.endswith("/assets/recognizers/oll/svg/oll_oll_26.svg")

    updated = service.create_case_custom_algorithm(
        case_id=int(case["id"]),
        formula="R U R' U R U2 R'",
        activate=True,
    )
    after_url = updated["recognizer_url"] or ""
    assert before_url == after_url


def test_pll_recognizer_path_is_case_stable(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    service = CardsService.create(repo_root=repo_root, db_path=tmp_path / "cards.db")

    case = next(item for item in service.list_cases("PLL") if item["case_code"] == "PLL_9")
    before_url = case["recognizer_url"] or ""
    assert before_url.endswith("/assets/recognizers/pll/svg/pll_pll_9.svg")

    updated = service.create_case_custom_algorithm(
        case_id=int(case["id"]),
        formula="R U R' U' R' F R2 U R' U' F'",
        activate=True,
    )
    after_url = updated["recognizer_url"] or ""
    assert after_url == before_url


def test_pll_case_metadata_follows_pll_txt_names(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    service = CardsService.create(repo_root=repo_root, db_path=tmp_path / "cards.db")

    case = next(item for item in service.list_cases("PLL") if item["case_code"] == "PLL_9")
    assert case["display_name"] == "Jb-perm"
    assert case["subgroup_title"] == "Adjacent Corner Swap"
    assert case["probability_text"] == "1/18"


def test_oll_case_metadata_follows_oll_txt(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    service = CardsService.create(repo_root=repo_root, db_path=tmp_path / "cards.db")

    case = next(item for item in service.list_cases("OLL") if item["case_code"] == "OLL_26")
    assert case["display_name"] == "OLL #26"
    assert case["subgroup_title"] == "Cross (Antisune)"
    assert case["probability_text"] == "1/54"


def test_runtime_reset_rebuilds_database(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "cards.db"
    initialize_database(repo_root=repo_root, db_path=db_path)

    with connect(db_path) as conn:
        conn.execute("UPDATE cases SET title = 'BROKEN' WHERE case_code = 'PLL_9'")

    reset_runtime_state(repo_root=repo_root, db_path=db_path)
    with connect(db_path) as conn:
        row = conn.execute("SELECT title FROM cases WHERE case_code = 'PLL_9'").fetchone()
    assert row is not None
    assert row["title"] == "Jb-perm"


def test_pll_seed_cleans_legacy_noncustom_algorithms(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "cards.db"
    initialize_database(repo_root=repo_root, db_path=db_path)

    with connect(db_path) as conn:
        case_row = conn.execute(
            "SELECT id FROM cases WHERE case_code = 'PLL_3'"
        ).fetchone()
        assert case_row is not None
        case_id = int(case_row["id"])
        now = "2026-02-18T00:00:00+00:00"
        conn.execute(
            """
            INSERT INTO algorithms (case_id, name, formula, progress_status, is_custom, created_at, updated_at)
            VALUES (?, 'PLL_3', 'R U R'' U''', 'NEW', 0, ?, ?)
            """,
            (case_id, now, now),
        )
        legacy_row = conn.execute(
            "SELECT id FROM algorithms WHERE case_id = ? AND name = 'PLL_3'",
            (case_id,),
        ).fetchone()
        assert legacy_row is not None
        legacy_id = int(legacy_row["id"])
        conn.execute(
            "UPDATE cases SET selected_algorithm_id = ? WHERE id = ?",
            (legacy_id, case_id),
        )

    initialize_database(repo_root=repo_root, db_path=db_path)

    with connect(db_path) as conn:
        count_noncustom = int(
            conn.execute(
                "SELECT COUNT(*) FROM algorithms WHERE case_id = (SELECT id FROM cases WHERE case_code = 'PLL_3') AND is_custom = 0"
            ).fetchone()[0]
        )
        active = conn.execute(
            """
            SELECT a.name, a.formula
            FROM cases c
            JOIN algorithms a ON a.id = c.selected_algorithm_id
            WHERE c.case_code = 'PLL_3'
            """
        ).fetchone()
    assert count_noncustom == 1
    assert active is not None
    assert active["name"] == "F"
