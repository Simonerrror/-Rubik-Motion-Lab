#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def _repo_root_from_file() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "db" / "cards" / "schema.sql").exists():
            return parent
    raise RuntimeError("Could not resolve repository root for tools/trainer/build_trainer_catalog.py")


REPO_ROOT = _repo_root_from_file()
PACKAGE_SRC = REPO_ROOT / "packages" / "cubeanim" / "src"
for entry in (REPO_ROOT, PACKAGE_SRC):
    token = str(entry)
    if token not in sys.path:
        sys.path.insert(0, token)

from cubeanim.cards import repository
from cubeanim.cards.db import connect
from cubeanim.cards.sandbox import build_sandbox_timeline
from cubeanim.cards.services import CardsService
from cubeanim.state import solved_state_string, state_slots_metadata
from tools.trainer.prune_trainer_assets import prune_trainer_assets


GROUPS = ("F2L", "OLL", "PLL")
SCHEMA_VERSION = "trainer-catalog-v1"
DEFAULT_PLAYBACK_CONFIG = {
    "run_time_sec": 0.65,
    "double_turn_multiplier": 1.7,
    "inter_move_pause_ratio": 0.05,
    "rate_func": "ease_in_out_sine",
}


def _default_state_slots() -> list[dict[str, Any]]:
    return [
        {"position": [x, y, z], "face": face}
        for (x, y, z), face in state_slots_metadata()
    ]


def _normalize_formula(formula: str) -> str:
    normalized = (
        str(formula)
        .replace("’", "'")
        .replace("‘", "'")
        .replace("`", "'")
        .replace("′", "'")
    )
    normalized = re.sub(r"2'+", "2", normalized)
    return " ".join(normalized.split())


def _algorithm_id(case_key: str, algorithm_id: int) -> str:
    return f"{case_key}:algo:{int(algorithm_id)}"


def _case_key(group: str, case_code: str) -> str:
    return f"{group}:{case_code}"


def _normalize_recognizer_url(recognizer_url: str | None, asset_base: str) -> str:
    if not recognizer_url:
        return ""
    normalized = str(recognizer_url).strip()
    if normalized.startswith("/assets/"):
        normalized = normalized[len("/assets/"):]
    elif normalized.startswith("assets/"):
        normalized = normalized[len("assets/"):]

    if not normalized:
        return ""
    return f"{asset_base.rstrip('/')}/{normalized}"


def _build_timeline_payload(formula: str, group: str) -> dict[str, Any]:
    normalized = _normalize_formula(formula)
    state_slots = _default_state_slots()

    if not normalized:
        return {
            "formula": "",
            "group": group,
            "move_steps": [],
            "moves_flat": [],
            "initial_state": solved_state_string(),
            "states_by_step": [solved_state_string()],
            "highlight_by_step": [],
            "state_slots": state_slots,
            "playback_config": DEFAULT_PLAYBACK_CONFIG,
        }

    try:
        timeline = build_sandbox_timeline(normalized, group)
    except Exception:
        # Keep static build resilient even if a runtime DB contains malformed custom formulas.
        return {
            "formula": normalized,
            "group": group,
            "move_steps": [],
            "moves_flat": [],
            "initial_state": solved_state_string(),
            "states_by_step": [solved_state_string()],
            "highlight_by_step": [],
            "state_slots": state_slots,
            "playback_config": DEFAULT_PLAYBACK_CONFIG,
        }

    return {
        "formula": timeline.formula,
        "group": timeline.group,
        "move_steps": timeline.move_steps,
        "moves_flat": timeline.moves_flat,
        "initial_state": timeline.initial_state,
        "states_by_step": timeline.states_by_step,
        "highlight_by_step": timeline.highlight_by_step,
        "state_slots": timeline.state_slots,
        "playback_config": DEFAULT_PLAYBACK_CONFIG,
    }


def _pick_active_algorithm_id(raw_case: dict[str, Any], algorithms: list[dict[str, Any]]) -> str:
    raw_active = raw_case.get("active_algorithm_id")
    if raw_active is None:
        return str(algorithms[0]["id"]) if algorithms else ""

    active = str(raw_active)
    for item in algorithms:
        if item["id"].split(":")[-1] == active or item["id"] == active:
            return item["id"]

    # Fall back to first algorithm if an active ID is stale.
    return str(algorithms[0]["id"]) if algorithms else ""


def build_catalog_payload(service: CardsService, *, base_catalog_url: str) -> dict[str, Any]:
    cases_out: list[dict[str, Any]] = []

    for group in GROUPS:
        raw_cases = service.list_cases(group=group)
        for raw_case in raw_cases:
            case_code = str(raw_case.get("case_code", "")).strip()
            if not case_code:
                continue

            case_key = _case_key(group, case_code)

            with connect(service.db_path) as conn:
                algorithm_rows = repository.list_case_alternatives(conn, case_id=int(raw_case["id"]))

            algorithms: list[dict[str, Any]] = []
            for item in algorithm_rows:
                raw_id = int(item["id"])
                algorithm_payload = {
                    "id": _algorithm_id(case_key, raw_id),
                    "name": str(item.get("name") or case_code),
                    "formula": _normalize_formula(str(item.get("formula") or "")),
                    "is_custom": bool(item.get("is_custom", False)),
                    "status": str(item.get("status", "NEW")),
                }
                algorithm_payload["sandbox"] = _build_timeline_payload(
                    formula=algorithm_payload["formula"],
                    group=group,
                )
                algorithms.append(algorithm_payload)

            if not algorithms:
                continue

            active_algorithm_id = _pick_active_algorithm_id(raw_case, algorithms)
            case_payload = {
                "case_key": case_key,
                "group": group,
                "case_code": case_code,
                "title": str(raw_case.get("title") or case_code),
                "subgroup_title": str(
                    raw_case.get("subgroup_title") or f"{group} Cases"
                ),
                "case_number": raw_case.get("case_number"),
                "probability_text": str(raw_case.get("probability_text") or "n/a"),
                "status": str(raw_case.get("status") or "NEW"),
                "recognizer_url": _normalize_recognizer_url(
                    raw_case.get("recognizer_url"),
                    base_catalog_url,
                ),
                "active_algorithm_id": active_algorithm_id,
                "algorithms": algorithms,
                "sandbox": algorithms[0]["sandbox"],
            }
            cases_out.append(case_payload)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "categories": list(GROUPS),
        "cases": cases_out,
    }


def build_trainer_catalog(
    *,
    repo_root: Path,
    db_path: Path | None = None,
    output_dir: Path,
    assets_dir: Path,
    base_catalog_url: str = "./assets",
) -> dict[str, Any]:
    service = CardsService.create(repo_root=repo_root, db_path=db_path)

    payload = build_catalog_payload(service, base_catalog_url=base_catalog_url)
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = data_dir / "catalog-v1.json"
    catalog_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    runtime_recognizers = service.db_path.parent / "recognizers"
    if runtime_recognizers.exists():
        target = assets_dir / "recognizers"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(runtime_recognizers, target)
    prune_trainer_assets(catalog_path=catalog_path, assets_dir=assets_dir)

    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build static trainer catalog")
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "apps" / "trainer",
        help="Trainer output directory",
    )
    parser.add_argument(
        "--assets-dir",
        type=Path,
        default=None,
        help="Assets directory for copied recognizers",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Path to runtime cards DB (optional)",
    )
    parser.add_argument(
        "--base-catalog-url",
        default="./assets",
        help="Base URL used in catalog recognizer paths",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = REPO_ROOT
    output_dir = args.output
    assets_dir = args.assets_dir or (output_dir / "assets")

    payload = build_trainer_catalog(
        repo_root=repo_root,
        db_path=args.db_path,
        output_dir=output_dir,
        assets_dir=assets_dir,
        base_catalog_url=args.base_catalog_url,
    )

    print(f"Catalog written to {output_dir / 'data' / 'catalog-v1.json'}")
    print(f"Recognizers copied to {assets_dir}")
    print(f"Cases: {len(payload['cases'])}")


if __name__ == "__main__":
    main()
