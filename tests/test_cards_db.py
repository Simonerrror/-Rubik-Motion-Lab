from __future__ import annotations

import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from cubeanim.formula import FormulaConverter
from cubeanim.cards.db import connect, initialize_database, reset_runtime_state
from cubeanim.cards.services import CardsService
from cubeanim.oll import resolve_valid_oll_start_state, validate_oll_f2l_start_state
from cubeanim.pll import balance_pll_formula_rotations
from cubeanim.state import state_slots_metadata, state_string_from_moves


def _svg_polygon_nodes(svg_content: str) -> list[ET.Element]:
    root = ET.fromstring(svg_content)
    return [node for node in root.iter() if node.tag.endswith("polygon")]


def _polygon_points(raw: str) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for token in raw.split():
        px, py = token.split(",")
        points.append((float(px), float(py)))
    return points


def _centroid(points: list[tuple[float, float]]) -> tuple[float, float]:
    return (
        sum(x for x, _ in points) / len(points),
        sum(y for _, y in points) / len(points),
    )


def test_initialize_database_is_idempotent(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "cards.db"

    initialize_database(repo_root=repo_root, db_path=db_path)
    initialize_database(repo_root=repo_root, db_path=db_path)

    with connect(db_path) as conn:
        case_count = int(conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0])
        algo_count = int(conn.execute("SELECT COUNT(*) FROM algorithms").fetchone()[0])

    assert case_count == 172
    assert algo_count == 337


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


def test_canonical_seed_tables_are_complete(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "cards.db"
    initialize_database(repo_root=repo_root, db_path=db_path)

    with connect(db_path) as conn:
        canonical_case_count = int(conn.execute("SELECT COUNT(*) FROM canonical_cases").fetchone()[0])
        canonical_algo_count = int(conn.execute("SELECT COUNT(*) FROM canonical_algorithms").fetchone()[0])
        oll_nonempty = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM canonical_cases cc
                JOIN canonical_algorithms ca ON ca.canonical_case_id = cc.id
                WHERE cc.category_code = 'OLL'
                  AND TRIM(ca.formula) != ''
                """
            ).fetchone()[0]
        )

    assert canonical_case_count == 172
    assert canonical_algo_count == 337
    assert oll_nonempty == 57


def test_initialize_database_does_not_require_legacy_txt_sources(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    synthetic_root = tmp_path / "synthetic_repo"
    (synthetic_root / "db").mkdir(parents=True, exist_ok=True)
    (synthetic_root / "db" / "cards").mkdir(parents=True, exist_ok=True)
    shutil.copy2(repo_root / "db" / "cards" / "schema.sql", synthetic_root / "db" / "cards" / "schema.sql")
    shutil.copy2(repo_root / "db" / "cards" / "seed.sql", synthetic_root / "db" / "cards" / "seed.sql")

    db_path = synthetic_root / "data" / "cards" / "runtime" / "cards.db"
    initialize_database(repo_root=synthetic_root, db_path=db_path)

    with connect(db_path) as conn:
        case_count = int(conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0])
        algo_count = int(conn.execute("SELECT COUNT(*) FROM algorithms").fetchone()[0])

    assert case_count == 172
    assert algo_count == 337


def test_oll_formulas_seeded_from_oll_txt(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    service = CardsService.create(repo_root=repo_root, db_path=tmp_path / "cards.db")

    oll_items = service.list_algorithms(group="OLL")
    assert len(oll_items) == 57
    assert all(str(item["formula"]).strip() for item in oll_items if not item.get("is_custom"))

    oll_by_case = {item["case_code"]: item for item in oll_items}
    assert oll_by_case["OLL_1"]["formula"] == "R U2 R2 F R F' U2 R' F R F'"
    assert oll_by_case["OLL_12"]["formula"] == "F R U R' U' F' U F R U R' U' F'"
    assert oll_by_case["OLL_14"]["formula"] == "R' F R U R' F' R F U' F'"
    assert oll_by_case["OLL_20"]["formula"] == "M U (R U R' U') M2 (U R U' R') M"
    assert oll_by_case["OLL_26"]["formula"] == "R U2 R' U' R U' R'"
    assert oll_by_case["OLL_27"]["formula"] == "R U R' U R U2 R'"
    assert oll_by_case["OLL_57"]["formula"] == "(R U R' U') M' (U R U' r')"


def test_seeded_oll_1_and_20_formulas_produce_valid_oll_start_state(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    service = CardsService.create(repo_root=repo_root, db_path=tmp_path / "cards.db")
    oll_by_case = {
        item["case_code"]: str(item["formula"] or "")
        for item in service.list_algorithms(group="OLL")
        if not item.get("is_custom")
    }

    for case_code in ("OLL_1", "OLL_20"):
        moves = FormulaConverter.convert(oll_by_case[case_code])
        inverse = FormulaConverter.invert_moves(moves)
        state = resolve_valid_oll_start_state(inverse)
        validate_oll_f2l_start_state(state)


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


def test_oll_1_12_14_20_are_not_fallback_recognizers(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "cards.db"
    initialize_database(repo_root=repo_root, db_path=db_path)

    svg_dir = tmp_path / "recognizers" / "oll" / "svg"
    for case_code in ("oll_oll_1.svg", "oll_oll_12.svg", "oll_oll_14.svg", "oll_oll_20.svg"):
        content = (svg_dir / case_code).read_text(encoding="utf-8")
        assert "recognizer:v4-fallback" not in content


def test_f2l_recognizer_version_marker(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "cards.db"
    initialize_database(repo_root=repo_root, db_path=db_path)

    svg_dir = tmp_path / "recognizers" / "f2l" / "svg"
    content = (svg_dir / "f2l_b01.svg").read_text(encoding="utf-8")
    assert "recognizer:v11-f2l category=F2L case=B01" in content
    assert "recognizer:v4-fallback" not in content


def test_f2l_recognizer_has_27_sticker_cells(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "cards.db"
    initialize_database(repo_root=repo_root, db_path=db_path)

    svg_dir = tmp_path / "recognizers" / "f2l" / "svg"
    content = (svg_dir / "f2l_a06.svg").read_text(encoding="utf-8")
    sticker_cells = [
        node
        for node in _svg_polygon_nodes(content)
        if node.attrib.get("data-layer") == "sticker"
    ]
    assert len(sticker_cells) == 27


def test_f2l_recognizer_has_matching_27_cubie_cells(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "cards.db"
    initialize_database(repo_root=repo_root, db_path=db_path)

    svg_dir = tmp_path / "recognizers" / "f2l" / "svg"
    content = (svg_dir / "f2l_a06.svg").read_text(encoding="utf-8")
    cubie_cells = [
        node
        for node in _svg_polygon_nodes(content)
        if node.attrib.get("data-layer") == "cubie"
    ]
    assert len(cubie_cells) == 27


def test_f2l_recognizer_mask_applies_by_cubie_u(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "cards.db"
    initialize_database(repo_root=repo_root, db_path=db_path)

    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT ca.formula
            FROM canonical_cases cc
            JOIN canonical_algorithms ca ON ca.canonical_case_id = cc.id
            WHERE cc.category_code = 'F2L'
              AND cc.case_code = 'A06'
            ORDER BY ca.is_primary DESC, ca.sort_order ASC, ca.id ASC
            LIMIT 1
            """
        ).fetchone()
        assert row is not None
        formula = str(row["formula"] or "")

    move_steps = FormulaConverter.convert_steps(formula, repeat=1)
    inverse_steps = FormulaConverter.invert_steps(move_steps)
    inverse_flat = [move for step in inverse_steps for move in step]
    start_state = state_string_from_moves(inverse_flat)

    masked_positions: set[tuple[int, int, int]] = set()
    for (position, _face), color_code in zip(state_slots_metadata(), start_state, strict=True):
        if color_code != "U":
            continue
        masked_positions.add((int(position[0]), int(position[1]), int(position[2])))
    assert masked_positions

    svg_dir = tmp_path / "recognizers" / "f2l" / "svg"
    content = (svg_dir / "f2l_a06.svg").read_text(encoding="utf-8")
    masked_fill = "#0b1220"
    sticker_polygons = [
        node
        for node in _svg_polygon_nodes(content)
        if node.attrib.get("data-layer") == "sticker"
    ]

    unmasked_count = 0
    for polygon in sticker_polygons:
        pos_token = str(polygon.attrib.get("data-pos", ""))
        pos = tuple(int(chunk) for chunk in pos_token.split(","))
        fill = str(polygon.attrib.get("fill", "")).lower()
        if pos in masked_positions:
            assert fill == masked_fill
        else:
            unmasked_count += int(fill != masked_fill)

    assert unmasked_count > 0


def test_f2l_recognizer_orientation_adjacency(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "cards.db"
    initialize_database(repo_root=repo_root, db_path=db_path)

    svg_dir = tmp_path / "recognizers" / "f2l" / "svg"
    content = (svg_dir / "f2l_a06.svg").read_text(encoding="utf-8")
    sticker_polygons = [
        node
        for node in _svg_polygon_nodes(content)
        if node.attrib.get("data-layer") == "sticker"
    ]

    centroids: dict[tuple[str, tuple[int, int, int]], tuple[float, float]] = {}
    for polygon in sticker_polygons:
        face = str(polygon.attrib.get("data-face", ""))
        pos = tuple(int(chunk) for chunk in str(polygon.attrib.get("data-pos", "")).split(","))
        centroids[(face, pos)] = _centroid(_polygon_points(str(polygon.attrib.get("points", ""))))

    u_back = [centroids[("U", (1, y, 1))][1] for y in (1, 0, -1)]
    u_front = [centroids[("U", (-1, y, 1))][1] for y in (1, 0, -1)]
    assert sum(u_front) / len(u_front) > sum(u_back) / len(u_back)

    f_top = [centroids[("F", (-1, y, 1))][1] for y in (1, 0, -1)]
    f_bottom = [centroids[("F", (-1, y, -1))][1] for y in (1, 0, -1)]
    assert sum(f_top) / len(f_top) < sum(f_bottom) / len(f_bottom)

    r_top = [centroids[("R", (x, -1, 1))][1] for x in (-1, 0, 1)]
    r_bottom = [centroids[("R", (x, -1, -1))][1] for x in (-1, 0, 1)]
    assert sum(r_top) / len(r_top) < sum(r_bottom) / len(r_bottom)


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


def test_f2l_default_order_is_basic_advanced_expert(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    service = CardsService.create(repo_root=repo_root, db_path=tmp_path / "cards.db")

    cases = service.list_cases("F2L")
    assert cases

    case_codes = [str(item["case_code"]) for item in cases]
    assert case_codes[0] == "B01"
    assert case_codes[40] == "B41"
    assert case_codes[41] == "A01"
    assert case_codes[76] == "A36"
    assert case_codes[77] == "E01"
    assert case_codes[-1] == "E17"

    algorithms = service.list_algorithms(group="F2L")
    seen_case_codes: list[str] = []
    seen_set: set[str] = set()
    for item in algorithms:
        code = str(item["case_code"])
        if code in seen_set:
            continue
        seen_set.add(code)
        seen_case_codes.append(code)
    assert seen_case_codes[:5] == ["B01", "B02", "B03", "B04", "B05"]
    assert seen_case_codes[-3:] == ["E15", "E16", "E17"]


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
