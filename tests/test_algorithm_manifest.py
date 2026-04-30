from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

repo_root = Path(__file__).resolve().parents[1]
package_src = repo_root / "packages" / "cubeanim" / "src"
for entry in (repo_root, package_src):
    token = str(entry)
    if token not in sys.path:
        sys.path.insert(0, token)

from tools.algorithm_manifest import (
    normalize_manifest_payload,
    render_seed_sql_block,
    validate_manifest_for_import,
    validate_manifest_governance,
    validate_formulas_with_parser_and_timeline,
)


def _load_manifest(name: str) -> dict:
    return json.loads((repo_root / "data" / "manifests" / name).read_text(encoding="utf-8"))


def _zbls_payload_with_license(license_text: str) -> dict:
    payload = _load_manifest("zbls_u_pilot.json")
    source = dict(payload["source"])
    source["license"] = license_text
    payload["source"] = source
    return payload


def test_manifest_fixture_supports_required_fields() -> None:
    payload = _load_manifest("zbll_t_fixture.json")
    manifest = normalize_manifest_payload(payload)

    assert manifest.category == "ZBLL"
    assert manifest.subset == "T"
    assert manifest.source_title
    assert manifest.source_license
    assert manifest.source_url and "speedcubedb.com" in manifest.source_url
    assert len(manifest.cases) == 2
    assert manifest.cases[0].recognition_notes
    assert manifest.cases[0].probability_notes
    assert len(manifest.cases[0].algorithms) >= 1
    assert manifest.cases[0].case_code.startswith("ZBLL_T")


def test_manifest_fixture_formulas_validate_parser_and_timeline() -> None:
    payload = _load_manifest("zbll_t_fixture.json")
    manifest = normalize_manifest_payload(payload)
    validate_formulas_with_parser_and_timeline(manifest)
    formulas = [algorithm.formula for case in manifest.cases for algorithm in case.algorithms]
    assert formulas
    assert all("2'" not in formula for formula in formulas)


def test_zbll_fixture_is_quarantined_until_source_license_is_explicit() -> None:
    payload = _load_manifest("zbll_t_fixture.json")
    manifest = normalize_manifest_payload(payload)

    with pytest.raises(ValueError, match="source.license"):
        validate_manifest_governance(manifest)


def test_zbll_fixture_cannot_render_seed_sql_without_explicit_license() -> None:
    payload = _load_manifest("zbll_t_fixture.json")
    manifest = normalize_manifest_payload(payload)

    with pytest.raises(ValueError, match="source.license"):
        render_seed_sql_block(manifest, begin_marker="-- BEGIN TEST", end_marker="-- END TEST")


@pytest.mark.parametrize(
    "license_text,blocked_term",
    [
        ("Unknown", "unknown"),
        ("Reuse basis unspecified by source", "unspecified"),
        ("Pending legal review from owner", "pending legal review"),
    ],
)
def test_zbls_manifest_rejects_uncertain_license_terms(license_text: str, blocked_term: str) -> None:
    payload = _zbls_payload_with_license(license_text)
    manifest = normalize_manifest_payload(payload)

    with pytest.raises(ValueError, match="source.license"):
        validate_manifest_governance(manifest)

    with pytest.raises(ValueError, match=blocked_term):
        validate_manifest_governance(manifest)


def test_zbls_manifest_supports_required_fields_and_license_gate() -> None:
    payload = _load_manifest("zbls_u_pilot.json")
    manifest = normalize_manifest_payload(payload)
    validate_manifest_for_import(manifest)

    assert manifest.category == "ZBLS"
    assert manifest.subset == "U"
    assert manifest.source_title
    assert manifest.source_url
    assert manifest.source_retrieved_at == "2026-04-30"
    assert manifest.source_license
    lower_license = manifest.source_license.lower()
    assert "unspecified" not in lower_license
    assert "unknown" not in lower_license
    assert "pending legal review" not in lower_license
    assert len(manifest.cases) == 2
    assert all(case.case_code.startswith("ZBLS_U") for case in manifest.cases)


def test_zbls_manifest_formulas_validate_and_render_seed_sql() -> None:
    payload = _load_manifest("zbls_u_pilot.json")
    manifest = normalize_manifest_payload(payload)
    validate_manifest_for_import(manifest)

    block = render_seed_sql_block(manifest, begin_marker="-- BEGIN TEST", end_marker="-- END TEST")
    assert block == render_seed_sql_block(manifest, begin_marker="-- BEGIN TEST", end_marker="-- END TEST")
    assert "category_code = 'ZBLS'" in block
    assert "ZBLS_U01" in block
    assert "ZBLS_U02" in block


def test_legacy_f2l_payload_is_still_supported() -> None:
    legacy_payload = {
        "version": 1,
        "source_pdf": "Best F2L Algorithms.pdf",
        "cases": [
            {
                "subgroup": "Basic F2L",
                "case_code": "B01",
                "case_number": 1,
                "algorithms": [
                    {"name": "Main", "formula": "R U R' U'", "primary": True},
                ],
            }
        ],
    }
    manifest = normalize_manifest_payload(legacy_payload)
    validate_formulas_with_parser_and_timeline(manifest)
    block = render_seed_sql_block(manifest, begin_marker="-- BEGIN TEST", end_marker="-- END TEST")

    assert manifest.category == "F2L"
    assert "B01" in block
