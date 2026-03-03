#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

def _repo_root_from_file() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "db" / "cards" / "schema.sql").exists():
            return parent
    raise RuntimeError("Could not resolve repository root for tools/trainer/profile_codec_cli.py")


REPO_ROOT = _repo_root_from_file()
PACKAGE_SRC = REPO_ROOT / "packages" / "cubeanim" / "src"
for entry in (REPO_ROOT, PACKAGE_SRC):
    token = str(entry)
    if token not in sys.path:
        sys.path.insert(0, token)

from cubeanim.trainer_profile import export_trainer_profile, import_trainer_profile


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trainer profile codec helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export", help="Encode profile JSON to base64url(gzip(json))")
    export_parser.add_argument("--input", type=Path, required=True, help="Path to profile JSON")

    import_parser = subparsers.add_parser("import", help="Decode profile payload to pretty JSON")
    import_parser.add_argument("--payload", required=True, help="Encoded payload string")

    return parser.parse_args()


def run_export(input_path: Path) -> None:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    print(export_trainer_profile(payload))


def run_import(payload: str) -> None:
    decoded = import_trainer_profile(payload)
    print(json.dumps(decoded, ensure_ascii=False, indent=2))


def main() -> None:
    args = parse_args()
    if args.command == "export":
        run_export(args.input)
        return
    if args.command == "import":
        run_import(args.payload)
        return
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
