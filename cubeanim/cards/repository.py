from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from cubeanim.cards.models import PROGRESS_STATUSES


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_formula(formula: str) -> str:
    return " ".join(formula.split())


def _algorithm_row_payload(row: sqlite3.Row) -> dict[str, Any]:
    recognizer_rel = row["recognizer_svg_path"] or row["recognizer_png_path"]
    recognizer_url = f"/assets/{recognizer_rel}" if recognizer_rel else None

    payload: dict[str, Any] = {
        "id": int(row["id"]),
        "name": row["name"],
        "formula": row["formula"],
        "group": row["category_code"],
        "case_code": row["case_code"],
        "status": row["progress_status"],
        "recognizer_url": recognizer_url,
    }
    if "case_id" in row.keys():
        payload["case_id"] = int(row["case_id"])
    if "case_title" in row.keys():
        payload["case_title"] = row["case_title"]
    if "subgroup_title" in row.keys():
        payload["subgroup_title"] = row["subgroup_title"]
    if "case_number" in row.keys():
        payload["case_number"] = row["case_number"]
    if "probability_text" in row.keys():
        payload["probability_text"] = row["probability_text"]
    if "is_custom" in row.keys():
        payload["is_custom"] = bool(row["is_custom"])
    return payload


def _case_payload(row: sqlite3.Row) -> dict[str, Any]:
    recognizer_rel = row["recognizer_svg_path"] or row["recognizer_png_path"]
    recognizer_url = f"/assets/{recognizer_rel}" if recognizer_rel else None
    return {
        "id": int(row["id"]),
        "group": row["category_code"],
        "case_code": row["case_code"],
        "title": row["title"],
        "subgroup_title": row["subgroup_title"] or f"{row['category_code']} Cases",
        "case_number": row["case_number"],
        "probability_text": row["probability_text"],
        "recognizer_url": recognizer_url,
        "active_algorithm_id": int(row["active_algorithm_id"]) if row["active_algorithm_id"] is not None else None,
        "active_algorithm_name": row["active_algorithm_name"],
        "active_formula": row["active_formula"] or "",
        "status": row["active_status"] or "NEW",
    }


def _resolve_case_selected_algorithm_id(conn: sqlite3.Connection, case_id: int) -> int | None:
    row = conn.execute(
        """
        SELECT
            COALESCE(
                selected_algorithm_id,
                (
                    SELECT a.id
                    FROM algorithms a
                    WHERE a.case_id = c.id
                    ORDER BY a.is_custom ASC, a.id ASC
                    LIMIT 1
                )
            ) AS selected_id
        FROM cases c
        WHERE c.id = ?
        """,
        (case_id,),
    ).fetchone()
    if row is None or row["selected_id"] is None:
        return None
    return int(row["selected_id"])


def list_algorithms(conn: sqlite3.Connection, group: str = "ALL") -> list[dict[str, Any]]:
    params: list[Any] = []
    where = ""
    if group != "ALL":
        where = "WHERE c.category_code = ?"
        params.append(group)

    rows = conn.execute(
        f"""
        SELECT
            a.id,
            a.case_id,
            a.name,
            a.formula,
            a.progress_status,
            a.is_custom,
            c.category_code,
            c.case_code,
            c.title AS case_title,
            c.subgroup_title,
            c.case_number,
            c.probability_text,
            c.recognizer_svg_path,
            c.recognizer_png_path
        FROM algorithms a
        JOIN cases c ON c.id = a.case_id
        {where}
        ORDER BY c.category_code, c.case_code, a.name
        """,
        params,
    ).fetchall()
    return [_algorithm_row_payload(row) for row in rows]


def get_algorithm(conn: sqlite3.Connection, algorithm_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT
            a.id,
            a.case_id,
            a.name,
            a.formula,
            a.progress_status,
            c.category_code,
            c.case_code,
            c.title AS case_title,
            c.subgroup_title,
            c.case_number,
            c.probability_text,
            c.recognizer_svg_path,
            c.recognizer_png_path,
            c.orientation_front,
            c.orientation_auf
        FROM algorithms a
        JOIN cases c ON c.id = a.case_id
        WHERE a.id = ?
        """,
        (algorithm_id,),
    ).fetchone()

    if row is None:
        return None

    payload = _algorithm_row_payload(row)
    payload["orientation_front"] = row["orientation_front"]
    payload["orientation_auf"] = int(row["orientation_auf"])
    return payload


def list_cases(conn: sqlite3.Connection, group: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            c.id,
            c.category_code,
            c.case_code,
            c.title,
            c.subgroup_title,
            c.case_number,
            c.probability_text,
            c.recognizer_svg_path,
            c.recognizer_png_path,
            sa.id AS active_algorithm_id,
            sa.name AS active_algorithm_name,
            sa.formula AS active_formula,
            sa.progress_status AS active_status
        FROM cases c
        LEFT JOIN algorithms sa ON sa.id = COALESCE(
            c.selected_algorithm_id,
            (
                SELECT a.id
                FROM algorithms a
                WHERE a.case_id = c.id
                ORDER BY a.is_custom ASC, a.id ASC
                LIMIT 1
            )
        )
        WHERE c.category_code = ?
        ORDER BY c.subgroup_title, c.case_number, c.case_code
        """,
        (group,),
    ).fetchall()
    return [_case_payload(row) for row in rows]


def list_case_algorithms(conn: sqlite3.Connection, case_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            a.id,
            a.case_id,
            a.name,
            a.formula,
            a.progress_status,
            a.is_custom,
            c.category_code,
            c.case_code,
            c.title AS case_title,
            c.subgroup_title,
            c.case_number,
            c.probability_text,
            c.recognizer_svg_path,
            c.recognizer_png_path
        FROM algorithms a
        JOIN cases c ON c.id = a.case_id
        WHERE a.case_id = ?
        ORDER BY a.id ASC
        """,
        (case_id,),
    ).fetchall()
    return [_algorithm_row_payload(row) for row in rows]


def list_reference_sets(conn: sqlite3.Connection, category: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            s.id AS set_id,
            s.category_code,
            s.set_code,
            s.title AS set_title,
            s.sort_order AS set_sort_order,
            st.id AS stat_id,
            st.case_name,
            st.probability_fraction,
            st.probability_percent_text,
            st.probability_percent,
            st.states_out_of_96_text,
            st.recognition_dod,
            st.sort_order AS stat_sort_order
        FROM reference_case_sets s
        LEFT JOIN reference_case_stats st ON st.set_id = s.id
        WHERE s.category_code = ?
        ORDER BY s.sort_order ASC, st.sort_order ASC
        """,
        (category,),
    ).fetchall()

    grouped: dict[int, dict[str, Any]] = {}
    for row in rows:
        set_id = int(row["set_id"])
        payload = grouped.get(set_id)
        if payload is None:
            payload = {
                "id": set_id,
                "category": row["category_code"],
                "set_code": row["set_code"],
                "title": row["set_title"],
                "sort_order": int(row["set_sort_order"]),
                "items": [],
            }
            grouped[set_id] = payload

        if row["stat_id"] is not None:
            payload["items"].append(
                {
                    "id": int(row["stat_id"]),
                    "case_name": row["case_name"],
                    "probability_fraction": row["probability_fraction"],
                    "probability_percent_text": row["probability_percent_text"],
                    "probability_percent": row["probability_percent"],
                    "states_out_of_96_text": row["states_out_of_96_text"],
                    "recognition_dod": row["recognition_dod"],
                    "sort_order": int(row["stat_sort_order"]),
                }
            )

    return list(grouped.values())


def get_case(conn: sqlite3.Connection, case_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT
            c.id,
            c.category_code,
            c.case_code,
            c.title,
            c.subgroup_title,
            c.case_number,
            c.probability_text,
            c.orientation_front,
            c.orientation_auf,
            c.recognizer_svg_path,
            c.recognizer_png_path,
            sa.id AS active_algorithm_id,
            sa.name AS active_algorithm_name,
            sa.formula AS active_formula,
            sa.progress_status AS active_status
        FROM cases c
        LEFT JOIN algorithms sa ON sa.id = COALESCE(
            c.selected_algorithm_id,
            (
                SELECT a.id
                FROM algorithms a
                WHERE a.case_id = c.id
                ORDER BY a.is_custom ASC, a.id ASC
                LIMIT 1
            )
        )
        WHERE c.id = ?
        """,
        (case_id,),
    ).fetchone()
    if row is None:
        return None

    payload = _case_payload(row)
    payload["orientation_front"] = row["orientation_front"]
    payload["orientation_auf"] = int(row["orientation_auf"])
    payload["algorithms"] = list_case_algorithms(conn, case_id=case_id)
    return payload


def _create_case_if_needed(
    conn: sqlite3.Connection,
    group: str,
    case_code: str,
    title: str,
) -> int:
    suffix = case_code.rsplit("_", 1)[-1]
    case_number = int(suffix) if suffix.isdigit() else None
    conn.execute(
        """
        INSERT OR IGNORE INTO cases (
            category_code,
            case_code,
            title,
            subgroup_title,
            case_number,
            orientation_front,
            orientation_auf
        )
        VALUES (?, ?, ?, ?, ?, 'F', 0)
        """,
        (group, case_code, title, f"{group} Cases", case_number),
    )
    row = conn.execute(
        "SELECT id FROM cases WHERE category_code = ? AND case_code = ?",
        (group, case_code),
    ).fetchone()
    if row is None:
        raise RuntimeError("Failed to create or resolve case")
    return int(row["id"])


def _next_custom_name(conn: sqlite3.Connection, case_id: int) -> str:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM algorithms WHERE case_id = ? AND is_custom = 1",
        (case_id,),
    ).fetchone()
    index = int(row["n"]) + 1 if row is not None else 1
    return f"Custom {index}"


def set_case_selected_algorithm(conn: sqlite3.Connection, case_id: int, algorithm_id: int) -> dict[str, Any]:
    row = conn.execute(
        "SELECT id FROM algorithms WHERE id = ? AND case_id = ?",
        (algorithm_id, case_id),
    ).fetchone()
    if row is None:
        raise KeyError("algorithm does not belong to case")
    conn.execute(
        "UPDATE cases SET selected_algorithm_id = ? WHERE id = ?",
        (algorithm_id, case_id),
    )
    updated = get_case(conn, case_id)
    if updated is None:
        raise KeyError(f"case id {case_id} not found")
    return updated


def create_custom_algorithm_for_case(
    conn: sqlite3.Connection,
    case_id: int,
    formula: str,
    name: str | None = None,
    activate: bool = True,
) -> dict[str, Any]:
    formula = _norm_formula(formula)
    if not formula:
        raise ValueError("formula must be non-empty")

    case_row = conn.execute(
        """
        SELECT id, category_code, case_code
        FROM cases
        WHERE id = ?
        """,
        (case_id,),
    ).fetchone()
    if case_row is None:
        raise KeyError(f"case id {case_id} not found")

    resolved_name = (name or "").strip() or _next_custom_name(conn, case_id)
    now = _utc_now_iso()
    conn.execute(
        """
        INSERT INTO algorithms (
            case_id,
            name,
            formula,
            progress_status,
            is_custom,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, 'NEW', 1, ?, ?)
        """,
        (case_id, resolved_name, formula, now, now),
    )
    row = conn.execute("SELECT last_insert_rowid() AS id").fetchone()
    if row is None:
        raise RuntimeError("Could not fetch inserted algorithm id")
    algorithm_id = int(row["id"])
    if activate:
        conn.execute(
            "UPDATE cases SET selected_algorithm_id = ? WHERE id = ?",
            (algorithm_id, case_id),
        )
    created = get_algorithm(conn, algorithm_id)
    if created is None:
        raise RuntimeError("Could not load inserted algorithm")
    return created


def create_custom_algorithm(
    conn: sqlite3.Connection,
    name: str,
    formula: str,
    group: str,
    case_code: str,
) -> dict[str, Any]:
    name = name.strip()
    if not name:
        raise ValueError("name must be non-empty")

    formula = _norm_formula(formula)
    if not formula:
        raise ValueError("formula must be non-empty")

    now = _utc_now_iso()
    case_id = _create_case_if_needed(conn, group=group, case_code=case_code, title=case_code)

    conn.execute(
        """
        INSERT INTO algorithms (
            case_id,
            name,
            formula,
            progress_status,
            is_custom,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, 'NEW', 1, ?, ?)
        """,
        (case_id, name, formula, now, now),
    )

    row = conn.execute("SELECT last_insert_rowid() AS id").fetchone()
    if row is None:
        raise RuntimeError("Could not fetch inserted algorithm id")
    algorithm_id = int(row["id"])
    conn.execute(
        "UPDATE cases SET selected_algorithm_id = ? WHERE id = ?",
        (algorithm_id, case_id),
    )
    return get_algorithm(conn, algorithm_id) or {}


def set_progress_status(conn: sqlite3.Connection, algorithm_id: int, status: str) -> None:
    if status not in PROGRESS_STATUSES:
        raise ValueError(f"status must be one of {sorted(PROGRESS_STATUSES)}")

    now = _utc_now_iso()
    cur = conn.execute(
        """
        UPDATE algorithms
        SET progress_status = ?, updated_at = ?
        WHERE id = ?
        """,
        (status, now, algorithm_id),
    )
    if cur.rowcount == 0:
        raise KeyError(f"algorithm id {algorithm_id} not found")


def get_render_artifact(
    conn: sqlite3.Connection,
    algorithm_id: int,
    quality: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT
            id,
            algorithm_id,
            quality,
            output_name,
            output_path,
            formula_norm,
            repeat,
            updated_at
        FROM render_artifacts
        WHERE algorithm_id = ? AND quality = ?
        """,
        (algorithm_id, quality),
    ).fetchone()
    if row is None:
        return None

    return {
        "id": int(row["id"]),
        "algorithm_id": int(row["algorithm_id"]),
        "quality": row["quality"],
        "output_name": row["output_name"],
        "output_path": row["output_path"],
        "formula_norm": row["formula_norm"],
        "repeat": int(row["repeat"]),
        "updated_at": row["updated_at"],
    }


def upsert_render_artifact(
    conn: sqlite3.Connection,
    algorithm_id: int,
    quality: str,
    output_name: str,
    output_path: str,
    formula_norm: str,
    repeat: int,
) -> None:
    now = _utc_now_iso()
    conn.execute(
        """
        INSERT INTO render_artifacts (
            algorithm_id,
            quality,
            output_name,
            output_path,
            formula_norm,
            repeat,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(algorithm_id, quality)
        DO UPDATE SET
            output_name = excluded.output_name,
            output_path = excluded.output_path,
            formula_norm = excluded.formula_norm,
            repeat = excluded.repeat,
            updated_at = excluded.updated_at
        """,
        (algorithm_id, quality, output_name, output_path, formula_norm, repeat, now),
    )


def get_active_job(
    conn: sqlite3.Connection,
    algorithm_id: int,
    quality: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT
            id,
            algorithm_id,
            target_quality,
            status,
            plan_action,
            output_name,
            output_path,
            error_message,
            created_at,
            started_at,
            finished_at
        FROM render_jobs
        WHERE algorithm_id = ?
          AND target_quality = ?
          AND status IN ('PENDING', 'RUNNING')
        ORDER BY id DESC
        LIMIT 1
        """,
        (algorithm_id, quality),
    ).fetchone()
    return _job_row(row) if row else None


def insert_render_job(
    conn: sqlite3.Connection,
    algorithm_id: int,
    quality: str,
    status: str = "PENDING",
    plan_action: str | None = None,
    output_name: str | None = None,
    output_path: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    now = _utc_now_iso()
    conn.execute(
        """
        INSERT INTO render_jobs (
            algorithm_id,
            target_quality,
            status,
            plan_action,
            output_name,
            output_path,
            error_message,
            created_at,
            started_at,
            finished_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
        """,
        (
            algorithm_id,
            quality,
            status,
            plan_action,
            output_name,
            output_path,
            error_message,
            now,
        ),
    )
    row = conn.execute("SELECT last_insert_rowid() AS id").fetchone()
    if row is None:
        raise RuntimeError("Could not fetch job id")
    job_id = int(row["id"])
    return get_job(conn, job_id)


def get_job(conn: sqlite3.Connection, job_id: int) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT
            id,
            algorithm_id,
            target_quality,
            status,
            plan_action,
            output_name,
            output_path,
            error_message,
            created_at,
            started_at,
            finished_at
        FROM render_jobs
        WHERE id = ?
        """,
        (job_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"job id {job_id} not found")
    return _job_row(row)


def list_latest_jobs_for_algorithm(conn: sqlite3.Connection, algorithm_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            id,
            algorithm_id,
            target_quality,
            status,
            plan_action,
            output_name,
            output_path,
            error_message,
            created_at,
            started_at,
            finished_at
        FROM render_jobs
        WHERE algorithm_id = ?
        ORDER BY id DESC
        LIMIT 20
        """,
        (algorithm_id,),
    ).fetchall()
    return [_job_row(row) for row in rows]


def claim_next_pending_job(conn: sqlite3.Connection) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT id
        FROM render_jobs
        WHERE status = 'PENDING'
        ORDER BY id ASC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return None

    job_id = int(row["id"])
    now = _utc_now_iso()
    cur = conn.execute(
        """
        UPDATE render_jobs
        SET status = 'RUNNING', started_at = ?
        WHERE id = ? AND status = 'PENDING'
        """,
        (now, job_id),
    )
    if cur.rowcount == 0:
        return None

    return get_job(conn, job_id)


def mark_job_done(
    conn: sqlite3.Connection,
    job_id: int,
    plan_action: str,
    output_name: str,
    output_path: str,
) -> dict[str, Any]:
    now = _utc_now_iso()
    conn.execute(
        """
        UPDATE render_jobs
        SET status = 'DONE',
            plan_action = ?,
            output_name = ?,
            output_path = ?,
            error_message = NULL,
            finished_at = ?
        WHERE id = ?
        """,
        (plan_action, output_name, output_path, now, job_id),
    )
    return get_job(conn, job_id)


def mark_job_failed(conn: sqlite3.Connection, job_id: int, error_message: str) -> dict[str, Any]:
    now = _utc_now_iso()
    conn.execute(
        """
        UPDATE render_jobs
        SET status = 'FAILED',
            error_message = ?,
            finished_at = ?
        WHERE id = ?
        """,
        (error_message, now, job_id),
    )
    return get_job(conn, job_id)


def _job_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "algorithm_id": int(row["algorithm_id"]),
        "quality": row["target_quality"],
        "status": row["status"],
        "plan_action": row["plan_action"],
        "output_name": row["output_name"],
        "output_path": row["output_path"],
        "error_message": row["error_message"],
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
    }
