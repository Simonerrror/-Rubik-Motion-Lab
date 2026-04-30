#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

def _repo_root_from_file() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "db" / "cards" / "schema.sql").exists():
            return parent
    raise RuntimeError("Could not resolve repository root for tools/import_f2l_pdf.py")


REPO_ROOT = _repo_root_from_file()
PACKAGE_SRC = REPO_ROOT / "packages" / "cubeanim" / "src"
for entry in (REPO_ROOT, PACKAGE_SRC):
    token = str(entry)
    if token not in sys.path:
        sys.path.insert(0, token)

from cubeanim.formula import FormulaConverter
from tools.algorithm_manifest import (
    normalize_manifest_payload,
    render_seed_sql_block,
    validate_manifest_for_import,
)

DEFAULT_PDF_PATH = REPO_ROOT / "Best F2L Algorithms.pdf"
DEFAULT_YAML_PATH = REPO_ROOT / "data" / "f2l" / "best_f2l_from_pdf.yaml"
DEFAULT_SEED_PATH = REPO_ROOT / "db" / "cards" / "seed.sql"

BEGIN_MARKER = "-- BEGIN PDF F2L"
END_MARKER = "-- END PDF F2L"

SUBGROUPS: tuple[tuple[str, str], ...] = (
    ("Basic F2L", "B"),
    ("Advanced F2L", "A"),
    ("Expert F2L", "E"),
)

SECTION_HEADINGS: dict[str, str] = {
    "Basic F2L": "Section 1: Basic F2L",
    "Advanced F2L": "Section 2: Advanced F2L",
    "Expert F2L": "Section 3: Expert F2L",
}

# These are explicit in the PDF headers.
EXPECTED_CASE_COUNTS: dict[str, int] = {
    "Basic F2L": 41,
    "Advanced F2L": 36,
}

_FORMULA_LINE_RE = re.compile(r"^[URFDLBMESxyzrludfb(]")


def _normalize_formula(formula: str) -> str:
    normalized = (
        str(formula)
        .replace("’", "'")
        .replace("‘", "'")
        .replace("`", "'")
        .replace("′", "'")
    )
    normalized = re.sub(r"2'+", "2", normalized)
    normalized = re.sub(r"\)\s*(\d+)\b", r")^\1", normalized)
    return " ".join(normalized.split())


def _try_parse_formula(candidate: str) -> str | None:
    normalized = _normalize_formula(candidate)
    if not normalized:
        return None
    try:
        FormulaConverter.convert_steps(normalized, repeat=1)
    except Exception:
        return None
    return normalized


def _lines_from_words(words: list[tuple]) -> list[str]:
    if not words:
        return []
    words = sorted(words, key=lambda w: (w[1], w[0]))

    lines: list[list[tuple]] = []
    current: list[tuple] = []
    current_y: float | None = None

    for word in words:
        y = float(word[1])
        if current and current_y is not None and abs(y - current_y) > 2.5:
            lines.append(current)
            current = [word]
            current_y = y
            continue

        if not current:
            current = [word]
            current_y = y
        else:
            current.append(word)

    if current:
        lines.append(current)

    return [" ".join(token[4] for token in line).strip() for line in lines if line]


def _dedup_preserve_order(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _extract_case_formulas_from_region(raw_lines: list[str]) -> list[str]:
    candidate_lines = [re.sub(r"\s+", " ", line).strip() for line in raw_lines if line.strip()]
    candidate_lines = [_normalize_formula(line) for line in candidate_lines if _FORMULA_LINE_RE.match(line)]
    if not candidate_lines:
        return []

    formulas: list[str] = []
    i = 0
    while i < len(candidate_lines):
        parsed = _try_parse_formula(candidate_lines[i])
        if parsed:
            formulas.append(parsed)
            i += 1
            continue

        merged = candidate_lines[i]
        merged_ok: str | None = None
        max_join = min(len(candidate_lines), i + 4)
        for j in range(i + 1, max_join):
            merged = f"{merged} {candidate_lines[j]}"
            parsed_merged = _try_parse_formula(merged)
            if parsed_merged:
                merged_ok = parsed_merged
                i = j
                break

        if merged_ok:
            formulas.append(merged_ok)

        i += 1

    return _dedup_preserve_order(formulas)


def _locate_section_page_ranges(doc) -> dict[str, range]:
    starts: dict[str, int] = {}
    for page_index in range(doc.page_count):
        text = doc.load_page(page_index).get_text("text") or ""
        for subgroup, heading in SECTION_HEADINGS.items():
            if heading in text:
                starts[subgroup] = page_index

    missing = [subgroup for subgroup in SECTION_HEADINGS if subgroup not in starts]
    if missing:
        raise ValueError(f"Could not locate section headings in PDF pages: {missing}")

    ordered = sorted(starts.items(), key=lambda item: item[1])
    ranges: dict[str, range] = {}
    for index, (subgroup, start_page) in enumerate(ordered):
        end_page = ordered[index + 1][1] if index + 1 < len(ordered) else doc.page_count
        ranges[subgroup] = range(start_page, end_page)
    return ranges


def _extract_case_cube_rects(page) -> list:
    rects: list = []
    for img in page.get_images(full=True):
        xref = img[0]
        for rect in page.get_image_rects(xref):
            if rect.width < 45 or rect.width > 70:
                continue
            if rect.height < 45 or rect.height > 80:
                continue
            if rect.x0 < 20 or rect.x0 > 430:
                continue
            rects.append(rect)

    rects.sort(key=lambda rect: (round(rect.y0, 1), round(rect.x0, 1)))

    unique: list = []
    for rect in rects:
        if unique and abs(rect.x0 - unique[-1].x0) < 0.5 and abs(rect.y0 - unique[-1].y0) < 0.5:
            continue
        unique.append(rect)
    return unique


def _extract_page_cases(page) -> list[list[str]]:
    cube_rects = _extract_case_cube_rects(page)
    if not cube_rects:
        return []

    left_col = sorted((rect for rect in cube_rects if rect.x0 < 200), key=lambda rect: rect.y0)
    right_col = sorted((rect for rect in cube_rects if rect.x0 >= 200), key=lambda rect: rect.y0)

    right_text_start = (min(rect.x1 for rect in right_col) + 6) if right_col else (page.rect.width - 6)
    left_text_end = right_text_start - 6

    words = page.get_text("words") or []

    def words_in_rect(x0: float, y0: float, x1: float, y1: float) -> list[tuple]:
        return [word for word in words if word[0] >= x0 and word[2] <= x1 and word[1] >= y0 and word[3] <= y1]

    formulas_by_rect: dict[tuple[float, float], list[str]] = {}

    for column_rects, is_left in ((left_col, True), (right_col, False)):
        for idx, rect in enumerate(column_rects):
            y0 = rect.y0 - 2
            y1 = (column_rects[idx + 1].y0 - 2) if idx + 1 < len(column_rects) else (page.rect.height - 2)
            x0 = rect.x1 + 6
            x1 = left_text_end if is_left else (page.rect.width - 6)
            region_lines = _lines_from_words(words_in_rect(x0, y0, x1, y1))
            formulas_by_rect[(rect.x0, rect.y0)] = _extract_case_formulas_from_region(region_lines)

    ordered_rects = sorted(cube_rects, key=lambda rect: (rect.y0, rect.x0))
    page_cases: list[list[str]] = []
    for rect in ordered_rects:
        formulas = formulas_by_rect.get((rect.x0, rect.y0), [])
        if formulas:
            page_cases.append(formulas)

    return page_cases


def extract_cases_from_pdf(pdf_path: Path) -> dict[str, list[list[str]]]:
    try:
        import fitz  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Missing dependency: PyMuPDF. Install with: uv pip install PyMuPDF") from exc

    doc = fitz.open(pdf_path)
    try:
        page_ranges = _locate_section_page_ranges(doc)
        extracted: dict[str, list[list[str]]] = {name: [] for name in SECTION_HEADINGS}
        for subgroup, _ in SUBGROUPS:
            for page_index in page_ranges[subgroup]:
                page = doc.load_page(page_index)
                extracted[subgroup].extend(_extract_page_cases(page))
        return extracted
    finally:
        doc.close()


def _case_code(prefix: str, index_1: int) -> str:
    return f"{prefix}{index_1:02d}"


def build_cases_from_pdf(pdf_path: Path) -> list[dict]:
    extracted = extract_cases_from_pdf(pdf_path)

    subgroup_counts = {subgroup: len(cases) for subgroup, cases in extracted.items()}
    for subgroup, expected in EXPECTED_CASE_COUNTS.items():
        actual = subgroup_counts.get(subgroup, 0)
        if actual != expected:
            raise ValueError(f"Expected {expected} cases for {subgroup}, got {actual}")

    if subgroup_counts.get("Expert F2L", 0) <= 0:
        raise ValueError("Expected at least one Expert F2L case")

    cases_out: list[dict] = []
    global_case_number = 1

    for subgroup, prefix in SUBGROUPS:
        subgroup_cases = extracted.get(subgroup, [])
        for index_0, formulas in enumerate(subgroup_cases):
            if not formulas:
                continue
            case_code = _case_code(prefix, index_0 + 1)
            algorithms: list[dict] = []
            for algo_index, formula in enumerate(formulas):
                algorithms.append(
                    {
                        "name": "Main" if algo_index == 0 else f"Alt {algo_index}",
                        "formula": formula,
                        "primary": algo_index == 0,
                    }
                )
            cases_out.append(
                {
                    "subgroup": subgroup,
                    "case_code": case_code,
                    "case_number": global_case_number,
                    "algorithms": algorithms,
                }
            )
            global_case_number += 1

    return cases_out


def write_yaml_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_yaml_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _generate_seed_sql(payload: dict) -> str:
    manifest = normalize_manifest_payload(payload)
    validate_manifest_for_import(manifest)
    return render_seed_sql_block(manifest, begin_marker=BEGIN_MARKER, end_marker=END_MARKER)


def _replace_seed_block(seed_text: str, block: str) -> str:
    start = seed_text.find(BEGIN_MARKER)
    end = seed_text.find(END_MARKER)
    if start < 0 or end < 0 or end < start:
        raise ValueError(f"Seed file must contain markers {BEGIN_MARKER!r} and {END_MARKER!r}")
    end += len(END_MARKER)
    before = seed_text[:start].rstrip("\n")
    after = seed_text[end:].lstrip("\n")
    return f"{before}\n{block}\n{after}"


def validate_yaml_payload(payload: dict) -> None:
    manifest = normalize_manifest_payload(payload)
    validate_manifest_for_import(manifest)


def _build_canonical_payload_from_extraction(*, cases: list[dict], source_pdf_name: str) -> dict:
    canonical_cases: list[dict] = []
    for case in cases:
        canonical_cases.append(
            {
                "case_code": str(case["case_code"]),
                "display_title": str(case["case_code"]),
                "subset": str(case["subgroup"]),
                "sort_order": int(case["case_number"]),
                "recognition_notes": "",
                "probability_notes": "",
                "algorithms": list(case["algorithms"]),
            }
        )
    return {
        "manifest_version": 1,
        "category": "F2L",
        "subset": "best-f2l-from-pdf",
        "source": {
            "title": source_pdf_name,
            "url": "",
            "retrieved_at": "",
            "license": "Unknown",
            "notes": "Extracted via tools/import_f2l_pdf.py",
        },
        "cases": canonical_cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Best F2L Algorithms PDF into cards seed data.")
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF_PATH)
    parser.add_argument("--yaml", type=Path, default=DEFAULT_YAML_PATH)
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED_PATH)
    parser.add_argument("--extract-yaml", action="store_true", help="Extract cases from PDF and write YAML/JSON payload.")
    parser.add_argument("--sync-seed", action="store_true", help="Generate and write db/cards/seed.sql F2L block from YAML payload.")
    args = parser.parse_args()

    if not args.extract_yaml and not args.sync_seed:
        parser.error("At least one action is required: --extract-yaml and/or --sync-seed")

    if args.extract_yaml:
        cases = build_cases_from_pdf(args.pdf)
        payload = _build_canonical_payload_from_extraction(cases=cases, source_pdf_name=str(args.pdf.name))
        validate_yaml_payload(payload)
        write_yaml_json(args.yaml, payload)

        case_counts: Counter[str] = Counter(str(case["subgroup"]) for case in cases)
        algo_count = sum(len(list(case.get("algorithms") or [])) for case in cases)
        summary = ", ".join(f"{key}={case_counts.get(key, 0)}" for key, _ in SUBGROUPS)
        print(f"Wrote {args.yaml} ({len(cases)} cases, {algo_count} algorithms; {summary})")

    if args.sync_seed:
        payload = read_yaml_json(args.yaml)
        validate_yaml_payload(payload)
        block = _generate_seed_sql(payload)
        seed_text = args.seed.read_text(encoding="utf-8")
        updated = _replace_seed_block(seed_text, block.rstrip("\n"))
        args.seed.write_text(updated, encoding="utf-8")
        print(f"Updated {args.seed} (replaced {BEGIN_MARKER} block)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
