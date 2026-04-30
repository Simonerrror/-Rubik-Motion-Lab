#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.algorithm_manifest import normalize_manifest_payload, read_manifest_json, render_seed_sql_block


def replace_seed_block(seed_path: Path, manifest_path: Path, *, block_name: str, before_marker: str) -> None:
    manifest = normalize_manifest_payload(read_manifest_json(manifest_path))
    header = f"-- Canonical {manifest.category} cases/algorithms"
    begin_marker = f"-- BEGIN MANIFEST {block_name}"
    end_marker = f"-- END MANIFEST {block_name}"
    block = "\n" + header + "\n" + render_seed_sql_block(
        manifest,
        begin_marker=begin_marker,
        end_marker=end_marker,
    )

    text = seed_path.read_text(encoding="utf-8")
    old_begin = "\n" + header + "\n" + begin_marker + "\n"
    if old_begin in text:
        prefix, rest = text.split(old_begin, 1)
        _old_block, suffix = rest.split(end_marker + "\n", 1)
        next_text = prefix + block + suffix
    else:
        if before_marker not in text:
            raise ValueError(f"before marker not found in seed file: {before_marker}")
        next_text = text.replace(before_marker, block + before_marker, 1)

    seed_path.write_text(next_text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a canonical manifest into db/cards/seed.sql")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--seed", type=Path, default=Path("db/cards/seed.sql"))
    parser.add_argument("--block-name", required=True)
    parser.add_argument("--before-marker", default="\n-- Reference PLL probability tables\n")
    args = parser.parse_args()

    replace_seed_block(
        args.seed,
        args.manifest,
        block_name=args.block_name,
        before_marker=args.before_marker,
    )
    print(f"Rendered {args.manifest} into {args.seed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
