#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

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
