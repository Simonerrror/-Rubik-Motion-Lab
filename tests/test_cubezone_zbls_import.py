from __future__ import annotations

import json
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
package_src = repo_root / "packages" / "cubeanim" / "src"
for entry in (repo_root, package_src):
    token = str(entry)
    if token not in sys.path:
        sys.path.insert(0, token)

from tools.algorithm_manifest import normalize_manifest_payload, validate_manifest_for_import
from tools.import_cubezone_zbls import (
    CUBEZONE_ZBLS_PAGES,
    build_zbls_manifest_payload,
    parse_zbls_page_html,
)


ZBLS_HTML_FIXTURE = """
<table cellspacing="0" cellpadding="5" class="oneborder">
<tr class="center"><td colspan="4"><big><em>ConF2L_3</em></big></td></tr>
<tr class="center">
<td><img src="https://cubezone.be/imagecube/imagecube.php?stickers=case-a&size=100"></td>
<td><img src="https://cubezone.be/imagecube/imagecube.php?stickers=case-b&size=100"></td>
<td><img src="https://cubezone.be/imagecube/imagecube.php?stickers=case-c&size=100"></td>
</tr>
<tr class="center">
<td>R U' R' U' R2 B' R' y R2 U2 R' F'</td>
<td>R U' R' F' L' U2 L F</td>
<td>R2 U2 F R' F' U2 R' U2 R'</td>
</tr>
</table>
"""


def test_parse_zbls_page_html_extracts_cases_and_formulas() -> None:
    cases = parse_zbls_page_html(
        ZBLS_HTML_FIXTURE,
        subgroup="ConF2L_3",
        source_url="https://www.cubezone.be/conF2L3.html",
        global_start_order=301,
    )

    assert [case["case_code"] for case in cases] == [
        "ZBLS_CONF2L301",
        "ZBLS_CONF2L302",
        "ZBLS_CONF2L303",
    ]
    assert cases[0]["display_title"] == "ZBLS ConF2L_3 #01"
    assert cases[0]["subset"] == "ConF2L_3"
    assert cases[0]["sort_order"] == 301
    assert "sticker case-a" in cases[0]["recognition_notes"]
    assert cases[0]["algorithms"] == [
        {
            "name": "Main",
            "formula": "R U' R' U' R2 B' R' y R2 U2 R' F'",
            "primary": True,
            "sort_order": 1,
        }
    ]


def test_build_zbls_manifest_payload_is_import_valid_for_fixture() -> None:
    payload = build_zbls_manifest_payload(
        {"ConF2L_3": ZBLS_HTML_FIXTURE},
        retrieved_at="2026-04-30",
    )
    manifest = normalize_manifest_payload(payload)

    validate_manifest_for_import(manifest)

    assert manifest.category == "ZBLS"
    assert manifest.subset == "all"
    assert len(manifest.cases) == 3
    assert manifest.source_url == "https://www.cubezone.be/zbf2l.html"
    assert "product owner directive" in str(manifest.source_license).lower()


def test_committed_zbls_manifest_contains_all_cubezone_cases() -> None:
    path = repo_root / "data" / "manifests" / "zbls_cubezone.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    manifest = normalize_manifest_payload(payload)

    validate_manifest_for_import(manifest)

    assert len(manifest.cases) == 306
    assert len(CUBEZONE_ZBLS_PAGES) == 21
    assert all(case.case_code.startswith("ZBLS_") for case in manifest.cases)
    assert all(len(case.algorithms) >= 1 for case in manifest.cases)
