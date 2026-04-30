from __future__ import annotations

from pathlib import Path

import sys

repo_root = Path(__file__).resolve().parents[1]
package_src = repo_root / "packages" / "cubeanim" / "src"
for entry in (repo_root, package_src):
    token = str(entry)
    if token not in sys.path:
        sys.path.insert(0, token)

from cubeanim.cards.services import CardsService
from tools.trainer.build_trainer_catalog import (
    SCHEMA_VERSION,
    build_catalog_payload,
    build_trainer_catalog,
)


def _build_payload(tmp_path: Path) -> dict:
    db_path = tmp_path / "cards.db"
    service = CardsService.create(repo_root=repo_root, db_path=db_path)
    return build_catalog_payload(service, base_catalog_url="./assets")


def test_build_trainer_catalog_payload_is_complete_and_grouped(tmp_path: Path) -> None:
    payload = _build_payload(tmp_path)

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["categories"] == ["F2L", "OLL", "ZBLS", "PLL"]
    assert payload["category_labels"]["ZBLS"] == "ZBLS"

    cases = payload["cases"]
    assert cases
    assert {case["group"] for case in cases} == {"F2L", "OLL", "ZBLS", "PLL"}

    for case in cases:
        assert case["case_key"]
        assert ":" in case["case_key"]
        assert case["status"] in {"NEW", "IN_PROGRESS", "LEARNED"}
        assert case["active_algorithm_id"]
        algorithms = case["algorithms"]
        assert isinstance(algorithms, list)
        assert algorithms

        for algorithm in algorithms:
            assert algorithm["formula"]
            assert "sandbox" not in algorithm


def test_build_trainer_catalog_writes_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "trainer"
    assets_dir = tmp_path / "assets"
    build_trainer_catalog(
        repo_root=repo_root,
        db_path=tmp_path / "cards.db",
        output_dir=output_dir,
        assets_dir=assets_dir,
        base_catalog_url="./assets",
    )

    catalog_path = output_dir / "data" / "catalog-v2.json"
    assert catalog_path.exists()
    catalog = catalog_path.read_text(encoding="utf-8")
    assert SCHEMA_VERSION in catalog
    assert (assets_dir / "recognizers").exists()
