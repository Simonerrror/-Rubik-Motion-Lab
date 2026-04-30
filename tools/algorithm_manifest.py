from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cubeanim.formula import FormulaConverter
from cubeanim_domain.sandbox import build_sandbox_timeline


@dataclass(frozen=True)
class ManifestAlgorithm:
    name: str
    formula: str
    primary: bool
    sort_order: int


@dataclass(frozen=True)
class ManifestCase:
    case_code: str
    display_title: str
    subset: str
    sort_order: int
    recognition_notes: str | None
    probability_notes: str | None
    algorithms: tuple[ManifestAlgorithm, ...]


@dataclass(frozen=True)
class CanonicalAlgorithmManifest:
    manifest_version: int
    category: str
    subset: str
    source_title: str
    source_url: str | None
    source_retrieved_at: str | None
    source_license: str | None
    source_notes: str | None
    cases: tuple[ManifestCase, ...]


_PILOT_GOVERNED_CATEGORIES = {"ZBLL", "ZBLS"}
_UNCERTAIN_LICENSE_TERMS = ("unknown", "unspecified", "pending legal review")


def read_manifest_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_formula(formula: str) -> str:
    normalized = (
        formula.replace("’", "'")
        .replace("‘", "'")
        .replace("`", "'")
        .replace("′", "'")
    )
    normalized = re.sub(r"2'+", "2", normalized)
    normalized = re.sub(r"\)\s*(\d+)\b", r")^\1", normalized)
    return " ".join(normalized.split())


def _require_non_empty_str(raw: Any, field: str) -> str:
    value = str(raw or "").strip()
    if not value:
        raise ValueError(f"{field} is required")
    return value


def _normalize_algorithm(raw: dict[str, Any], *, default_name: str, sort_order: int) -> ManifestAlgorithm:
    name = _require_non_empty_str(raw.get("name", default_name), "algorithm.name")
    formula = _normalize_formula(_require_non_empty_str(raw.get("formula"), "algorithm.formula"))
    primary = bool(raw.get("primary"))
    normalized_sort_order = int(raw.get("sort_order", sort_order))
    if normalized_sort_order <= 0:
        raise ValueError(f"algorithm {name}: sort_order must be > 0")
    return ManifestAlgorithm(name=name, formula=formula, primary=primary, sort_order=normalized_sort_order)


def _normalize_case(raw: dict[str, Any], *, fallback_subset: str, fallback_sort_order: int) -> ManifestCase:
    case_code = _require_non_empty_str(raw.get("case_code"), "case.case_code")
    display_title = _require_non_empty_str(raw.get("display_title") or raw.get("title") or case_code, "case.display_title")
    subset = _require_non_empty_str(raw.get("subset") or raw.get("subgroup") or fallback_subset, "case.subset")

    sort_order_raw = raw.get("sort_order", raw.get("case_number", fallback_sort_order))
    sort_order = int(sort_order_raw)
    if sort_order <= 0:
        raise ValueError(f"case {case_code}: sort_order must be > 0")

    algorithms_raw = raw.get("algorithms")
    if not isinstance(algorithms_raw, list) or not algorithms_raw:
        raise ValueError(f"case {case_code}: algorithms must be a non-empty list")

    algorithms: list[ManifestAlgorithm] = []
    for index, algorithm_raw in enumerate(algorithms_raw, start=1):
        if not isinstance(algorithm_raw, dict):
            raise ValueError(f"case {case_code}: algorithm entry #{index} must be an object")
        algorithms.append(
            _normalize_algorithm(
                algorithm_raw,
                default_name=f"Algo {index}",
                sort_order=index,
            )
        )

    primary_count = sum(1 for item in algorithms if item.primary)
    if primary_count != 1:
        raise ValueError(f"case {case_code}: exactly one primary algorithm is required (got {primary_count})")

    return ManifestCase(
        case_code=case_code,
        display_title=display_title,
        subset=subset,
        sort_order=sort_order,
        recognition_notes=str(raw.get("recognition_notes") or "").strip() or None,
        probability_notes=str(raw.get("probability_notes") or raw.get("probability_text") or "").strip() or None,
        algorithms=tuple(algorithms),
    )


def _normalize_source(payload: dict[str, Any]) -> tuple[str, str | None, str | None, str | None, str | None]:
    source = payload.get("source")
    if isinstance(source, dict):
        return (
            _require_non_empty_str(source.get("title"), "source.title"),
            str(source.get("url") or "").strip() or None,
            str(source.get("retrieved_at") or "").strip() or None,
            str(source.get("license") or "").strip() or None,
            str(source.get("notes") or "").strip() or None,
        )

    legacy_source_pdf = str(payload.get("source_pdf") or "").strip()
    if legacy_source_pdf:
        return (legacy_source_pdf, None, None, None, "Legacy F2L PDF extraction payload")

    raise ValueError("source metadata is required")


def _normalize_legacy_manifest(payload: dict[str, Any]) -> CanonicalAlgorithmManifest:
    if int(payload.get("version", 0)) != 1:
        raise ValueError("legacy payload must use version=1")

    cases_raw = payload.get("cases")
    if not isinstance(cases_raw, list) or not cases_raw:
        raise ValueError("legacy payload cases must be a non-empty list")

    source_title, source_url, source_retrieved_at, source_license, source_notes = _normalize_source(payload)

    normalized_cases = tuple(
        _normalize_case(case_raw, fallback_subset="F2L", fallback_sort_order=index)
        for index, case_raw in enumerate(cases_raw, start=1)
    )
    return CanonicalAlgorithmManifest(
        manifest_version=1,
        category="F2L",
        subset="legacy-f2l",
        source_title=source_title,
        source_url=source_url,
        source_retrieved_at=source_retrieved_at,
        source_license=source_license,
        source_notes=source_notes,
        cases=normalized_cases,
    )


def _normalize_canonical_manifest(payload: dict[str, Any]) -> CanonicalAlgorithmManifest:
    if int(payload.get("manifest_version", 0)) != 1:
        raise ValueError("manifest_version must be 1")

    category = _require_non_empty_str(payload.get("category"), "category").upper()
    subset = _require_non_empty_str(payload.get("subset"), "subset")
    source_title, source_url, source_retrieved_at, source_license, source_notes = _normalize_source(payload)

    cases_raw = payload.get("cases")
    if not isinstance(cases_raw, list) or not cases_raw:
        raise ValueError("cases must be a non-empty list")

    normalized_cases = tuple(
        _normalize_case(case_raw, fallback_subset=subset, fallback_sort_order=index)
        for index, case_raw in enumerate(cases_raw, start=1)
    )
    return CanonicalAlgorithmManifest(
        manifest_version=1,
        category=category,
        subset=subset,
        source_title=source_title,
        source_url=source_url,
        source_retrieved_at=source_retrieved_at,
        source_license=source_license,
        source_notes=source_notes,
        cases=normalized_cases,
    )


def normalize_manifest_payload(payload: dict[str, Any]) -> CanonicalAlgorithmManifest:
    if "manifest_version" in payload:
        manifest = _normalize_canonical_manifest(payload)
    elif "version" in payload:
        manifest = _normalize_legacy_manifest(payload)
    else:
        raise ValueError("Unsupported payload: expected canonical manifest_version or legacy version")
    _validate_uniqueness(manifest)
    return manifest


def _validate_uniqueness(manifest: CanonicalAlgorithmManifest) -> None:
    seen_case_codes: set[str] = set()
    for case in manifest.cases:
        if case.case_code in seen_case_codes:
            raise ValueError(f"Duplicate case_code detected: {case.case_code}")
        seen_case_codes.add(case.case_code)

        seen_algorithm_names: set[str] = set()
        for algorithm in case.algorithms:
            if algorithm.name in seen_algorithm_names:
                raise ValueError(f"Duplicate algorithm name for case {case.case_code}: {algorithm.name}")
            seen_algorithm_names.add(algorithm.name)


def validate_manifest_governance(manifest: CanonicalAlgorithmManifest) -> None:
    if manifest.category not in _PILOT_GOVERNED_CATEGORIES:
        return

    required_source_fields = {
        "source.title": manifest.source_title,
        "source.url": manifest.source_url,
        "source.retrieved_at": manifest.source_retrieved_at,
        "source.license": manifest.source_license,
        "source.notes": manifest.source_notes,
    }
    missing = [field for field, value in required_source_fields.items() if not str(value or "").strip()]
    if missing:
        raise ValueError(f"{manifest.category}/{manifest.subset}: missing required provenance fields: {missing}")

    license_text = str(manifest.source_license or "").strip()
    lower_license = license_text.lower()
    blocked_terms = [term for term in _UNCERTAIN_LICENSE_TERMS if term in lower_license]
    if blocked_terms:
        raise ValueError(
            f"{manifest.category}/{manifest.subset}: source.license must include an explicit reuse basis "
            f"before pilot import (blocked terms: {blocked_terms})"
        )


def validate_formulas_with_parser_and_timeline(manifest: CanonicalAlgorithmManifest) -> None:
    for case in manifest.cases:
        for algorithm in case.algorithms:
            try:
                FormulaConverter.convert_steps(algorithm.formula, repeat=1)
            except Exception as exc:
                raise ValueError(
                    f"Invalid formula for {manifest.category}/{case.case_code}/{algorithm.name}: {algorithm.formula}"
                ) from exc
            build_sandbox_timeline(algorithm.formula, manifest.category)


def validate_manifest_for_import(manifest: CanonicalAlgorithmManifest) -> None:
    """Run mandatory checks before generating import artifacts."""
    validate_manifest_governance(manifest)
    validate_formulas_with_parser_and_timeline(manifest)


def render_seed_sql_block(
    manifest: CanonicalAlgorithmManifest,
    *,
    begin_marker: str,
    end_marker: str,
) -> str:
    validate_manifest_governance(manifest)

    category = manifest.category
    lines: list[str] = [
        begin_marker,
        f"-- Auto-generated from canonical manifest: {category}/{manifest.subset}",
        "DELETE FROM canonical_algorithms",
        "WHERE canonical_case_id IN (",
        f"  SELECT id FROM canonical_cases WHERE category_code = '{category}'",
        ");",
        f"DELETE FROM canonical_cases WHERE category_code = '{category}';",
    ]

    cases = sorted(manifest.cases, key=lambda item: (item.sort_order, item.case_code))
    for case in cases:
        probability = "NULL" if case.probability_notes is None else f"'{_sql_escape(case.probability_notes)}'"
        lines.append(
            "INSERT INTO canonical_cases (category_code, case_code, title, subgroup_title, case_number, probability_text, orientation_front, orientation_auf, sort_order) "
            f"VALUES ('{_sql_escape(category)}', '{_sql_escape(case.case_code)}', '{_sql_escape(case.display_title)}', "
            f"'{_sql_escape(case.subset)}', {case.sort_order}, {probability}, 'F', 0, {case.sort_order}) "
            "ON CONFLICT(category_code, case_code) DO UPDATE SET "
            "title=excluded.title, subgroup_title=excluded.subgroup_title, case_number=excluded.case_number, "
            "probability_text=excluded.probability_text, orientation_front=excluded.orientation_front, "
            "orientation_auf=excluded.orientation_auf, sort_order=excluded.sort_order;"
        )

        algorithms = sorted(case.algorithms, key=lambda item: (item.sort_order, item.name))
        for algorithm in algorithms:
            lines.append(
                "INSERT INTO canonical_algorithms (canonical_case_id, name, formula, is_primary, sort_order) "
                f"SELECT id, '{_sql_escape(algorithm.name)}', '{_sql_escape(algorithm.formula)}', "
                f"{1 if algorithm.primary else 0}, {algorithm.sort_order} "
                f"FROM canonical_cases WHERE category_code='{_sql_escape(category)}' AND case_code='{_sql_escape(case.case_code)}' "
                "ON CONFLICT(canonical_case_id, name) DO UPDATE SET "
                "formula=excluded.formula, is_primary=excluded.is_primary, sort_order=excluded.sort_order;"
            )

    lines.append(end_marker)
    return "\n".join(lines) + "\n"


def _sql_escape(value: str) -> str:
    return value.replace("'", "''")
