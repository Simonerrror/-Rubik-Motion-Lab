from __future__ import annotations

from typing import Literal

ProgressStatus = Literal["NEW", "IN_PROGRESS", "LEARNED"]

PROGRESS_STATUSES = {"NEW", "IN_PROGRESS", "LEARNED"}
