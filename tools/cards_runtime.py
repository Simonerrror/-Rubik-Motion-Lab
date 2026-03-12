#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_SRC = REPO_ROOT / "packages" / "cubeanim" / "src"
for entry in (REPO_ROOT, PACKAGE_SRC):
    token = str(entry)
    if token not in sys.path:
        sys.path.insert(0, token)

from cubeanim.cards.services import CardsService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Local cards runtime administration without the deprecated HTTP API."
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Optional path to an alternate cards.db runtime root",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("reset-runtime", help="Rebuild cards runtime DB and recognizers")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    service = CardsService.create(repo_root=REPO_ROOT, db_path=args.db_path)

    if args.command == "reset-runtime":
        payload = service.reset_runtime()
    else:
        raise ValueError(f"Unsupported command: {args.command}")

    print(json.dumps({"ok": True, "data": payload}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
