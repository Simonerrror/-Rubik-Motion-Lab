#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any


SPEEDCUBEDB_ZBLL_SUBSETS = ("U", "L", "T", "H", "Pi", "S", "AS")
SPEEDCUBEDB_ZBLL_SOURCE_URL = "https://speedcubedb.com/a/3x3/ZBLL"

_SUBSET_SLUGS = {
    "U": "ZBLLU",
    "L": "ZBLLL",
    "T": "ZBLLT",
    "H": "ZBLLH",
    "Pi": "ZBLLPi",
    "S": "ZBLLS",
    "AS": "ZBLLAS",
}
_BLOCK_RE = re.compile(
    r'<div\s+class="[^"]*\bsinglealgorithm\b[^"]*"[^>]*>.*?(?=<div\s+class="[^"]*\bsinglealgorithm\b|$)',
    re.IGNORECASE | re.DOTALL,
)
_ATTR_RE_TEMPLATE = r"""{name}\s*=\s*(['"])(.*?)\1"""
_FORMULA_RE = re.compile(
    r"""<div\b[^>]*class\s*=\s*(['"])[^'"]*\bcubedb-ftw-[^'"]*\1[^>]*\bdata-alg\s*=\s*(['"])(.*?)\2""",
    re.IGNORECASE | re.DOTALL,
)


def _attr(raw: str, name: str) -> str:
    match = re.search(_ATTR_RE_TEMPLATE.format(name=re.escape(name)), raw, re.IGNORECASE | re.DOTALL)
    return html.unescape(match.group(2)).strip() if match else ""


def _normalize_formula(formula: str) -> str:
    normalized = (
        html.unescape(formula)
        .replace("’", "'")
        .replace("‘", "'")
        .replace("`", "'")
        .replace("′", "'")
    )

    def collapse_prime_run(match: re.Match[str]) -> str:
        base = match.group(1)
        count = len(match.group(2)) % 4
        if count == 0:
            return base
        if count == 1:
            return f"{base}'"
        if count == 2:
            return f"{base}2"
        return base

    normalized = re.sub(r"\b([URFDLBMESxyzrlfubd](?:w|W)?)(\'+)", collapse_prime_run, normalized)
    normalized = re.sub(r"2'+", "2", normalized)
    normalized = re.sub(r"\b([URFDLBMESxyzrlfubd](?:w|W)?)3\b", r"\1'", normalized)
    normalized = re.sub(r"\)\s*(\d+)\b", r")^\1", normalized)
    return " ".join(normalized.split())


def _case_number_from_title(title: str) -> int:
    match = re.search(r"(\d+)\s*$", title.strip())
    if not match:
        raise ValueError(f"Could not infer ZBLL case number from title: {title!r}")
    return int(match.group(1))


def _case_code(subset_code: str, case_number: int) -> str:
    return f"ZBLL_{subset_code.upper()}{case_number}"


def _source_url_for_subset(subset_code: str) -> str:
    return f"https://speedcubedb.com/a/3x3/{_SUBSET_SLUGS[subset_code]}"


def parse_zbll_subset_html(html_text: str, *, subset_code: str, source_url: str) -> list[dict[str, Any]]:
    """Extract visible SpeedCubeDB ZBLL rows from one subset aggregate page."""
    if subset_code not in SPEEDCUBEDB_ZBLL_SUBSETS:
        raise ValueError(f"Unsupported ZBLL subset: {subset_code}")

    cases: list[dict[str, Any]] = []
    seen_codes: set[str] = set()

    for block in _BLOCK_RE.findall(html_text):
        title = _attr(block, "data-alg")
        if not title.startswith("ZBLL "):
            continue

        subgroup = _attr(block, "data-subgroup") or _attr(block, "data-filter") or subset_code
        case_number = _case_number_from_title(title)
        code = _case_code(subset_code, case_number)
        if code in seen_codes:
            continue

        formulas: list[str] = []
        seen_formulas: set[str] = set()
        for formula_match in _FORMULA_RE.finditer(block):
            formula = _normalize_formula(formula_match.group(3))
            if formula and formula not in seen_formulas:
                formulas.append(formula)
                seen_formulas.add(formula)

        if not formulas:
            raise ValueError(f"{code}: no formulas found in {source_url}")

        algorithms = [
            {
                "name": "Main" if index == 1 else f"Alt {index - 1}",
                "formula": formula,
                "primary": index == 1,
                "sort_order": index,
            }
            for index, formula in enumerate(formulas, start=1)
        ]
        cases.append(
            {
                "case_code": code,
                "display_title": f"ZBLL {subset_code} #{case_number}",
                "subset": subgroup,
                "sort_order": case_number,
                "recognition_notes": f"Imported from SpeedCubeDB ZBLL {subset_code} page; source subgroup {subgroup}.",
                "probability_notes": "ZBLL full-set import; probability metadata not supplied by source page.",
                "source_url": source_url,
                "algorithms": algorithms,
            }
        )
        seen_codes.add(code)

    return sorted(cases, key=lambda item: (int(item["sort_order"]), str(item["case_code"])))


def build_zbll_manifest_payload(html_by_subset: Mapping[str, str], *, retrieved_at: str) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    global_sort_order = 1
    for subset_code in SPEEDCUBEDB_ZBLL_SUBSETS:
        html_text = html_by_subset.get(subset_code)
        if html_text is None:
            continue
        subset_cases = parse_zbll_subset_html(
            html_text,
            subset_code=subset_code,
            source_url=_source_url_for_subset(subset_code),
        )
        for case in subset_cases:
            case = dict(case)
            case["sort_order"] = global_sort_order
            cases.append(case)
            global_sort_order += 1

    if not cases:
        raise ValueError("No ZBLL cases parsed")

    return {
        "manifest_version": 1,
        "category": "ZBLL",
        "subset": "all",
        "source": {
            "title": "SpeedCubeDB 3x3 ZBLL public aggregate pages",
            "url": SPEEDCUBEDB_ZBLL_SOURCE_URL,
            "retrieved_at": retrieved_at,
            "license": (
                "Imported from public SpeedCubeDB pages by product owner directive; "
                "attribution preserved in docs/reviews/2026-04-30-zbll-speedcubedb-source-review.md."
            ),
            "notes": "Full ZBLL import covers U, L, T, H, Pi, S, and AS subsets from visible aggregate-page algorithms.",
        },
        "cases": cases,
    }


def _fetch_or_read(cache_dir: Path, subset_code: str) -> str:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{subset_code}.html"
    if path.exists():
        return path.read_text(encoding="utf-8")

    url = _source_url_for_subset(subset_code)
    request = urllib.request.Request(url, headers={"User-Agent": "Rubik-Motion-Lab-ZBLL-Importer/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        text = response.read().decode("utf-8", errors="replace")
    path.write_text(text, encoding="utf-8")
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import full SpeedCubeDB ZBLL aggregate pages into a canonical manifest")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/manifests/zbll_speedcubedb.json"),
        help="Manifest JSON output path",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(".cache/speedcubedb-zbll"),
        help="HTML cache directory",
    )
    parser.add_argument(
        "--retrieved-at",
        default="2026-04-30",
        help="Source retrieval date recorded in manifest metadata",
    )
    args = parser.parse_args(argv)

    html_by_subset = {subset: _fetch_or_read(args.cache_dir, subset) for subset in SPEEDCUBEDB_ZBLL_SUBSETS}
    payload = build_zbll_manifest_payload(html_by_subset, retrieved_at=args.retrieved_at)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(payload['cases'])} ZBLL cases to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
