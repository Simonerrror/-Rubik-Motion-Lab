from __future__ import annotations

import csv
import sqlite3
import json
import re
import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Any

from cubeanim.cards.recognizer import ensure_recognizer_assets

DEFAULT_DB_ENV = "CUBEANIM_CARDS_DB"


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

_PLL_REQUIRED_HEADER = ("№", "Название", "Алгоритм", "Группа", "Вероятность")
_OLL_REQUIRED_HEADER = ("№", "Название", "Алгоритм", "Группа", "Вероятность")
_OLL_EXPECTED_CASES = 57
_FRACTION_PATTERN = re.compile(r"^\d+/\d+$")


@dataclass(frozen=True)
class OLLSeedCase:
    case_code: str
    case_number: int
    case_title: str
    formula: str
    subgroup_title: str
    probability_text: str


@dataclass(frozen=True)
class PLLSeedCase:
    case_code: str
    case_number: int
    case_title: str
    algorithm_name: str
    formula: str
    subgroup_title: str
    probability_text: str


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


def oll_algorithms_path(repo_root: Path | None = None) -> Path:
    root = repo_root or repo_root_from_file()
    return root / "oll.txt"


def pll_algorithms_path(repo_root: Path | None = None) -> Path:
    root = repo_root or repo_root_from_file()
    return root / "pll.txt"


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


def _resolve_case_metadata(
    category: str,
    case_code: str,
) -> dict[str, Any]:
    number = _extract_case_number(case_code)
    subgroup: str | None = None
    probability: str | None = None

    if category == "F2L" and number is not None:
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


def _iter_seed_cases(root: Path | None = None, include_pll: bool = True) -> Iterator[tuple[str, str]]:
    path = seed_cases_path(root)
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload.get("categories", []):
            code = str(item["code"])
            if code == "PLL" and not include_pll:
                continue
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

    if include_pll:
        for idx in range(1, 22):
            yield "PLL", f"PLL_{idx}"


_KNOWN_FORMULAS = {
    "F2L_1": "R U R' U'",
}


def _fraction_from_probability(raw_probability: str, source: str, row_number: int) -> str:
    clean = raw_probability.strip()
    if not clean:
        raise ValueError(f"{source} row {row_number}: empty probability")
    fraction = clean.split(maxsplit=1)[0]
    if not _FRACTION_PATTERN.fullmatch(fraction):
        raise ValueError(
            f"{source} row {row_number}: probability must start with fraction X/Y, got '{raw_probability}'"
        )
    return fraction


def _parse_oll_seed_row(row: list[str], row_number: int) -> OLLSeedCase:
    if len(row) < 5:
        raise ValueError(f"oll.txt row {row_number}: expected 5 columns, got {len(row)}")

    raw_index = row[0].strip()
    if not raw_index.isdigit():
        raise ValueError(f"oll.txt row {row_number}: invalid case number '{raw_index}'")

    case_number = int(raw_index)
    raw_name = row[1].strip()
    if not raw_name:
        raise ValueError(f"oll.txt row {row_number}: empty name")

    formula = _norm_formula(str(row[2]))
    if not formula:
        raise ValueError(f"oll.txt row {row_number}: empty formula")

    subgroup = row[3].strip()
    if not subgroup:
        raise ValueError(f"oll.txt row {row_number}: empty group")

    probability = _fraction_from_probability(row[4], source="oll.txt", row_number=row_number)
    return OLLSeedCase(
        case_code=f"OLL_{case_number}",
        case_number=case_number,
        case_title=f"OLL #{case_number}",
        formula=formula,
        subgroup_title=subgroup,
        probability_text=probability,
    )


def _load_oll_seed_cases(root: Path | None = None) -> dict[str, OLLSeedCase]:
    path = oll_algorithms_path(root)
    if not path.exists():
        raise FileNotFoundError(f"Required OLL source not found: {path}")

    rows = list(csv.reader(path.read_text(encoding="utf-8-sig").splitlines()))
    if not rows:
        raise ValueError("oll.txt is empty")

    header = tuple(cell.strip() for cell in rows[0][:5])
    if header != _OLL_REQUIRED_HEADER:
        raise ValueError(
            "oll.txt header mismatch. "
            f"Expected {list(_OLL_REQUIRED_HEADER)}, got {list(header)}"
        )

    mapping: dict[str, OLLSeedCase] = {}
    for index, row in enumerate(rows[1:], start=2):
        if not row or not "".join(row).strip():
            continue
        parsed = _parse_oll_seed_row(row=row, row_number=index)
        if parsed.case_code in mapping:
            raise ValueError(f"oll.txt duplicate case number for {parsed.case_code}")
        mapping[parsed.case_code] = parsed

    expected_codes = {f"OLL_{number}" for number in range(1, _OLL_EXPECTED_CASES + 1)}
    found_codes = set(mapping.keys())
    missing = sorted(expected_codes - found_codes, key=lambda item: int(item.split("_")[1]))
    extra = sorted(found_codes - expected_codes, key=lambda item: int(item.split("_")[1]))
    if missing or extra:
        raise ValueError(
            "oll.txt must provide complete OLL_1..OLL_57 set. "
            f"Missing: {missing or 'none'}; Extra: {extra or 'none'}"
        )
    return mapping


def _pll_display_name(name: str) -> str:
    clean = name.strip()
    if not clean:
        raise ValueError("PLL row has empty name")
    lowered = clean.lower()
    if lowered.endswith("-perm") or lowered.endswith(" perm"):
        return clean
    return f"{clean}-perm"


def _pll_probability_fraction(raw_probability: str, row_number: int) -> str:
    return _fraction_from_probability(raw_probability, source="pll.txt", row_number=row_number)


def _norm_formula(formula: str) -> str:
    return " ".join(formula.split())


def _parse_pll_seed_row(row: list[str], row_number: int) -> PLLSeedCase:
    if len(row) < 5:
        raise ValueError(f"pll.txt row {row_number}: expected 5 columns, got {len(row)}")

    raw_index = row[0].strip()
    if not raw_index.isdigit():
        raise ValueError(f"pll.txt row {row_number}: invalid case number '{raw_index}'")

    case_number = int(raw_index)
    raw_name = row[1].strip()
    formula = " ".join(row[2].split())
    subgroup = row[3].strip()
    probability = _pll_probability_fraction(row[4], row_number=row_number)
    if not formula:
        raise ValueError(f"pll.txt row {row_number}: empty formula")
    if not subgroup:
        raise ValueError(f"pll.txt row {row_number}: empty group")

    return PLLSeedCase(
        case_code=f"PLL_{case_number}",
        case_number=case_number,
        case_title=_pll_display_name(raw_name),
        algorithm_name=raw_name,
        formula=formula,
        subgroup_title=subgroup,
        probability_text=probability,
    )


def _load_pll_seed_cases(root: Path | None = None) -> dict[str, PLLSeedCase]:
    path = pll_algorithms_path(root)
    if not path.exists():
        raise FileNotFoundError(f"Required PLL source not found: {path}")

    rows = list(csv.reader(path.read_text(encoding="utf-8-sig").splitlines()))
    if not rows:
        raise ValueError("pll.txt is empty")

    header = tuple(cell.strip() for cell in rows[0][:5])
    if header != _PLL_REQUIRED_HEADER:
        raise ValueError(
            "pll.txt header mismatch. "
            f"Expected {list(_PLL_REQUIRED_HEADER)}, got {list(header)}"
        )

    mapping: dict[str, PLLSeedCase] = {}
    for index, row in enumerate(rows[1:], start=2):
        if not row or not "".join(row).strip():
            continue
        parsed = _parse_pll_seed_row(row=row, row_number=index)
        if parsed.case_code in mapping:
            raise ValueError(f"pll.txt duplicate case number for {parsed.case_code}")
        mapping[parsed.case_code] = parsed

    if not mapping:
        raise ValueError("pll.txt does not contain data rows")
    return mapping


def _cleanup_algorithm_dependencies(conn: sqlite3.Connection, algorithm_id: int) -> None:
    conn.execute("DELETE FROM render_jobs WHERE algorithm_id = ?", (algorithm_id,))
    conn.execute("DELETE FROM render_artifacts WHERE algorithm_id = ?", (algorithm_id,))


def _cleanup_stale_noncustom_pll_algorithms(
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


def _cleanup_stale_artifacts_for_formula(
    conn: sqlite3.Connection,
    algorithm_id: int,
    formula: str,
) -> None:
    formula_norm = _norm_formula(formula)
    conn.execute(
        """
        DELETE FROM render_artifacts
        WHERE algorithm_id = ?
          AND formula_norm != ?
        """,
        (algorithm_id, formula_norm),
    )


def seed_defaults(repo_root: Path | None = None, db_path: Path | None = None) -> None:
    root = repo_root or repo_root_from_file()
    path = db_path or default_db_path(root)
    run_dir = path.parent if db_path is not None else runtime_dir(root)
    run_dir.mkdir(parents=True, exist_ok=True)
    oll_cases = _load_oll_seed_cases(root)
    pll_cases = _load_pll_seed_cases(root)
    known_formulas = dict(_KNOWN_FORMULAS)
    for case_code, payload in oll_cases.items():
        known_formulas[case_code] = payload.formula
    for case_code, payload in pll_cases.items():
        known_formulas[case_code] = payload.formula

    with connect(path) as conn:
        _seed_categories(conn)
        _seed_reference_probabilities(conn)

        for category, case_code in _iter_seed_cases(root, include_pll=False):
            if category == "OLL":
                if case_code not in oll_cases:
                    raise ValueError(
                        f"seed_cases declares {case_code}, but oll.txt does not provide it"
                    )
                oll_case = oll_cases[case_code]
                metadata = {
                    "title": oll_case.case_title,
                    "subgroup_title": oll_case.subgroup_title,
                    "case_number": oll_case.case_number,
                    "probability_text": oll_case.probability_text,
                }
                formula_for_case = oll_case.formula
            else:
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

        for pll_case in sorted(pll_cases.values(), key=lambda item: item.case_number):
            recognizer = ensure_recognizer_assets(
                run_dir,
                "PLL",
                pll_case.case_code,
                formula=pll_case.formula,
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
                VALUES ('PLL', ?, ?, ?, ?, ?, 'F', 0, ?, ?)
                """,
                (
                    pll_case.case_code,
                    pll_case.case_title,
                    pll_case.subgroup_title,
                    pll_case.case_number,
                    pll_case.probability_text,
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
                WHERE category_code = 'PLL' AND case_code = ?
                """,
                (
                    pll_case.case_title,
                    pll_case.subgroup_title,
                    pll_case.case_number,
                    pll_case.probability_text,
                    recognizer.svg_rel_path,
                    recognizer.png_rel_path,
                    pll_case.case_code,
                ),
            )

        now = utc_now_iso()
        rows = conn.execute("SELECT id, case_code, category_code FROM cases").fetchall()
        for row in rows:
            case_id = int(row["id"])
            case_code = str(row["case_code"])
            category_code = str(row["category_code"])
            formula = known_formulas.get(case_code, "")
            if category_code == "OLL" and not formula:
                raise ValueError(f"OLL case {case_code} has empty canonical formula")
            default_algorithm_name = case_code
            if category_code == "PLL" and case_code in pll_cases:
                default_algorithm_name = pll_cases[case_code].algorithm_name
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
                (case_id, default_algorithm_name, formula, now, now),
            )
            conn.execute(
                """
                UPDATE algorithms
                SET formula = ?, updated_at = ?
                WHERE case_id = ? AND name = ? AND is_custom = 0
                """,
                (formula, now, case_id, default_algorithm_name),
            )
            canonical_noncustom_id: int | None = None
            if category_code == "PLL" and case_code in pll_cases:
                canonical_noncustom_id = _cleanup_stale_noncustom_pll_algorithms(
                    conn,
                    case_id=case_id,
                    canonical_name=default_algorithm_name,
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
                default_algo_id = int(default_algo["id"])
                if canonical_noncustom_id is not None:
                    default_algo_id = canonical_noncustom_id
                conn.execute(
                    """
                    UPDATE cases
                    SET selected_algorithm_id = COALESCE(selected_algorithm_id, ?)
                    WHERE id = ?
                    """,
                    (default_algo_id, case_id),
                )
                _cleanup_stale_artifacts_for_formula(
                    conn,
                    algorithm_id=default_algo_id,
                    formula=formula,
                )
            active = conn.execute(
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
            if active is not None:
                active_formula = str(active["formula"] or "")
                recognizer = ensure_recognizer_assets(
                    run_dir,
                    str(active["category_code"]),
                    str(active["case_code"]),
                    formula=active_formula,
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
