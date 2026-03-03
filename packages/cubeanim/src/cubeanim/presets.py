from __future__ import annotations

from typing import Dict

from cubeanim.models import AlgorithmPreset, RenderGroup


PRESET_LIST = [
    AlgorithmPreset(
        name="Sexy",
        formula="R' U R U'",
        repeat=6,
        group=RenderGroup.NO_GROUP,
        aliases=("SexyMoveSixTimes",),
    ),
    AlgorithmPreset(
        name="Ua",
        formula="M2 U M U2 M' U M2",
        group=RenderGroup.PLL,
    ),
    AlgorithmPreset(
        name="Ub",
        formula="M2 U' M U2 M' U' M2",
        group=RenderGroup.PLL,
    ),
    AlgorithmPreset(
        name="Vperm",
        formula="R' U R' d' R' F' R2 U' R' U R' F R F",
        group=RenderGroup.PLL,
    ),
]


def _normalized_key(name: str) -> str:
    return name.strip().lower()


def _build_registry() -> Dict[str, AlgorithmPreset]:
    registry: Dict[str, AlgorithmPreset] = {}
    for preset in PRESET_LIST:
        keys = [preset.name, *preset.aliases]
        for raw_key in keys:
            key = _normalized_key(raw_key)
            if key in registry:
                raise ValueError(f"Duplicate preset key detected: {raw_key}")
            registry[key] = preset
    return registry


PRESET_REGISTRY = _build_registry()


def get_preset(name: str) -> AlgorithmPreset:
    key = _normalized_key(name)
    if key not in PRESET_REGISTRY:
        available = ", ".join(sorted({preset.name for preset in PRESET_REGISTRY.values()}))
        raise KeyError(f"Unknown preset: {name}. Available presets: {available}")
    return PRESET_REGISTRY[key]


def list_preset_names() -> list[str]:
    return sorted({preset.name for preset in PRESET_REGISTRY.values()})
