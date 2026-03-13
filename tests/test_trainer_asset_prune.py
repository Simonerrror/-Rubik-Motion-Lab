from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.trainer.prune_trainer_assets import prune_trainer_assets


def test_prune_trainer_assets_removes_non_whitelisted_files(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog-v2.json"
    assets_dir = tmp_path / "assets"

    keep_path = assets_dir / "recognizers" / "f2l" / "svg" / "f2l_b01.svg"
    drop_path = assets_dir / "recognizers" / "f2l" / "svg" / "f2l_b99.svg"
    keep_path.parent.mkdir(parents=True, exist_ok=True)
    keep_path.write_text("<svg/>", encoding="utf-8")
    drop_path.write_text("<svg/>", encoding="utf-8")

    payload = {
        "cases": [
            {
                "group": "F2L",
                "case_code": "B01",
                "recognizer_url": "./assets/recognizers/f2l/svg/f2l_b01.svg",
            }
        ]
    }
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")

    stats = prune_trainer_assets(catalog_path=catalog_path, assets_dir=assets_dir)
    assert stats["kept_count"] == 1
    assert stats["removed_count"] == 1
    assert keep_path.exists()
    assert not drop_path.exists()


def test_prune_trainer_assets_rejects_invalid_case_codes(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog-v2.json"
    assets_dir = tmp_path / "assets"
    (assets_dir / "recognizers").mkdir(parents=True, exist_ok=True)
    payload = {
        "cases": [
            {
                "group": "F2L",
                "case_code": "INVALID",
                "recognizer_url": "./assets/recognizers/f2l/svg/f2l_invalid.svg",
            }
        ]
    }
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid case codes"):
        prune_trainer_assets(catalog_path=catalog_path, assets_dir=assets_dir)
