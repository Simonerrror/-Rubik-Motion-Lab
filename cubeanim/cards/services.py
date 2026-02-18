from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

from cubeanim.cards import repository
from cubeanim.cards.db import DEFAULT_DB_ENV, connect, default_db_path, initialize_database, repo_root_from_file
from cubeanim.cards.models import RENDER_QUALITIES
from cubeanim.render_service import RenderRequest, plan_formula_render, render_formula

GROUPS = {"F2L", "OLL", "PLL"}


@dataclass
class CardsService:
    repo_root: Path
    db_path: Path

    @classmethod
    def create(cls, repo_root: Path | None = None, db_path: Path | None = None) -> "CardsService":
        root = repo_root or repo_root_from_file()
        path = db_path
        if path is None:
            env_path = os.environ.get(DEFAULT_DB_ENV, "").strip()
            path = Path(env_path) if env_path else default_db_path(root)
        initialize_database(repo_root=root, db_path=path)
        return cls(repo_root=root, db_path=path)

    def list_algorithms(self, group: str = "ALL") -> list[dict[str, Any]]:
        with connect(self.db_path) as conn:
            rows = repository.list_algorithms(conn, group=group)
            return [self._decorate_algorithm(row, conn) for row in rows]

    def list_reference_sets(self, category: str) -> list[dict[str, Any]]:
        normalized = category.strip().upper()
        if normalized not in GROUPS:
            raise ValueError(f"category must be one of {sorted(GROUPS)}")
        with connect(self.db_path) as conn:
            return repository.list_reference_sets(conn, category=normalized)

    def list_cases(self, group: str) -> list[dict[str, Any]]:
        normalized = group.strip().upper()
        if normalized not in GROUPS:
            raise ValueError(f"group must be one of {sorted(GROUPS)}")
        with connect(self.db_path) as conn:
            rows = repository.list_cases(conn, group=normalized)
            return [self._decorate_case(row, conn) for row in rows]

    def get_case(self, case_id: int) -> dict[str, Any]:
        with connect(self.db_path) as conn:
            row = repository.get_case(conn, case_id=case_id)
            if row is None:
                raise KeyError(f"case id {case_id} not found")
            return self._decorate_case(row, conn, include_jobs=True)

    def activate_case_algorithm(self, case_id: int, algorithm_id: int) -> dict[str, Any]:
        with connect(self.db_path) as conn:
            updated = repository.set_case_selected_algorithm(conn, case_id=case_id, algorithm_id=algorithm_id)
            return self._decorate_case(updated, conn, include_jobs=True)

    def create_case_custom_algorithm(
        self,
        case_id: int,
        formula: str,
        name: str | None = None,
        activate: bool = True,
    ) -> dict[str, Any]:
        with connect(self.db_path) as conn:
            repository.create_custom_algorithm_for_case(
                conn,
                case_id=case_id,
                formula=formula,
                name=name,
                activate=activate,
            )
            row = repository.get_case(conn, case_id=case_id)
            if row is None:
                raise KeyError(f"case id {case_id} not found")
            return self._decorate_case(row, conn, include_jobs=True)

    def get_algorithm(self, algorithm_id: int) -> dict[str, Any]:
        with connect(self.db_path) as conn:
            row = repository.get_algorithm(conn, algorithm_id)
            if row is None:
                raise KeyError(f"algorithm id {algorithm_id} not found")
            return self._decorate_algorithm(row, conn, include_jobs=True)

    def create_custom_algorithm(
        self,
        name: str,
        formula: str,
        group: str,
        case_code: str,
    ) -> dict[str, Any]:
        with connect(self.db_path) as conn:
            created = repository.create_custom_algorithm(
                conn,
                name=name,
                formula=formula,
                group=group,
                case_code=case_code,
            )
            return self._decorate_algorithm(created, conn)

    def set_progress(self, algorithm_id: int, status: str) -> dict[str, Any]:
        with connect(self.db_path) as conn:
            repository.set_progress_status(conn, algorithm_id=algorithm_id, status=status)
            row = repository.get_algorithm(conn, algorithm_id)
            if row is None:
                raise KeyError(f"algorithm id {algorithm_id} not found")
            return self._decorate_algorithm(row, conn)

    def enqueue_render(self, algorithm_id: int, quality: str) -> dict[str, Any]:
        if quality not in RENDER_QUALITIES:
            raise ValueError(f"quality must be one of {sorted(RENDER_QUALITIES)}")

        with connect(self.db_path) as conn:
            return self._enqueue_render_for_algorithm(conn, algorithm_id=algorithm_id, quality=quality)

    def enqueue_case_render(self, case_id: int, quality: str) -> dict[str, Any]:
        if quality not in RENDER_QUALITIES:
            raise ValueError(f"quality must be one of {sorted(RENDER_QUALITIES)}")
        with connect(self.db_path) as conn:
            case_row = repository.get_case(conn, case_id=case_id)
            if case_row is None:
                raise KeyError(f"case id {case_id} not found")
            algorithm_id = case_row.get("active_algorithm_id")
            if algorithm_id is None:
                raise ValueError("Case has no active algorithm")
            return self._enqueue_render_for_algorithm(conn, algorithm_id=int(algorithm_id), quality=quality)

    def queue_status(self, algorithm_id: int | None = None, case_id: int | None = None) -> dict[str, Any]:
        with connect(self.db_path) as conn:
            if algorithm_id is None:
                if case_id is None:
                    raise ValueError("Either algorithm_id or case_id must be provided")
                case_row = repository.get_case(conn, case_id=case_id)
                if case_row is None:
                    raise KeyError(f"case id {case_id} not found")
                algorithm_id = case_row.get("active_algorithm_id")
                if algorithm_id is None:
                    raise ValueError("Case has no active algorithm")

            jobs = repository.list_latest_jobs_for_algorithm(conn, algorithm_id)
            draft_art = repository.get_render_artifact(conn, algorithm_id, "draft")
            high_art = repository.get_render_artifact(conn, algorithm_id, "high")
            return {
                "algorithm_id": algorithm_id,
                "jobs": jobs,
                "artifacts": {
                    "draft": self._artifact_payload(draft_art),
                    "high": self._artifact_payload(high_art),
                },
            }

    def process_next_job(self) -> dict[str, Any] | None:
        with connect(self.db_path) as conn:
            job = repository.claim_next_pending_job(conn)
            if job is None:
                return None

            algorithm_id = int(job["algorithm_id"])
            quality = str(job["quality"])
            algorithm = repository.get_algorithm(conn, algorithm_id)
            if algorithm is None:
                return repository.mark_job_failed(conn, job["id"], "Algorithm not found")

            formula = str(algorithm["formula"]).strip()
            if not formula:
                return repository.mark_job_failed(conn, job["id"], "Algorithm formula is empty")

            try:
                request = self._build_request(algorithm=algorithm, quality=quality)
                plan = plan_formula_render(request=request, repo_root=self.repo_root)

                if (
                    plan.action == "confirm_rerender"
                    and "identical formula" in plan.reason.lower()
                    and plan.final_path.exists()
                ):
                    rel_output_path = str(plan.final_path.relative_to(self.repo_root))
                    repository.upsert_render_artifact(
                        conn,
                        algorithm_id=algorithm_id,
                        quality=quality,
                        output_name=plan.output_name,
                        output_path=rel_output_path,
                        formula_norm=self._normalize_formula(formula),
                        repeat=1,
                    )
                    return repository.mark_job_done(
                        conn,
                        job_id=job["id"],
                        plan_action="reuse_existing",
                        output_name=plan.output_name,
                        output_path=rel_output_path,
                    )

                result = render_formula(
                    request=request,
                    repo_root=self.repo_root,
                    allow_rerender=(plan.action == "confirm_rerender"),
                )
                rel_output_path = str(result.final_path.relative_to(self.repo_root))
                repository.upsert_render_artifact(
                    conn,
                    algorithm_id=algorithm_id,
                    quality=quality,
                    output_name=result.output_name,
                    output_path=rel_output_path,
                    formula_norm=self._normalize_formula(formula),
                    repeat=1,
                )
                return repository.mark_job_done(
                    conn,
                    job_id=job["id"],
                    plan_action=result.action,
                    output_name=result.output_name,
                    output_path=rel_output_path,
                )
            except Exception as exc:
                return repository.mark_job_failed(conn, job_id=job["id"], error_message=str(exc))

    def _enqueue_render_for_algorithm(
        self,
        conn,
        algorithm_id: int,
        quality: str,
    ) -> dict[str, Any]:
        algorithm = repository.get_algorithm(conn, algorithm_id)
        if algorithm is None:
            raise KeyError(f"algorithm id {algorithm_id} not found")

        formula = str(algorithm["formula"]).strip()
        if not formula:
            raise ValueError("Selected algorithm has empty formula. Add or edit formula first.")

        if quality == "high":
            draft_artifact = repository.get_render_artifact(conn, algorithm_id, "draft")
            if draft_artifact is None:
                raise ValueError("HD render requires existing draft artifact")

        active = repository.get_active_job(conn, algorithm_id=algorithm_id, quality=quality)
        if active is not None:
            return {
                "job": active,
                "reused": False,
                "message": "Job already in queue",
            }

        cached_artifact = repository.get_render_artifact(conn, algorithm_id, quality)
        if (
            cached_artifact is not None
            and cached_artifact.get("formula_norm") == self._normalize_formula(formula)
            and (self.repo_root / str(cached_artifact["output_path"])).exists()
        ):
            done_job = repository.insert_render_job(
                conn,
                algorithm_id=algorithm_id,
                quality=quality,
                status="DONE",
                plan_action="reuse_cached_artifact",
                output_name=str(cached_artifact["output_name"]),
                output_path=str(cached_artifact["output_path"]),
            )
            return {
                "job": done_job,
                "reused": True,
                "message": "Existing artifact reused",
            }

        request = self._build_request(algorithm=algorithm, quality=quality)
        plan = plan_formula_render(request=request, repo_root=self.repo_root)

        if plan.action == "confirm_rerender" and "identical formula" in plan.reason.lower() and plan.final_path.exists():
            rel_output_path = str(plan.final_path.relative_to(self.repo_root))
            repository.upsert_render_artifact(
                conn,
                algorithm_id=algorithm_id,
                quality=quality,
                output_name=plan.output_name,
                output_path=rel_output_path,
                formula_norm=self._normalize_formula(formula),
                repeat=1,
            )
            done_job = repository.insert_render_job(
                conn,
                algorithm_id=algorithm_id,
                quality=quality,
                status="DONE",
                plan_action="reuse_existing",
                output_name=plan.output_name,
                output_path=rel_output_path,
            )
            return {
                "job": done_job,
                "reused": True,
                "message": "Existing render reused",
            }

        pending = repository.insert_render_job(
            conn,
            algorithm_id=algorithm_id,
            quality=quality,
            status="PENDING",
        )
        return {
            "job": pending,
            "reused": False,
            "message": "Job queued",
        }

    def _build_request(self, algorithm: dict[str, Any], quality: str) -> RenderRequest:
        return RenderRequest(
            formula=str(algorithm["formula"]),
            name=str(algorithm["name"]),
            group=str(algorithm["group"]),
            quality=quality,
            repeat=1,
            play=False,
        )

    @staticmethod
    def _normalize_formula(formula: str) -> str:
        return " ".join(formula.split())

    def _decorate_algorithm(
        self,
        row: dict[str, Any],
        conn,
        include_jobs: bool = False,
    ) -> dict[str, Any]:
        algorithm_id = int(row["id"])
        draft = repository.get_render_artifact(conn, algorithm_id, "draft")
        high = repository.get_render_artifact(conn, algorithm_id, "high")

        payload = {
            **row,
            "artifacts": {
                "draft": self._artifact_payload(draft),
                "high": self._artifact_payload(high),
            },
        }
        if include_jobs:
            payload["jobs"] = repository.list_latest_jobs_for_algorithm(conn, algorithm_id)
        return payload

    def _artifact_payload(self, artifact: dict[str, Any] | None) -> dict[str, Any] | None:
        if artifact is None:
            return None
        return {
            "quality": artifact["quality"],
            "output_name": artifact["output_name"],
            "output_path": artifact["output_path"],
            "video_url": f"/{artifact['output_path']}",
            "updated_at": artifact["updated_at"],
        }

    def _decorate_case(
        self,
        row: dict[str, Any],
        conn,
        include_jobs: bool = False,
    ) -> dict[str, Any]:
        algorithm_id = row.get("active_algorithm_id")
        artifacts = {"draft": None, "high": None}
        jobs: list[dict[str, Any]] = []
        if algorithm_id is not None:
            draft = repository.get_render_artifact(conn, int(algorithm_id), "draft")
            high = repository.get_render_artifact(conn, int(algorithm_id), "high")
            artifacts = {
                "draft": self._artifact_payload(draft),
                "high": self._artifact_payload(high),
            }
            if include_jobs:
                jobs = repository.list_latest_jobs_for_algorithm(conn, int(algorithm_id))

        payload = {
            **row,
            "artifacts": artifacts,
        }
        if "algorithms" in row:
            payload["algorithms"] = [
                {
                    **item,
                    "is_active": item["id"] == row.get("active_algorithm_id"),
                }
                for item in row["algorithms"]
            ]
        if include_jobs:
            payload["jobs"] = jobs
        return payload
