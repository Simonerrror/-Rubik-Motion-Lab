from __future__ import annotations

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


def seed_defaults(repo_root: Path | None = None, db_path: Path | None = None) -> None:
    root = repo_root or repo_root_from_file()
    path = db_path or default_db_path(root)
    run_dir = path.parent if db_path is not None else runtime_dir(root)
    run_dir.mkdir(parents=True, exist_ok=True)

    with connect(path) as conn:
        _seed_categories(conn)

        for category, case_code in _iter_seed_cases(root):
            metadata = _resolve_case_metadata(category, case_code)
            recognizer = ensure_recognizer_assets(run_dir, category, case_code)
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
            formula = _KNOWN_FORMULAS.get(case_code, "")
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
