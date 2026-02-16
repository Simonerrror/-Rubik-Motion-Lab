from __future__ import annotations

from cubeanim.scenes import FormulaScene, PresetScene


class Preset(PresetScene):
    """
    Uses environment variable configured by scripts/render_algo.py:
    - CUBEANIM_PRESET
    """


class Formula(FormulaScene):
    """
    Uses environment variables configured by scripts/render_algo.py:
    - CUBEANIM_FORMULA
    - CUBEANIM_GROUP
    - CUBEANIM_NAME
    - CUBEANIM_REPEAT
    """
