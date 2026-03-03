from __future__ import annotations

import pytest

from cubeanim.trainer_profile import export_trainer_profile, import_trainer_profile


def _sample_profile() -> dict:
    return {
        "schema_version": 1,
        "case_progress": {"PLL:PLL_1": "IN_PROGRESS"},
        "active_algorithm_by_case": {"PLL:PLL_1": "pll:pll_1:custom:abc"},
        "custom_algorithms_by_case": {
            "PLL:PLL_1": [
                {
                    "id": "pll:pll_1:custom:abc",
                    "name": "My v1",
                    "formula": "R U R'",
                    "status": "NEW",
                }
            ]
        },
    }


def test_trainer_profile_codec_roundtrip() -> None:
    payload = _sample_profile()
    encoded = export_trainer_profile(payload)

    assert isinstance(encoded, str)
    assert encoded

    decoded = import_trainer_profile(encoded)
    assert decoded["schema_version"] == 1
    assert decoded["case_progress"] == payload["case_progress"]
    assert decoded["active_algorithm_by_case"] == payload["active_algorithm_by_case"]
    assert decoded["custom_algorithms_by_case"] == payload["custom_algorithms_by_case"]


def test_trainer_profile_codec_rejects_wrong_schema_version() -> None:
    invalid_payload = _sample_profile()
    invalid_payload["schema_version"] = 999

    encoded = export_trainer_profile(invalid_payload)
    with pytest.raises(ValueError, match="Unsupported schema_version"):
        import_trainer_profile(encoded)
