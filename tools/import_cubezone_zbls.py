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
from urllib.parse import parse_qs, urlparse


CUBEZONE_ZBLS_SOURCE_URL = "https://www.cubezone.be/zbf2l.html"
CUBEZONE_ZBLS_BASE_URL = "http://www.cubezone.be"
CUBEZONE_ZBLS_PAGES: tuple[tuple[str, str], ...] = (
    ("ConU_1a", "conU1a.html"),
    ("ConU_1b", "conU1b.html"),
    ("ConU_2a", "conU2a.html"),
    ("ConU_2b", "conU2b.html"),
    ("ConU_3a", "conU3a.html"),
    ("ConU_3b", "conU3b.html"),
    ("SepU_1a", "sepU1a.html"),
    ("SepU_1b", "sepU1b.html"),
    ("SepU_2a", "sepU2a.html"),
    ("SepU_2b", "sepU2b.html"),
    ("SepU_3a", "sepU3a.html"),
    ("SepU_3b", "sepU3b.html"),
    ("InsertE_1", "insertE1.html"),
    ("InsertE_2", "insertE2.html"),
    ("InsertE_3", "insertE3.html"),
    ("InsertC_1", "insertC1.html"),
    ("InsertC_2", "insertC2.html"),
    ("InsertC_3", "insertC3.html"),
    ("ConF2L_1", "conF2L1.html"),
    ("ConF2L_2", "conF2L2.html"),
    ("ConF2L_3", "conF2L3.html"),
)

_ONEBORDER_TABLE_RE = re.compile(
    r"""<table\b(?=[^>]*\bclass\s*=\s*(?P<quote>['"])[^'"]*\boneborder\b[^'"]*(?P=quote))[^>]*>.*?</table>""",
    re.IGNORECASE | re.DOTALL,
)
_TR_RE = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_TD_RE = re.compile(r"<td\b[^>]*>(.*?)</td>", re.IGNORECASE | re.DOTALL)
_IMG_RE = re.compile(r"<img\b[^>]*\bsrc\s*=\s*(['\"])(.*?)\1", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_KNOWN_NEUTRAL_PLACEHOLDERS = {
    ("ConF2L_1", 6): "U U'",
}


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


def _strip_tags(raw: str) -> str:
    return " ".join(html.unescape(_TAG_RE.sub(" ", raw)).split())


def _case_code(subgroup: str, global_order: int) -> str:
    subgroup_token = "CONF2L" if subgroup.startswith("ConF2L_") else re.sub(r"[^A-Za-z0-9]+", "", subgroup).upper()
    order_token = f"{global_order:02d}" if global_order < 100 else str(global_order)
    return f"ZBLS_{subgroup_token}{order_token}"


def _source_url_for_slug(slug: str) -> str:
    return f"https://www.cubezone.be/{slug}"


def _sticker_id_from_image(cell_html: str) -> str:
    match = _IMG_RE.search(cell_html)
    if not match:
        return ""

    src = html.unescape(match.group(2)).strip()
    parsed = urlparse(src)
    stickers = parse_qs(parsed.query).get("stickers", [""])[0].strip()
    if stickers:
        return stickers
    return src.rsplit("/", 1)[-1]


def _extract_algorithm_table(html_text: str, subgroup: str) -> str:
    for match in _ONEBORDER_TABLE_RE.finditer(html_text):
        table = match.group(0)
        if subgroup in _strip_tags(table):
            return table
    raise ValueError(f"Could not find CubeZone ZBLS table for subgroup {subgroup}")


def parse_zbls_page_html(
    html_text: str,
    *,
    subgroup: str,
    source_url: str,
    global_start_order: int,
) -> list[dict[str, Any]]:
    """Extract CubeZone ZB F2L/ZBLS cases from one individual subgroup page."""
    table = _extract_algorithm_table(html_text, subgroup)
    rows = [_TD_RE.findall(row) for row in _TR_RE.findall(table)]

    cases: list[dict[str, Any]] = []
    local_index = 1
    global_order = global_start_order
    pending_images: list[str] | None = None

    for cells in rows:
        if not cells:
            continue
        if any(_IMG_RE.search(cell) for cell in cells):
            pending_images = cells
            continue

        if pending_images is None:
            continue

        formulas = [_normalize_formula(_strip_tags(cell)) for cell in cells]
        if len(formulas) != len(pending_images):
            raise ValueError(
                f"{subgroup}: image/formula cell mismatch in {source_url}: "
                f"{len(pending_images)} images, {len(formulas)} formulas"
            )

        for image_cell, formula in zip(pending_images, formulas, strict=True):
            if not formula:
                formula = _KNOWN_NEUTRAL_PLACEHOLDERS.get((subgroup, local_index), "")
            if not formula:
                raise ValueError(f"{subgroup} #{local_index}: empty formula in {source_url}")
            sticker_id = _sticker_id_from_image(image_cell)
            notes_suffix = ""
            if (subgroup, local_index) in _KNOWN_NEUTRAL_PLACEHOLDERS:
                notes_suffix = " CubeZone formula cell is blank for this solved-slot case; neutral identity placeholder recorded."
            cases.append(
                {
                    "case_code": _case_code(subgroup, global_order),
                    "display_title": f"ZBLS {subgroup} #{local_index:02d}",
                    "subset": subgroup,
                    "sort_order": global_order,
                    "recognition_notes": (
                        f"Imported from CubeZone ZB F2L {subgroup} page; sticker {sticker_id}.{notes_suffix}"
                    ),
                    "probability_notes": (
                        "CubeZone full ZB F2L/ZBLS import; probability metadata not supplied by source page."
                    ),
                    "source_url": source_url,
                    "algorithms": [
                        {
                            "name": "Main",
                            "formula": formula,
                            "primary": True,
                            "sort_order": 1,
                        }
                    ],
                }
            )
            local_index += 1
            global_order += 1
        pending_images = None

    if not cases:
        raise ValueError(f"No ZBLS cases parsed for subgroup {subgroup} from {source_url}")
    return cases


def build_zbls_manifest_payload(html_by_page: Mapping[str, str], *, retrieved_at: str) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    global_order = 1

    for subgroup, slug in CUBEZONE_ZBLS_PAGES:
        html_text = html_by_page.get(subgroup)
        if html_text is None:
            html_text = html_by_page.get(slug)
        if html_text is None:
            continue

        page_cases = parse_zbls_page_html(
            html_text,
            subgroup=subgroup,
            source_url=_source_url_for_slug(slug),
            global_start_order=global_order,
        )
        cases.extend(page_cases)
        global_order += len(page_cases)

    if not cases:
        raise ValueError("No ZBLS cases parsed")

    return {
        "manifest_version": 1,
        "category": "ZBLS",
        "subset": "all",
        "source": {
            "title": "CubeZone ZB First Two Layers public pages",
            "url": CUBEZONE_ZBLS_SOURCE_URL,
            "retrieved_at": retrieved_at,
            "license": (
                "Imported from public CubeZone pages by product owner directive; "
                "attribution preserved in docs/reviews/2026-04-30-zbls-cubezone-source-review.md."
            ),
            "notes": (
                "Full ZB First Two Layers/ZBLS import covers all 306 cases from the individual CubeZone "
                "subgroup pages; ConF2L_1 #06 has a blank source formula cell and is recorded with a neutral "
                "identity placeholder so runtime records stay non-empty."
            ),
        },
        "cases": cases,
    }


def _fetch_or_read(cache_dir: Path, subgroup: str, slug: str) -> str:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / slug
    if path.exists():
        return path.read_text(encoding="utf-8")

    url = f"{CUBEZONE_ZBLS_BASE_URL}/{slug}"
    request = urllib.request.Request(url, headers={"User-Agent": "Rubik-Motion-Lab-ZBLS-Importer/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        text = response.read().decode("utf-8", errors="replace")
    path.write_text(text, encoding="utf-8")
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import CubeZone ZB First Two Layers pages into a canonical ZBLS manifest")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/manifests/zbls_cubezone.json"),
        help="Manifest JSON output path",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(".cache/cubezone-zbls"),
        help="HTML cache directory",
    )
    parser.add_argument(
        "--retrieved-at",
        default="2026-04-30",
        help="Source retrieval date recorded in manifest metadata",
    )
    args = parser.parse_args(argv)

    html_by_page = {
        subgroup: _fetch_or_read(args.cache_dir, subgroup, slug)
        for subgroup, slug in CUBEZONE_ZBLS_PAGES
    }
    payload = build_zbls_manifest_payload(html_by_page, retrieved_at=args.retrieved_at)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(payload['cases'])} ZBLS cases to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
