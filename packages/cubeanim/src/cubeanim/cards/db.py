from __future__ import annotations

import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from cubeanim.cards.recognizer import ensure_recognizer_assets

DEFAULT_DB_ENV = "CUBEANIM_CARDS_DB"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_root_from_file() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "db" / "cards" / "schema.sql").exists():
            return parent
    raise RuntimeError("Could not resolve repository root from cubeanim.cards.db")


def runtime_dir(repo_root: Path | None = None) -> Path:
    root = repo_root or repo_root_from_file()
    return root / "data" / "cards" / "runtime"


def default_db_path(repo_root: Path | None = None) -> Path:
    return runtime_dir(repo_root) / "cards.db"


def schema_path(repo_root: Path | None = None) -> Path:
    root = repo_root or repo_root_from_file()
    return root / "db" / "cards" / "schema.sql"


def seed_sql_path(repo_root: Path | None = None) -> Path:
    root = repo_root or repo_root_from_file()
    return root / "db" / "cards" / "seed.sql"


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 30000")
        yield conn
        conn.commit()
    finally:
        conn.close()


def initialize_database(repo_root: Path | None = None, db_path: Path | None = None) -> Path:
    root = repo_root or repo_root_from_file()
    path = db_path or default_db_path(root)

    with connect(path) as conn:
        conn.executescript(schema_path(root).read_text(encoding="utf-8"))
        _apply_schema_migrations(conn)
        conn.executescript(seed_sql_path(root).read_text(encoding="utf-8"))

    seed_defaults(repo_root=root, db_path=path)
    return path


def seed_defaults(repo_root: Path | None = None, db_path: Path | None = None) -> None:
    root = repo_root or repo_root_from_file()
    path = db_path or default_db_path(root)
    run_dir = path.parent if db_path is not None else runtime_dir(root)
    run_dir.mkdir(parents=True, exist_ok=True)

    with connect(path) as conn:
        _materialize_runtime_from_canonical(conn, run_dir)


def _materialize_runtime_from_canonical(conn: sqlite3.Connection, run_dir: Path) -> None:
    case_rows = conn.execute(
        """
        SELECT
            cc.id AS canonical_case_id,
            cc.category_code,
            cc.case_code,
            cc.title,
            cc.subgroup_title,
            cc.case_number,
            cc.probability_text,
            cc.orientation_front,
            cc.orientation_auf,
            cc.sort_order
        FROM canonical_cases cc
        ORDER BY cc.category_code ASC, cc.sort_order ASC, cc.case_number ASC, cc.case_code ASC
        """
    ).fetchall()
    if not case_rows:
        raise ValueError("canonical_cases is empty; check db/cards/seed.sql")

    now = utc_now_iso()

    canonical_f2l_codes = {
        str(row["case_code"])
        for row in case_rows
        if str(row["category_code"]) == "F2L"
    }
    if canonical_f2l_codes:
        placeholders = ",".join(["?"] * len(canonical_f2l_codes))
        params = ("F2L", *sorted(canonical_f2l_codes))
        stale_cases_sql = f"SELECT id FROM cases WHERE category_code = ? AND case_code NOT IN ({placeholders})"
        stale_algorithms_sql = f"SELECT id FROM algorithms WHERE case_id IN ({stale_cases_sql})"
        conn.execute(
            f"UPDATE cases SET selected_algorithm_id = NULL WHERE id IN ({stale_cases_sql})",
            params,
        )
        conn.execute(
            f"DELETE FROM algorithms WHERE id IN ({stale_algorithms_sql})",
            params,
        )
        conn.execute(
            f"DELETE FROM cases WHERE id IN ({stale_cases_sql})",
            params,
        )

    for row in case_rows:
        category = str(row["category_code"])
        case_code = str(row["case_code"])
        title = str(row["title"])
        subgroup_title = row["subgroup_title"]
        case_number = row["case_number"]
        probability_text = row["probability_text"]
        orientation_front = str(row["orientation_front"] or "F")
        orientation_auf = int(row["orientation_auf"] or 0)
        canonical_case_id = int(row["canonical_case_id"])

        algo_rows = conn.execute(
            """
            SELECT
                name,
                formula,
                is_primary,
                sort_order
            FROM canonical_algorithms
            WHERE canonical_case_id = ?
            ORDER BY is_primary DESC, sort_order ASC, id ASC
            """,
            (canonical_case_id,),
        ).fetchall()

        canonical_algorithms: list[tuple[str, str, bool, int]] = []
        for algo_row in algo_rows:
            name = str(algo_row["name"] or case_code).strip() or case_code
            formula = " ".join(str(algo_row["formula"] or "").split())
            is_primary = bool(algo_row["is_primary"])
            sort_order = int(algo_row["sort_order"] or 0)
            canonical_algorithms.append((name, formula, is_primary, sort_order))

        if not canonical_algorithms:
            canonical_algorithms = [(case_code, "", True, 1)]

        primary = next((item for item in canonical_algorithms if item[2]), canonical_algorithms[0])
        primary_name, primary_formula, _, _ = primary

        recognizer = ensure_recognizer_assets(run_dir, category, case_code, formula=primary_formula)

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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                category,
                case_code,
                title,
                subgroup_title,
                case_number,
                probability_text,
                orientation_front,
                orientation_auf,
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
                orientation_front = ?,
                orientation_auf = ?,
                recognizer_svg_path = ?,
                recognizer_png_path = COALESCE(?, recognizer_png_path)
            WHERE category_code = ? AND case_code = ?
            """,
            (
                title,
                subgroup_title,
                case_number,
                probability_text,
                orientation_front,
                orientation_auf,
                recognizer.svg_rel_path,
                recognizer.png_rel_path,
                category,
                case_code,
            ),
        )

        case_row = conn.execute(
            "SELECT id FROM cases WHERE category_code = ? AND case_code = ?",
            (category, case_code),
        ).fetchone()
        if case_row is None:
            raise RuntimeError(f"Could not resolve case: {category}:{case_code}")
        case_id = int(case_row["id"])

        canonical_names = [name for name, _, _, _ in canonical_algorithms]
        for name, formula, _, _ in canonical_algorithms:
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
                (case_id, name, formula, now, now),
            )
            conn.execute(
                """
                UPDATE algorithms
                SET formula = ?, updated_at = ?
                WHERE case_id = ? AND name = ? AND is_custom = 0
                """,
                (formula, now, case_id, name),
            )

        keep_placeholders = ",".join(["?"] * len(canonical_names))
        stale_rows = conn.execute(
            f"""
            SELECT id
            FROM algorithms
            WHERE case_id = ? AND is_custom = 0 AND name NOT IN ({keep_placeholders})
            """,
            (case_id, *canonical_names),
        ).fetchall()
        stale_ids = [int(item["id"]) for item in stale_rows]
        if stale_ids:
            id_placeholders = ",".join(["?"] * len(stale_ids))
            conn.execute(
                f"""
                UPDATE cases
                SET selected_algorithm_id = NULL
                WHERE id = ? AND selected_algorithm_id IN ({id_placeholders})
                """,
                (case_id, *stale_ids),
            )
            conn.execute(
                f"DELETE FROM algorithms WHERE id IN ({id_placeholders})",
                tuple(stale_ids),
            )

        primary_row = conn.execute(
            """
            SELECT id
            FROM algorithms
            WHERE case_id = ? AND name = ? AND is_custom = 0
            """,
            (case_id, primary_name),
        ).fetchone()
        primary_algorithm_id = int(primary_row["id"]) if primary_row is not None else None

        selected_row = conn.execute(
            "SELECT selected_algorithm_id FROM cases WHERE id = ?",
            (case_id,),
        ).fetchone()
        selected_algorithm_id = selected_row["selected_algorithm_id"] if selected_row is not None else None
        selected_valid = False
        if selected_algorithm_id is not None:
            existing = conn.execute(
                "SELECT 1 FROM algorithms WHERE id = ? AND case_id = ?",
                (int(selected_algorithm_id), case_id),
            ).fetchone()
            selected_valid = existing is not None

        if primary_algorithm_id is not None and (selected_algorithm_id is None or not selected_valid):
            conn.execute(
                "UPDATE cases SET selected_algorithm_id = ? WHERE id = ?",
                (primary_algorithm_id, case_id),
            )
        for name, formula, _, _ in canonical_algorithms:
            algo_row = conn.execute(
                """
                SELECT id
                FROM algorithms
                WHERE case_id = ? AND name = ? AND is_custom = 0
                """,
                (case_id, name),
            ).fetchone()
            if algo_row is None:
                continue

        _refresh_case_recognizer_by_active(conn, run_dir, case_id)


def _refresh_case_recognizer_by_active(conn: sqlite3.Connection, run_dir: Path, case_id: int) -> None:
    row = conn.execute(
        """
        SELECT
            c.category_code,
            c.case_code,
            a.formula
        FROM cases c
        LEFT JOIN algorithms a ON a.id = COALESCE(
            c.selected_algorithm_id,
            (
                SELECT aa.id
                FROM algorithms aa
                WHERE aa.case_id = c.id
                ORDER BY aa.is_custom ASC, aa.id ASC
                LIMIT 1
            )
        )
        WHERE c.id = ?
        """,
        (case_id,),
    ).fetchone()
    if row is None:
        return

    recognizer = ensure_recognizer_assets(
        run_dir,
        category=str(row["category_code"]),
        case_code=str(row["case_code"]),
        formula=str(row["formula"] or ""),
    )

    conn.execute(
        """
        UPDATE cases
        SET
            recognizer_svg_path = ?,
            recognizer_png_path = COALESCE(?, recognizer_png_path)
        WHERE id = ?
        """,
        (recognizer.svg_rel_path, recognizer.png_rel_path, case_id),
    )


def _cleanup_stale_noncustom_algorithms(
    conn: sqlite3.Connection,
    case_id: int,
    canonical_name: str,
) -> int | None:
    rows = conn.execute(
        """
        SELECT id, name
        FROM algorithms
        WHERE case_id = ? AND is_custom = 0
        ORDER BY id ASC
        """,
        (case_id,),
    ).fetchall()
    if not rows:
        return None

    canonical_id: int | None = None
    for row in rows:
        if str(row["name"]) == canonical_name:
            canonical_id = int(row["id"])
            break
    if canonical_id is None:
        canonical_id = int(rows[0]["id"])

    for row in rows:
        algorithm_id = int(row["id"])
        if algorithm_id == canonical_id:
            continue
        conn.execute(
            """
            UPDATE cases
            SET selected_algorithm_id = ?
            WHERE id = ? AND selected_algorithm_id = ?
            """,
            (canonical_id, case_id, algorithm_id),
        )
        _cleanup_algorithm_dependencies(conn, algorithm_id)
        conn.execute("DELETE FROM algorithms WHERE id = ?", (algorithm_id,))

    return canonical_id


def _cleanup_algorithm_dependencies(conn: sqlite3.Connection, algorithm_id: int) -> None:
    return None


def reset_runtime_state(repo_root: Path | None = None, db_path: Path | None = None) -> Path:
    root = repo_root or repo_root_from_file()
    path = db_path or default_db_path(root)
    recognizer_dir = path.parent / "recognizers"
    if path.exists():
        path.unlink()
    if recognizer_dir.exists():
        shutil.rmtree(recognizer_dir)
    return initialize_database(repo_root=root, db_path=path)


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
    conn.execute("DROP INDEX IF EXISTS idx_render_jobs_algorithm_quality")
    conn.execute("DROP INDEX IF EXISTS idx_render_jobs_status")
    conn.execute("DROP TABLE IF EXISTS render_jobs")
    conn.execute("DROP TABLE IF EXISTS render_artifacts")
