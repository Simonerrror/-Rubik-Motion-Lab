from __future__ import annotations

import os
import hashlib
import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from cubeanim.cards import repository
from cubeanim.cards.db import (
    DEFAULT_DB_ENV,
    connect,
    default_db_path,
    initialize_database,
    reset_runtime_state,
    repo_root_from_file,
)
from cubeanim.cards.models import RENDER_QUALITIES
from cubeanim.cards.recognizer import ensure_recognizer_assets
from cubeanim.cards.renderer_client import RendererClient, build_renderer_client_from_env
from cubeanim.cards.sandbox import build_sandbox_timeline
from cubeanim.executor import ExecutionConfig
from cubeanim.palette import FACE_ORDER, CONTRAST_SAFE_CUBE_COLORS
from cubeanim.render_service import RenderRequest

GROUPS = {"F2L", "OLL", "PLL"}
_MOVE_RUN_TIME_ENV = "CUBEANIM_MOVE_RUN_TIME"
_SANDBOX_RATE_FUNC = "ease_in_out_sine"


def _resolved_execution_config() -> ExecutionConfig:
    config = ExecutionConfig()
    raw_run_time = os.environ.get(_MOVE_RUN_TIME_ENV, "").strip()
    if not raw_run_time:
        return config
    try:
        run_time = float(raw_run_time)
    except ValueError as exc:
        raise ValueError(
            f"Environment variable {_MOVE_RUN_TIME_ENV} must be a float"
        ) from exc
    if run_time <= 0:
        raise ValueError(
            f"Environment variable {_MOVE_RUN_TIME_ENV} must be > 0"
        )
    return replace(config, run_time=run_time)


@dataclass
class CardsService:
    repo_root: Path
    db_path: Path
    renderer_client: RendererClient

    @classmethod
    def create(
        cls,
        repo_root: Path | None = None,
        db_path: Path | None = None,
        renderer_client: RendererClient | None = None,
    ) -> "CardsService":
        root = repo_root or repo_root_from_file()
        path = db_path
        if path is None:
            env_path = os.environ.get(DEFAULT_DB_ENV, "").strip()
            path = Path(env_path) if env_path else default_db_path(root)
        initialize_database(repo_root=root, db_path=path)
        client = renderer_client or build_renderer_client_from_env()
        return cls(repo_root=root, db_path=path, renderer_client=client)

    def list_algorithms(self, group: str = "ALL") -> list[dict[str, Any]]:
        with connect(self.db_path) as conn:
            rows = repository.list_algorithms(conn, group=group)
            return [self._decorate_algorithm(row, conn) for row in rows]

    def reset_runtime(self) -> dict[str, Any]:
        path = reset_runtime_state(repo_root=self.repo_root, db_path=self.db_path)
        self.db_path = path
        return {"db_path": str(path)}

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

    def get_case_sandbox(self, case_id: int) -> dict[str, Any]:
        with connect(self.db_path) as conn:
            row = repository.get_case(conn, case_id=case_id)
            if row is None:
                raise KeyError(f"case id {case_id} not found")

        group = str(row["group"])
        formula = self._normalize_formula(str(row.get("active_formula") or ""))
        timeline = build_sandbox_timeline(formula=formula, group=group)
        return {
            "case_id": int(row["id"]),
            "group": group,
            "formula": timeline.formula,
            "moves_flat": timeline.moves_flat,
            "move_steps": timeline.move_steps,
            "step_count": len(timeline.move_steps),
            "initial_state": timeline.initial_state,
            "states_by_step": timeline.states_by_step,
            "highlight_by_step": timeline.highlight_by_step,
            "state_slots": timeline.state_slots,
            "playback_config": self._sandbox_playback_config(),
            "face_colors": self._sandbox_face_colors(),
        }

    def list_alternatives(self, case_id: int) -> list[dict[str, Any]]:
        with connect(self.db_path) as conn:
            case_row = repository.get_case(conn, case_id=case_id)
            if case_row is None:
                raise KeyError(f"case id {case_id} not found")
            return repository.list_case_alternatives(conn, case_id=case_id)

    def activate_case_algorithm(self, case_id: int, algorithm_id: int) -> dict[str, Any]:
        with connect(self.db_path) as conn:
            updated = repository.set_case_selected_algorithm(conn, case_id=case_id, algorithm_id=algorithm_id)
            self._refresh_case_recognizer(conn, updated)
            refreshed = repository.get_case(conn, case_id=case_id)
            if refreshed is None:
                raise KeyError(f"case id {case_id} not found")
            updated = refreshed
            return self._decorate_case(updated, conn, include_jobs=True)

    def activate_alternative(self, case_id: int, algorithm_id: int) -> dict[str, Any]:
        return self.activate_case_algorithm(case_id=case_id, algorithm_id=algorithm_id)

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
            self._refresh_case_recognizer(conn, row)
            refreshed = repository.get_case(conn, case_id=case_id)
            if refreshed is None:
                raise KeyError(f"case id {case_id} not found")
            row = refreshed
            return self._decorate_case(row, conn, include_jobs=True)

    def create_alternative(
        self,
        case_id: int,
        formula: str,
        name: str | None = None,
        activate: bool = True,
    ) -> dict[str, Any]:
        return self.create_case_custom_algorithm(
            case_id=case_id,
            formula=formula,
            name=name,
            activate=activate,
        )

    def delete_case_algorithm(
        self,
        case_id: int,
        algorithm_id: int,
        purge_media: bool = True,
    ) -> dict[str, Any]:
        removed_paths: list[str] = []
        with connect(self.db_path) as conn:
            deleted = repository.delete_case_algorithm(
                conn,
                case_id=case_id,
                algorithm_id=algorithm_id,
            )
            removed_paths = list(deleted.get("deleted_output_paths", []))
            row = repository.get_case(conn, case_id=case_id)
            if row is None:
                raise KeyError(f"case id {case_id} not found")
            self._refresh_case_recognizer(conn, row)
            refreshed = repository.get_case(conn, case_id=case_id)
            if refreshed is None:
                raise KeyError(f"case id {case_id} not found")
            case_payload = self._decorate_case(refreshed, conn, include_jobs=True)

        if purge_media:
            self._purge_output_paths(removed_paths)

        return {
            "case": case_payload,
            "deleted_algorithm_id": algorithm_id,
            "deleted_output_paths": removed_paths,
        }

    def delete_alternative(
        self,
        case_id: int,
        algorithm_id: int,
        purge_media: bool = True,
    ) -> dict[str, Any]:
        return self.delete_case_algorithm(
            case_id=case_id,
            algorithm_id=algorithm_id,
            purge_media=purge_media,
        )

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
            case_row = repository.get_case(conn, case_id=int(created["case_id"]))
            if case_row is not None:
                self._refresh_case_recognizer(conn, case_row)
            return self._decorate_algorithm(created, conn)

    def set_progress(self, algorithm_id: int, status: str) -> dict[str, Any]:
        with connect(self.db_path) as conn:
            repository.set_progress_status(conn, algorithm_id=algorithm_id, status=status)
            row = repository.get_algorithm(conn, algorithm_id)
            if row is None:
                raise KeyError(f"algorithm id {algorithm_id} not found")
            return self._decorate_algorithm(row, conn)

    def set_case_progress(self, case_id: int, status: str) -> dict[str, Any]:
        with connect(self.db_path) as conn:
            case_row = repository.get_case(conn, case_id=case_id)
            if case_row is None:
                raise KeyError(f"case id {case_id} not found")
            algorithm_id = case_row.get("active_algorithm_id")
            if algorithm_id is None:
                raise ValueError("Case has no active algorithm")
            repository.set_progress_status(conn, algorithm_id=int(algorithm_id), status=status)
            refreshed = repository.get_case(conn, case_id=case_id)
            if refreshed is None:
                raise KeyError(f"case id {case_id} not found")
            return self._decorate_case(refreshed, conn, include_jobs=True)

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

    def queue_case_render(self, case_id: int, quality: str) -> dict[str, Any]:
        return self.enqueue_case_render(case_id=case_id, quality=quality)

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
                    "draft": self._artifact_payload(conn, draft_art),
                    "high": self._artifact_payload(conn, high_art),
                },
            }

    def case_queue_status(self, case_id: int) -> dict[str, Any]:
        return self.queue_status(case_id=case_id)

    def process_next_job(self, manim_threads: int | None = None) -> dict[str, Any] | None:
        job_id: int | None = None
        algorithm_id: int | None = None
        quality = ""
        formula_norm = ""
        request: RenderRequest | None = None
        allow_rerender = False
        with connect(self.db_path) as conn:
            job = repository.claim_next_pending_job(conn)
            if job is None:
                return None

            job_id = int(job["id"])
            algorithm_id = int(job["algorithm_id"])
            quality = str(job["quality"])
            algorithm = repository.get_algorithm(conn, algorithm_id)
            if algorithm is None:
                return repository.mark_job_failed(conn, job_id, "Algorithm not found")

            formula = str(algorithm["formula"]).strip()
            if not formula:
                return repository.mark_job_failed(conn, job_id, "Algorithm formula is empty")

            try:
                formula_norm = self._normalize_formula(formula)
                reused_shared = self._reuse_case_formula_artifact(
                    conn,
                    algorithm=algorithm,
                    quality=quality,
                    formula_norm=formula_norm,
                )
                if reused_shared is not None:
                    return repository.mark_job_done(
                        conn,
                        job_id=job_id,
                        plan_action="reuse_case_formula_artifact",
                        output_name=reused_shared["output_name"],
                        output_path=reused_shared["output_path"],
                    )

                request = self._build_request(
                    algorithm=algorithm,
                    quality=quality,
                    manim_threads=manim_threads,
                )
                plan = self.renderer_client.plan(request=request, repo_root=self.repo_root)

                if (
                    plan.action == "confirm_rerender"
                    and "identical formula" in plan.reason.lower()
                    and self._plan_output_exists(plan)
                ):
                    rel_output_path = self._path_to_output_path(plan.final_path)
                    repository.upsert_render_artifact(
                        conn,
                        algorithm_id=algorithm_id,
                        quality=quality,
                        output_name=plan.output_name,
                        output_path=rel_output_path,
                        formula_norm=formula_norm,
                        repeat=1,
                    )
                    return repository.mark_job_done(
                        conn,
                        job_id=job_id,
                        plan_action="reuse_existing",
                        output_name=plan.output_name,
                        output_path=rel_output_path,
                    )

                allow_rerender = plan.action == "confirm_rerender"
            except Exception as exc:
                return repository.mark_job_failed(conn, job_id=job_id, error_message=str(exc))

        if request is None or job_id is None or algorithm_id is None:
            return None

        try:
            result = self.renderer_client.render(
                request=request,
                repo_root=self.repo_root,
                allow_rerender=allow_rerender,
            )
        except Exception as exc:
            with connect(self.db_path) as conn:
                return repository.mark_job_failed(conn, job_id=job_id, error_message=str(exc))

        rel_output_path = self._path_to_output_path(result.final_path)
        with connect(self.db_path) as conn:
            repository.upsert_render_artifact(
                conn,
                algorithm_id=algorithm_id,
                quality=quality,
                output_name=result.output_name,
                output_path=rel_output_path,
                formula_norm=formula_norm,
                repeat=1,
            )
            return repository.mark_job_done(
                conn,
                job_id=job_id,
                plan_action=result.action,
                output_name=result.output_name,
                output_path=rel_output_path,
            )

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
        formula_norm = self._normalize_formula(formula)

        if quality == "high":
            draft_artifact = repository.get_render_artifact(conn, algorithm_id, "draft")
            if not self._is_existing_artifact(draft_artifact):
                if draft_artifact is not None:
                    repository.delete_render_artifact(conn, int(draft_artifact["id"]))
                shared_draft = self._reuse_case_formula_artifact(
                    conn,
                    algorithm=algorithm,
                    quality="draft",
                    formula_norm=formula_norm,
                )
                if shared_draft is None:
                    raise ValueError("HD render requires existing draft artifact")

        active = repository.get_active_job(conn, algorithm_id=algorithm_id, quality=quality)
        if active is not None:
            return {
                "job": active,
                "reused": False,
                "message": "Job already in queue",
            }

        cached_artifact = repository.get_render_artifact(conn, algorithm_id, quality)
        if cached_artifact is not None and not self._is_existing_artifact(cached_artifact):
            repository.delete_render_artifact(conn, int(cached_artifact["id"]))
            cached_artifact = None
        if cached_artifact is not None and cached_artifact.get("formula_norm") == formula_norm and self._is_existing_artifact(cached_artifact):
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

        reused_shared = self._reuse_case_formula_artifact(
            conn,
            algorithm=algorithm,
            quality=quality,
            formula_norm=formula_norm,
        )
        if reused_shared is not None:
            done_job = repository.insert_render_job(
                conn,
                algorithm_id=algorithm_id,
                quality=quality,
                status="DONE",
                plan_action="reuse_case_formula_artifact",
                output_name=str(reused_shared["output_name"]),
                output_path=str(reused_shared["output_path"]),
            )
            return {
                "job": done_job,
                "reused": True,
                "message": "Existing case artifact reused",
            }

        request = self._build_request(algorithm=algorithm, quality=quality)
        plan = self.renderer_client.plan(request=request, repo_root=self.repo_root)

        if plan.action == "confirm_rerender" and "identical formula" in plan.reason.lower() and self._plan_output_exists(plan):
            rel_output_path = self._path_to_output_path(plan.final_path)
            repository.upsert_render_artifact(
                conn,
                algorithm_id=algorithm_id,
                quality=quality,
                output_name=plan.output_name,
                output_path=rel_output_path,
                formula_norm=formula_norm,
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

    def _build_request(
        self,
        algorithm: dict[str, Any],
        quality: str,
        manim_threads: int | None = None,
    ) -> RenderRequest:
        formula_norm = self._normalize_formula(str(algorithm["formula"]))
        case_code = str(algorithm.get("case_code") or "case")
        group = str(algorithm["group"])
        case_slug = re.sub(r"[^a-z0-9]+", "_", case_code.lower()).strip("_") or "case"
        formula_hash = hashlib.sha1(formula_norm.encode("utf-8")).hexdigest()[:12]
        storage_name = f"{group.lower()}_{case_slug}_{formula_hash}"
        display_name = (
            str(algorithm.get("case_title") or "").strip()
            or str(algorithm.get("display_name") or "").strip()
            or str(algorithm.get("name") or "").strip()
            or case_code
        )
        return RenderRequest(
            formula=formula_norm,
            name=storage_name,
            display_name=display_name,
            group=group,
            quality=quality,
            repeat=1,
            play=False,
            manim_threads=manim_threads,
        )

    def _reuse_case_formula_artifact(
        self,
        conn,
        algorithm: dict[str, Any],
        quality: str,
        formula_norm: str,
    ) -> dict[str, Any] | None:
        shared = repository.find_case_render_artifact_by_formula(
            conn,
            case_id=int(algorithm["case_id"]),
            quality=quality,
            formula_norm=formula_norm,
            exclude_algorithm_id=int(algorithm["id"]),
        )
        if shared is None:
            return None
        output_path = str(shared["output_path"])
        if self.renderer_client.local_paths and not (self.repo_root / output_path).exists():
            repository.delete_render_artifact(conn, int(shared["id"]))
            return None
        repository.upsert_render_artifact(
            conn,
            algorithm_id=int(algorithm["id"]),
            quality=quality,
            output_name=str(shared["output_name"]),
            output_path=output_path,
            formula_norm=formula_norm,
            repeat=int(shared.get("repeat", 1)),
        )
        return shared

    @staticmethod
    def _normalize_formula(formula: str) -> str:
        return " ".join(formula.split())

    @staticmethod
    def _sandbox_playback_config() -> dict[str, Any]:
        config = _resolved_execution_config()
        return {
            "run_time_sec": config.run_time,
            "double_turn_multiplier": config.double_turn_multiplier,
            "inter_move_pause_ratio": config.inter_move_pause_ratio,
            "rate_func": _SANDBOX_RATE_FUNC,
        }

    @staticmethod
    def _sandbox_face_colors() -> dict[str, str]:
        return {
            face: color
            for face, color in zip(FACE_ORDER, CONTRAST_SAFE_CUBE_COLORS, strict=True)
        }

    def _is_existing_artifact(self, artifact: dict[str, Any] | None) -> bool:
        if artifact is None:
            return False
        output_path = str(artifact.get("output_path") or "").strip()
        if not output_path:
            return False
        if not self.renderer_client.local_paths:
            return True
        return (self.repo_root / output_path).exists()

    def _plan_output_exists(self, plan) -> bool:
        if not self.renderer_client.local_paths:
            return True
        return plan.final_path.exists()

    def _path_to_output_path(self, path: Path) -> str:
        if self.renderer_client.local_paths:
            try:
                return str(path.relative_to(self.repo_root))
            except ValueError:
                return str(path)
        return str(path)

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
                "draft": self._artifact_payload(conn, draft),
                "high": self._artifact_payload(conn, high),
            },
        }
        if include_jobs:
            payload["jobs"] = repository.list_latest_jobs_for_algorithm(conn, algorithm_id)
        return payload

    def _artifact_payload(self, conn, artifact: dict[str, Any] | None) -> dict[str, Any] | None:
        if self.renderer_client.local_paths and artifact is not None and not self._is_existing_artifact(artifact):
            repository.delete_render_artifact(conn, int(artifact["id"]))
            return None
        if not self._is_existing_artifact(artifact):
            return None
        output_path = str(artifact["output_path"])
        if output_path.startswith("http://") or output_path.startswith("https://"):
            video_url = output_path
        else:
            video_url = f"/{output_path}"
        return {
            "quality": artifact["quality"],
            "output_name": artifact["output_name"],
            "output_path": output_path,
            "video_url": video_url,
            "updated_at": artifact["updated_at"],
        }

    def _refresh_case_recognizer(self, conn, case_row: dict[str, Any]) -> None:
        case_id = int(case_row["id"])
        category = str(case_row["group"])
        case_code = str(case_row["case_code"])
        formula = str(case_row.get("active_formula") or "")
        assets = ensure_recognizer_assets(
            self.db_path.parent,
            category=category,
            case_code=case_code,
            formula=formula,
        )
        repository.update_case_recognizer_paths(
            conn,
            case_id=case_id,
            svg_rel_path=assets.svg_rel_path,
            png_rel_path=assets.png_rel_path,
        )

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
                "draft": self._artifact_payload(conn, draft),
                "high": self._artifact_payload(conn, high),
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

    def _purge_output_paths(self, output_paths: list[str]) -> None:
        if not output_paths:
            return
        if not self.renderer_client.local_paths:
            return
        root = self.repo_root.resolve()
        existing_rel_paths: set[str] = set()
        for rel in output_paths:
            candidate = (self.repo_root / rel).resolve()
            if not str(candidate).startswith(str(root)):
                continue
            existing_rel_paths.add(rel)
            if candidate.exists() and candidate.is_file():
                candidate.unlink()

        if not existing_rel_paths:
            return

        catalog_path = self.repo_root / "media" / "videos" / "render_catalog.json"
        if not catalog_path.exists():
            return
        try:
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        except Exception:
            return
        records = catalog.get("records")
        if not isinstance(records, list):
            return
        filtered = [
            record for record in records
            if str(record.get("path") or "") not in existing_rel_paths
        ]
        if len(filtered) == len(records):
            return
        catalog["records"] = filtered
        catalog_path.write_text(json.dumps(catalog, ensure_ascii=True, indent=2), encoding="utf-8")
