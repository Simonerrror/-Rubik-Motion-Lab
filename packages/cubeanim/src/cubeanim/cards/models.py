from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ProgressStatus = Literal["NEW", "IN_PROGRESS", "LEARNED"]
RenderQuality = Literal["draft", "high"]
JobStatus = Literal["PENDING", "RUNNING", "DONE", "FAILED", "CANCELED"]

PROGRESS_STATUSES = {"NEW", "IN_PROGRESS", "LEARNED"}
RENDER_QUALITIES = {"draft", "high"}
JOB_STATUSES = {"PENDING", "RUNNING", "DONE", "FAILED", "CANCELED"}


@dataclass(frozen=True)
class AlgorithmSummary:
    id: int
    name: str
    formula: str
    group: str
    case_code: str
    status: ProgressStatus
    recognizer_url: str | None


@dataclass(frozen=True)
class RenderArtifact:
    quality: str
    output_name: str
    output_path: str


@dataclass(frozen=True)
class QueueItem:
    id: int
    quality: str
    status: str
    plan_action: str | None
    output_path: str | None
    error_message: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None
