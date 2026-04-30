#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

CASE_CODE_PATTERNS: dict[str, re.Pattern[str]] = {
    "F2L": re.compile(r"^[BAE]\d{2}$"),
    "OLL": re.compile(r"^OLL_\d+$"),
    "PLL": re.compile(r"^PLL_\d+$"),
    "ZBLL": re.compile(r"^ZBLL_[A-Z0-9]+$"),
    "ZBLS": re.compile(r"^ZBLS_[A-Z0-9]+$"),
}


def _repo_root_from_file() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "db" / "cards" / "schema.sql").exists():
            return parent
    raise RuntimeError("Could not resolve repository root for tools/trainer/prune_trainer_assets.py")


REPO_ROOT = _repo_root_from_file()


def _normalize_recognizer_rel_path(raw_url: str) -> str:
    normalized = str(raw_url).strip()
    if not normalized:
        return ""
    if "://" in normalized:
        normalized = urlsplit(normalized).path
    normalized = normalized.split("?", 1)[0].split("#", 1)[0]
    normalized = normalized.lstrip("./").lstrip("/")
    if "assets/" in normalized:
        normalized = normalized.split("assets/", 1)[1]
    if not normalized.startswith("recognizers/"):
        return ""
    return normalized


def _validate_case_codes(cases: list[dict]) -> None:
    invalid: list[str] = []
    for case in cases:
        group = str(case.get("group") or "").strip().upper()
        case_code = str(case.get("case_code") or "").strip()
        pattern = CASE_CODE_PATTERNS.get(group)
        if pattern is None and group:
            pattern = re.compile(rf"^{re.escape(group)}_[A-Z0-9]+$")
        if pattern is None:
            invalid.append(f"{group}:{case_code}")
            continue
        if not pattern.fullmatch(case_code):
            invalid.append(f"{group}:{case_code}")
    if invalid:
        raise ValueError(f"Invalid case codes in trainer catalog: {invalid[:10]}")


def prune_trainer_assets(*, catalog_path: Path, assets_dir: Path) -> dict[str, int]:
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    cases = list(payload.get("cases") or [])
    _validate_case_codes(cases)

    whitelist_rel: set[str] = set()
    for case in cases:
        rel = _normalize_recognizer_rel_path(str(case.get("recognizer_url") or ""))
        if rel:
            whitelist_rel.add(rel)

    if not whitelist_rel:
        raise ValueError("No recognizer assets found in catalog whitelist")

    recognizer_root = assets_dir / "recognizers"
    recognizer_root.mkdir(parents=True, exist_ok=True)
    whitelist_abs = {assets_dir / rel for rel in whitelist_rel}

    removed_count = 0
    for candidate in recognizer_root.rglob("*"):
        if not candidate.is_file():
            continue
        if candidate not in whitelist_abs:
            candidate.unlink()
            removed_count += 1

    for directory in sorted((p for p in recognizer_root.rglob("*") if p.is_dir()), reverse=True):
        if any(directory.iterdir()):
            continue
        directory.rmdir()

    missing = [path for path in sorted(whitelist_abs) if not path.exists()]
    if missing:
        preview = [str(path.relative_to(assets_dir)) for path in missing[:10]]
        raise FileNotFoundError(f"Missing recognizer assets after prune: {preview}")

    return {
        "whitelist_count": len(whitelist_abs),
        "removed_count": removed_count,
        "kept_count": len(whitelist_abs),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prune trainer recognizer assets to catalog whitelist")
    parser.add_argument(
        "--catalog",
        type=Path,
        default=REPO_ROOT / "apps" / "trainer" / "data" / "catalog-v2.json",
        help="Path to trainer catalog JSON",
    )
    parser.add_argument(
        "--assets-dir",
        type=Path,
        default=REPO_ROOT / "apps" / "trainer" / "assets",
        help="Assets directory containing recognizers",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stats = prune_trainer_assets(catalog_path=args.catalog, assets_dir=args.assets_dir)
    print(
        "Pruned recognizers: "
        f"kept={stats['kept_count']} removed={stats['removed_count']} whitelist={stats['whitelist_count']}"
    )


if __name__ == "__main__":
    main()
