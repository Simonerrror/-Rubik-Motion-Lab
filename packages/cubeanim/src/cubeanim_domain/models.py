from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class RenderGroup(str, Enum):
    F2L = "F2L"
    OLL = "OLL"
    PLL = "PLL"
    ZBLL = "ZBLL"
    NO_GROUP = "NO_GROUP"


@dataclass(frozen=True)
class AlgorithmPreset:
    name: str
    formula: str
    group: RenderGroup = RenderGroup.NO_GROUP
    repeat: int = 1
    aliases: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Preset name must be non-empty")
        if not self.formula.strip():
            raise ValueError("Preset formula must be non-empty")
        if self.repeat < 1:
            raise ValueError("Preset repeat must be >= 1")
