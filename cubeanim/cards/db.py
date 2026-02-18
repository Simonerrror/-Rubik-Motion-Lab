from __future__ import annotations

import csv
import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Any

from cubeanim.cards.recognizer import ensure_recognizer_assets

DEFAULT_DB_ENV = "CUBEANIM_CARDS_DB"


_OLL_SUBGROUPS: dict[str, set[int]] = {
    "All Edges Oriented Correctly": {21, 22, 23, 24, 25, 26, 27},
    "No Edges Oriented Correctly": {1, 2, 3, 4, 17, 18, 19, 20},
    "T-Shapes": {33, 45},
    "Squares": {5, 6},
    "C-Shapes": {34, 46},
    "W-Shapes": {36, 38},
    "Corners Correct, Edges Flipped": {28, 57},
    "P-Shapes": {31, 32, 43, 44},
    "I-Shapes": {51, 52, 55, 56},
    "Fish Shapes": {9, 10, 35, 37},
    "Knight Move Shapes": {13, 14, 15, 16},
    "Awkward Shapes": {29, 30, 41, 42},
    "L-Shapes": {47, 48, 49, 50, 53, 54},
    "Lightning Bolts": {7, 8, 11, 12, 39, 40},
}

_OLL_PROBABILITY_OVERRIDES: dict[int, str] = {
    1: "1/108",
    20: "1/216",
    21: "1/108",
    55: "1/108",
    56: "1/108",
    57: "1/108",
}

_PLL_PROBABILITY_BY_NUMBER: dict[int, str] = {
    1: "1/18",   # Aa
    2: "1/18",   # Ab
    3: "1/36",   # E
    4: "1/18",   # F
    5: "1/12",   # Ga
    6: "1/12",   # Gb
    7: "1/12",   # Gc
    8: "1/12",   # Gd
    9: "1/72",   # H
    10: "1/18",  # Ja
    11: "1/18",  # Jb
    12: "1/72",  # Na
    13: "1/72",  # Nb
    14: "1/18",  # Ra
    15: "1/18",  # Rb
    16: "1/12",  # T
    17: "1/18",  # Ua
    18: "1/18",  # Ub
    19: "1/18",  # V
    20: "1/18",  # Y
    21: "1/36",  # Z
}

_PLL_SUBGROUPS: dict[str, set[int]] = {
    "Edges Only": {9, 17, 18, 21},
    "Corners Only": {1, 2, 3},
    "Adjacent Swap": {4, 10, 11, 14, 15, 16},
    "Diagonal Swap": {12, 13, 19, 20},
    "G-Perms": {5, 6, 7, 8},
}

_PLL_REFERENCE_SETS: list[dict[str, Any]] = [
    {
        "set_code": "skip",
        "title": "Skip",
        "items": [
            {
                "case_name": "PLL Skip",
                "probability_fraction": "1/72",
                "probability_percent_text": "1.39%",
                "states_out_of_96_text": "1",
                "recognition_dod": "Все элементы на своих местах.",
            },
        ],
    },
    {
        "set_code": "edges_only",
        "title": "Edges Only",
        "items": [
            {
                "case_name": "Ua / Ub",
                "probability_fraction": "1/18 (каждый)",
                "probability_percent_text": "5.56%",
                "states_out_of_96_text": "4 + 4",
                "recognition_dod": "3 угла на местах, перестановка 3 ребер.",
            },
            {
                "case_name": "H",
                "probability_fraction": "1/72",
                "probability_percent_text": "1.39%",
                "states_out_of_96_text": "1",
                "recognition_dod": "Взаимная перестановка противоположных ребер.",
            },
            {
                "case_name": "Z",
                "probability_fraction": "1/36",
                "probability_percent_text": "2.78%",
                "states_out_of_96_text": "2",
                "recognition_dod": "Взаимная перестановка смежных ребер.",
            },
        ],
    },
    {
        "set_code": "corners_only",
        "title": "Corners Only",
        "items": [
            {
                "case_name": "Aa / Ab",
                "probability_fraction": "1/18 (каждый)",
                "probability_percent_text": "5.56%",
                "states_out_of_96_text": "4 + 4",
                "recognition_dod": "3 ребра на местах, перестановка 3 углов.",
            },
            {
                "case_name": "E",
                "probability_fraction": "1/36",
                "probability_percent_text": "2.78%",
                "states_out_of_96_text": "2",
                "recognition_dod": "Перестановка углов по диагонали (без блоков).",
            },
        ],
    },
    {
        "set_code": "adjacent_swap",
        "title": "Adjacent Swap",
        "items": [
            {
                "case_name": "Ja / Jb",
                "probability_fraction": "1/18 (каждый)",
                "probability_percent_text": "5.56%",
                "states_out_of_96_text": "4 + 4",
                "recognition_dod": "Блок 1x1x3 («Полоска»).",
            },
            {
                "case_name": "T",
                "probability_fraction": "1/12",
                "probability_percent_text": "8.33%",
                "states_out_of_96_text": "8",
                "recognition_dod": "Два блока 1x1x2 («Глазки» и «Бар»).",
            },
            {
                "case_name": "Ra / Rb",
                "probability_fraction": "1/18 (каждый)",
                "probability_percent_text": "5.56%",
                "states_out_of_96_text": "4 + 4",
                "recognition_dod": "Блок 1x1x2 + «Фонари» (Headlights).",
            },
            {
                "case_name": "F",
                "probability_fraction": "1/18",
                "probability_percent_text": "5.56%",
                "states_out_of_96_text": "4",
                "recognition_dod": "Один длинный блок 1x1x3 на одной стороне.",
            },
        ],
    },
    {
        "set_code": "diagonal_swap",
        "title": "Diagonal Swap",
        "items": [
            {
                "case_name": "V",
                "probability_fraction": "1/18",
                "probability_percent_text": "5.56%",
                "states_out_of_96_text": "4",
                "recognition_dod": "Блок 2x2x1 («Квадрат»).",
            },
            {
                "case_name": "Y",
                "probability_fraction": "1/18",
                "probability_percent_text": "5.56%",
                "states_out_of_96_text": "4",
                "recognition_dod": "Два блока 1x1x2 под углом 90°.",
            },
            {
                "case_name": "Na / Nb",
                "probability_fraction": "1/72 (каждый)",
                "probability_percent_text": "1.39%",
                "states_out_of_96_text": "1 + 1",
                "recognition_dod": "Два блока 1x1x3 на противоположных сторонах.",
            },
        ],
    },
    {
        "set_code": "g_perms",
        "title": "G-Perms",
        "items": [
            {
                "case_name": "Ga / Gb / Gc / Gd",
                "probability_fraction": "1/12 (каждый)",
                "probability_percent_text": "8.33%",
                "states_out_of_96_text": "8 + 8 + 8 + 8",
                "recognition_dod": "Блок 1x1x2 + «Фонари» на смежной грани.",
            },
        ],
    },
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_root_from_file() -> Path:
    return Path(__file__).resolve().parents[2]


def runtime_dir(repo_root: Path | None = None) -> Path:
    root = repo_root or repo_root_from_file()
    return root / "data" / "cards" / "runtime"


def default_db_path(repo_root: Path | None = None) -> Path:
    return runtime_dir(repo_root) / "cards.db"


def schema_path(repo_root: Path | None = None) -> Path:
    root = repo_root or repo_root_from_file()
    return root / "db" / "cards_schema.sql"


def seed_cases_path(repo_root: Path | None = None) -> Path:
    root = repo_root or repo_root_from_file()
    return root / "data" / "cards" / "seed_cases.json"


def pll_algorithms_path(repo_root: Path | None = None) -> Path:
    root = repo_root or repo_root_from_file()
    return root / "pll.txt"


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
        conn.commit()
    finally:
        conn.close()


def initialize_database(repo_root: Path | None = None, db_path: Path | None = None) -> Path:
    root = repo_root or repo_root_from_file()
    path = db_path or default_db_path(root)
    sql = schema_path(root).read_text(encoding="utf-8")

    with connect(path) as conn:
        conn.executescript(sql)
        _apply_schema_migrations(conn)

    seed_defaults(repo_root=root, db_path=path)
    return path


def _seed_categories(conn: sqlite3.Connection) -> None:
    categories = [
        ("F2L", "F2L", 1, 10),
        ("OLL", "OLL", 1, 20),
        ("PLL", "PLL", 1, 30),
    ]
    conn.executemany(
        """
        INSERT OR IGNORE INTO categories (code, title, enabled, sort_order)
        VALUES (?, ?, ?, ?)
        """,
        categories,
    )


def _extract_case_number(case_code: str) -> int | None:
    suffix = case_code.rsplit("_", 1)[-1]
    if suffix.isdigit():
        return int(suffix)
    return None


def _resolve_case_metadata(category: str, case_code: str) -> dict[str, Any]:
    number = _extract_case_number(case_code)
    subgroup: str | None = None
    probability: str | None = None

    if category == "OLL" and number is not None:
        subgroup = "OLL Cases"
        for title, numbers in _OLL_SUBGROUPS.items():
            if number in numbers:
                subgroup = title
                break
        probability = _OLL_PROBABILITY_OVERRIDES.get(number, "1/54")
        title = f"OLL {number}"
    elif category == "PLL" and number is not None:
        subgroup = "PLL Cases"
        for title_candidate, numbers in _PLL_SUBGROUPS.items():
            if number in numbers:
                subgroup = title_candidate
                break
        probability = _PLL_PROBABILITY_BY_NUMBER.get(number)
        title = f"PLL {number}"
    elif category == "F2L" and number is not None:
        subgroup = "F2L Cases"
        title = f"F2L {number}"
    else:
        subgroup = f"{category} Cases"
        title = case_code

    return {
        "title": title,
        "subgroup_title": subgroup,
        "case_number": number,
        "probability_text": probability,
    }


def _iter_seed_cases(root: Path | None = None) -> Iterator[tuple[str, str]]:
    path = seed_cases_path(root)
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload.get("categories", []):
            code = str(item["code"])
            prefix = str(item.get("prefix", f"{code}_"))
            count = int(item["count"])
            for idx in range(1, count + 1):
                case_code = f"{prefix}{idx}"
                yield code, case_code
        return

    for idx in range(1, 11):
        yield "F2L", f"F2L_{idx}"

    for idx in range(1, 58):
        yield "OLL", f"OLL_{idx}"

    for idx in range(1, 22):
        yield "PLL", f"PLL_{idx}"


_KNOWN_FORMULAS = {
    "F2L_1": "R U R' U'",
    "OLL_1": "R U2 R2 F R F' U2 R' F R F'",
    "OLL_27": "R U R' U R U2 R'",
    "OLL_26": "R U2 R' U' R U' R'",
    "PLL_1": "M2 U M U2 M' U M2",
    "PLL_2": "M2 U' M U2 M' U' M2",
    "PLL_3": "R' U R' d' R' F' R2 U' R' U R' F R F",
}


def _load_pll_algorithms(root: Path | None = None) -> dict[str, dict[str, str]]:
    path = pll_algorithms_path(root)
    if not path.exists():
        return {}

    rows = csv.reader(path.read_text(encoding="utf-8-sig").splitlines())
    mapping: dict[str, dict[str, str]] = {}

    for row in rows:
        if len(row) < 3:
            continue
        raw_index = row[0].strip()
        if raw_index in {"", "№"}:
            continue
        if not raw_index.isdigit():
            continue

        case_code = f"PLL_{int(raw_index)}"
        mapping[case_code] = {
            "name": row[1].strip(),
            "formula": " ".join(row[2].split()),
        }

    return mapping


def seed_defaults(repo_root: Path | None = None, db_path: Path | None = None) -> None:
    root = repo_root or repo_root_from_file()
    path = db_path or default_db_path(root)
    run_dir = path.parent if db_path is not None else runtime_dir(root)
    run_dir.mkdir(parents=True, exist_ok=True)
    pll_algorithms = _load_pll_algorithms(root)
    known_formulas = dict(_KNOWN_FORMULAS)
    for case_code, payload in pll_algorithms.items():
        formula = payload.get("formula", "").strip()
        if formula:
            known_formulas[case_code] = formula

    with connect(path) as conn:
        _seed_categories(conn)
        _seed_reference_probabilities(conn)

        for category, case_code in _iter_seed_cases(root):
            metadata = _resolve_case_metadata(category, case_code)
            formula_for_case = known_formulas.get(case_code, "")
            recognizer = ensure_recognizer_assets(
                run_dir,
                category,
                case_code,
                formula=formula_for_case,
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO cases (
                    category_code,
                    case_code,
                    title,
                    subgroup_title,
                    case_number,
                    probability_text,
                    orientation_front,
                    orientation_auf,
                    recognizer_svg_path,
                    recognizer_png_path
                )
                VALUES (?, ?, ?, ?, ?, ?, 'F', 0, ?, ?)
                """,
                (
                    category,
                    case_code,
                    metadata["title"],
                    metadata["subgroup_title"],
                    metadata["case_number"],
                    metadata["probability_text"],
                    recognizer.svg_rel_path,
                    recognizer.png_rel_path,
                ),
            )
            conn.execute(
                """
                UPDATE cases
                SET
                    title = ?,
                    subgroup_title = ?,
                    case_number = ?,
                    probability_text = ?,
                    recognizer_svg_path = ?,
                    recognizer_png_path = COALESCE(?, recognizer_png_path)
                WHERE category_code = ? AND case_code = ?
                """,
                (
                    metadata["title"],
                    metadata["subgroup_title"],
                    metadata["case_number"],
                    metadata["probability_text"],
                    recognizer.svg_rel_path,
                    recognizer.png_rel_path,
                    category,
                    case_code,
                ),
            )

        now = utc_now_iso()
        rows = conn.execute("SELECT id, case_code FROM cases").fetchall()
        for row in rows:
            case_id = int(row["id"])
            case_code = str(row["case_code"])
            formula = known_formulas.get(case_code, "")
            conn.execute(
                """
                INSERT OR IGNORE INTO algorithms (
                    case_id,
                    name,
                    formula,
                    progress_status,
                    is_custom,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, 'NEW', 0, ?, ?)
                """,
                (case_id, case_code, formula, now, now),
            )
            conn.execute(
                """
                UPDATE algorithms
                SET formula = ?, updated_at = ?
                WHERE case_id = ? AND name = ? AND is_custom = 0
                """,
                (formula, now, case_id, case_code),
            )
            default_algo = conn.execute(
                """
                SELECT id
                FROM algorithms
                WHERE case_id = ?
                ORDER BY is_custom ASC, id ASC
                LIMIT 1
                """,
                (case_id,),
            ).fetchone()
            if default_algo is not None:
                conn.execute(
                    """
                    UPDATE cases
                    SET selected_algorithm_id = COALESCE(selected_algorithm_id, ?)
                    WHERE id = ?
                    """,
                    (int(default_algo["id"]), case_id),
                )


def _column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(str(row["name"]) == column_name for row in rows)


def _apply_schema_migrations(conn: sqlite3.Connection) -> None:
    if not _column_exists(conn, "cases", "subgroup_title"):
        conn.execute("ALTER TABLE cases ADD COLUMN subgroup_title TEXT")
    if not _column_exists(conn, "cases", "case_number"):
        conn.execute("ALTER TABLE cases ADD COLUMN case_number INTEGER")
    if not _column_exists(conn, "cases", "probability_text"):
        conn.execute("ALTER TABLE cases ADD COLUMN probability_text TEXT")
    if not _column_exists(conn, "cases", "selected_algorithm_id"):
        conn.execute("ALTER TABLE cases ADD COLUMN selected_algorithm_id INTEGER")


def _parse_percent_value(text: str) -> float | None:
    normalized = text.strip().replace("%", "")
    try:
        return float(normalized)
    except ValueError:
        return None


def _seed_reference_probabilities(conn: sqlite3.Connection) -> None:
    for set_index, item in enumerate(_PLL_REFERENCE_SETS):
        conn.execute(
            """
            INSERT OR IGNORE INTO reference_case_sets (
                category_code,
                set_code,
                title,
                sort_order
            )
            VALUES ('PLL', ?, ?, ?)
            """,
            (item["set_code"], item["title"], set_index),
        )
        conn.execute(
            """
            UPDATE reference_case_sets
            SET title = ?, sort_order = ?
            WHERE category_code = 'PLL' AND set_code = ?
            """,
            (item["title"], set_index, item["set_code"]),
        )
        set_row = conn.execute(
            """
            SELECT id
            FROM reference_case_sets
            WHERE category_code = 'PLL' AND set_code = ?
            """,
            (item["set_code"],),
        ).fetchone()
        if set_row is None:
            raise RuntimeError(f"Could not resolve reference set: {item['set_code']}")
        set_id = int(set_row["id"])

        for case_index, case_item in enumerate(item["items"]):
            probability_text = case_item["probability_percent_text"]
            conn.execute(
                """
                INSERT OR IGNORE INTO reference_case_stats (
                    set_id,
                    case_name,
                    probability_fraction,
                    probability_percent_text,
                    probability_percent,
                    states_out_of_96_text,
                    recognition_dod,
                    sort_order
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    set_id,
                    case_item["case_name"],
                    case_item["probability_fraction"],
                    probability_text,
                    _parse_percent_value(probability_text),
                    case_item["states_out_of_96_text"],
                    case_item["recognition_dod"],
                    case_index,
                ),
            )
            conn.execute(
                """
                UPDATE reference_case_stats
                SET
                    probability_fraction = ?,
                    probability_percent_text = ?,
                    probability_percent = ?,
                    states_out_of_96_text = ?,
                    recognition_dod = ?,
                    sort_order = ?
                WHERE set_id = ? AND case_name = ?
                """,
                (
                    case_item["probability_fraction"],
                    probability_text,
                    _parse_percent_value(probability_text),
                    case_item["states_out_of_96_text"],
                    case_item["recognition_dod"],
                    case_index,
                    set_id,
                    case_item["case_name"],
                ),
            )
