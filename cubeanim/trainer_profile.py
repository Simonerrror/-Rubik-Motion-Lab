from __future__ import annotations

import base64
import gzip
import json
from pathlib import Path
from typing import Any


PROFILE_SCHEMA_VERSION = 1


def _ensure_schema(version: Any) -> int:
    if version is None:
        raise ValueError("schema_version is required")

    if int(version) != PROFILE_SCHEMA_VERSION:
        raise ValueError(f"Unsupported schema_version: {version}")

    return PROFILE_SCHEMA_VERSION


def _strip_padding(value: str) -> str:
    return value.rstrip("=")


def _decode_base64url(value: str) -> bytes:
    padded = value
    missing = len(padded) % 4
    if missing:
        padded += "=" * (4 - missing)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def export_trainer_profile(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = gzip.compress(data)
    return _strip_padding(base64.urlsafe_b64encode(compressed).decode("ascii"))


def import_trainer_profile(raw: str) -> dict[str, Any]:
    if not isinstance(raw, str):
        raise ValueError("Profile payload must be a string")

    value = raw.strip()
    if not value:
        raise ValueError("Profile payload is empty")

    try:
        compressed = _decode_base64url(value)
        data = gzip.decompress(compressed)
    except Exception as exc:
        raise ValueError(f"Invalid profile encoding: {exc}") from exc

    try:
        payload = json.loads(data.decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"Invalid profile JSON payload: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Invalid profile payload")

    _ensure_schema(payload.get("schema_version"))

    case_progress = payload.get("case_progress")
    if not isinstance(case_progress, dict):
        raise ValueError("case_progress must be an object")

    active_algorithm_by_case = payload.get("active_algorithm_by_case")
    if not isinstance(active_algorithm_by_case, dict):
        raise ValueError("active_algorithm_by_case must be an object")

    custom_algorithms_by_case = payload.get("custom_algorithms_by_case")
    if not isinstance(custom_algorithms_by_case, dict):
        raise ValueError("custom_algorithms_by_case must be an object")

    for case_key, algorithms in custom_algorithms_by_case.items():
        if not isinstance(case_key, str) or not case_key.strip():
            raise ValueError("custom_algorithms_by_case keys must be non-empty strings")

        if not isinstance(algorithms, list):
            raise ValueError(f"custom_algorithms_by_case[{case_key}] must be an array")

        for algorithm in algorithms:
            if not isinstance(algorithm, dict):
                raise ValueError("custom algorithm entries must be objects")
            if not algorithm.get("id"):
                raise ValueError("custom algorithm id is required")
            if not algorithm.get("formula"):
                raise ValueError("custom algorithm formula is required")

    return {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "case_progress": dict(case_progress),
        "active_algorithm_by_case": dict(active_algorithm_by_case),
        "custom_algorithms_by_case": {
            str(case): list(algorithms)
            for case, algorithms in custom_algorithms_by_case.items()
        },
    }
