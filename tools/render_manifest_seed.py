#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.algorithm_manifest import normalize_manifest_payload, read_manifest_json, render_seed_sql_block


def replace_seed_block(
    seed_path: Path,
    manifest_path: Path,
    *,
    block_name: str,
    before_marker: str,
    old_block_name: str | None = None,
) -> None:
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
    block_names = [block_name]
    if old_block_name and old_block_name not in block_names:
        block_names.append(old_block_name)

    for candidate_block_name in block_names:
        candidate_begin = f"-- BEGIN MANIFEST {candidate_block_name}"
        candidate_end = f"-- END MANIFEST {candidate_block_name}"
        old_begin = "\n" + header + "\n" + candidate_begin + "\n"
        if old_begin not in text:
            continue
        prefix, rest = text.split(old_begin, 1)
        _old_block, suffix = rest.split(candidate_end + "\n", 1)
        next_text = prefix + block + suffix
        break
    else:
        legacy_begin = f"\n-- BEGIN MANIFEST {old_block_name}\n" if old_block_name else ""
        if legacy_begin and legacy_begin in text:
            prefix, rest = text.split(legacy_begin, 1)
            lines = prefix.splitlines(keepends=True)
            if lines and lines[-1].startswith("-- Canonical "):
                prefix = "".join(lines[:-1])
            legacy_end = f"-- END MANIFEST {old_block_name}"
            _old_block, suffix = rest.split(legacy_end + "\n", 1)
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
    parser.add_argument("--old-block-name")
    parser.add_argument("--before-marker", default="\n-- Reference PLL probability tables\n")
    args = parser.parse_args()

    replace_seed_block(
        args.seed,
        args.manifest,
        block_name=args.block_name,
        old_block_name=args.old_block_name,
        before_marker=args.before_marker,
    )
    print(f"Rendered {args.manifest} into {args.seed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
