from __future__ import annotations

import json
from pathlib import Path

import sys

repo_root = Path(__file__).resolve().parents[1]
package_src = repo_root / "packages" / "cubeanim" / "src"
for entry in (repo_root, package_src):
    token = str(entry)
    if token not in sys.path:
        sys.path.insert(0, token)

from tools.import_speedcubedb_zbll import (
    SPEEDCUBEDB_ZBLL_SUBSETS,
    build_zbll_manifest_payload,
    parse_zbll_subset_html,
)
from tools.algorithm_manifest import normalize_manifest_payload, validate_manifest_for_import


ZBLL_HTML_FIXTURE = """
<div class="row singlealgorithm g-0" data-subgroup="T1" data-alg="ZBLL T 1">
  <a data-title="3x3 - ZBLL T - ZBLL T 1" href="a/3x3/ZBLLT/ZBLL_T_1"></a>
  <div><a href="#" data-filter="T1">T1</a></div>
  <div class="setup-case align-items-center"><div>setup:</div>L' U L U2' R' L'</div>
  <div data-ori='0'><ul class='list-group' data-t="ZBLL T 1,0">
    <li class='list-group-item'>
      <div class="cubedb-ftw-" data-puzzle="3x3" data-alg="y R' U' R U' R' U' R U2 L' R' U R U' L"></div>
    </li>
    <li class='list-group-item'>
      <div class="cubedb-ftw-" data-puzzle="3x3" data-alg="y2 S R U' R2 U B' U' R2 U B R' S'"></div>
    </li>
  </ul></div>
</div>
<div class="row singlealgorithm g-0" data-subgroup="T1" data-alg="ZBLL T 2">
  <a data-title="3x3 - ZBLL T - ZBLL T 2" href="a/3x3/ZBLLT/ZBLL_T_2"></a>
  <div><a href="#" data-filter="T1">T1</a></div>
  <div class="setup-case align-items-center"><div>setup:</div>L' U R' U'</div>
  <div data-ori='0'><ul class='list-group' data-t="ZBLL T 2,0">
    <li class='list-group-item'>
      <div class="cubedb-ftw-" data-puzzle="3x3" data-alg="R' U2 R U' R' D R' U R U R' U2 R U' D' R"></div>
    </li>
  </ul></div>
</div>
"""


def test_parse_zbll_subset_html_extracts_cases_and_algorithms() -> None:
    cases = parse_zbll_subset_html(ZBLL_HTML_FIXTURE, subset_code="T", source_url="https://speedcubedb.com/a/3x3/ZBLLT")

    assert [case["case_code"] for case in cases] == ["ZBLL_T1", "ZBLL_T2"]
    assert cases[0]["display_title"] == "ZBLL T #1"
    assert cases[0]["subset"] == "T1"
    assert cases[0]["sort_order"] == 1
    assert cases[0]["recognition_notes"] == "Imported from SpeedCubeDB ZBLL T page; source subgroup T1."
    assert [item["name"] for item in cases[0]["algorithms"]] == ["Main", "Alt 1"]
    assert cases[0]["algorithms"][0]["primary"] is True
    assert cases[0]["algorithms"][1]["primary"] is False


def test_build_zbll_manifest_payload_is_import_valid_for_fixture() -> None:
    payload = build_zbll_manifest_payload({"T": ZBLL_HTML_FIXTURE}, retrieved_at="2026-04-30")
    manifest = normalize_manifest_payload(payload)

    validate_manifest_for_import(manifest)

    assert manifest.category == "ZBLL"
    assert manifest.subset == "all"
    assert len(manifest.cases) == 2
    assert manifest.source_url == "https://speedcubedb.com/a/3x3/ZBLL"
    assert "product owner directive" in str(manifest.source_license).lower()


def test_committed_zbll_manifest_contains_all_speedcubedb_cases() -> None:
    path = repo_root / "data" / "manifests" / "zbll_speedcubedb.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    manifest = normalize_manifest_payload(payload)

    validate_manifest_for_import(manifest)

    assert len(manifest.cases) == 472
    assert set(SPEEDCUBEDB_ZBLL_SUBSETS) == {
        "U",
        "L",
        "T",
        "H",
        "Pi",
        "S",
        "AS",
    }
    assert all(case.case_code.startswith("ZBLL_") for case in manifest.cases)
    assert all(len(case.algorithms) >= 1 for case in manifest.cases)
