from __future__ import annotations

from pathlib import Path
import threading
import time
from typing import Callable

from cubeanim.cards.db import connect
from cubeanim.cards import repository
from cubeanim.cards.services import CardsService
from cubeanim.render_service import RenderPlan


class _StubRendererClient:
    local_paths = True

    def __init__(
        self,
        plan_fn: Callable,
        render_fn: Callable | None = None,
    ) -> None:
        self._plan_fn = plan_fn
        self._render_fn = render_fn

    def plan(self, request, repo_root):
        return self._plan_fn(request, repo_root)

    def render(self, request, repo_root, allow_rerender=False):
        if self._render_fn is None:
            raise AssertionError("render() should not be called in this test")
        return self._render_fn(request, repo_root, allow_rerender=allow_rerender)


def test_enqueue_deduplicates_active_job(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    service = CardsService.create(repo_root=repo_root, db_path=tmp_path / "cards.db")

    algos = service.list_algorithms(group="PLL")
    target = next(item for item in algos if item["formula"])

    first = service.enqueue_render(algorithm_id=int(target["id"]), quality="draft")
    second = service.enqueue_render(algorithm_id=int(target["id"]), quality="draft")

    assert first["job"]["status"] in {"PENDING", "DONE"}
    if first["job"]["status"] == "PENDING":
        assert second["job"]["id"] == first["job"]["id"]


def test_enqueue_reuses_existing_identical_render(tmp_path: Path, monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    service = CardsService.create(repo_root=repo_root, db_path=tmp_path / "cards.db")

    algos = service.list_algorithms(group="PLL")
    target = next(item for item in algos if item["formula"])
    algo_id = int(target["id"])

    fake_final = repo_root / "media" / "videos" / "PLL" / "draft" / "reuse_for_test.mp4"
    fake_final.parent.mkdir(parents=True, exist_ok=True)
    fake_final.write_bytes(b"reuse")

    def fake_plan_formula_render(request, repo_root):
        return RenderPlan(
            action="confirm_rerender",
            output_name="reuse",
            final_path=fake_final,
            reason="An identical formula already exists",
        )

    service.renderer_client = _StubRendererClient(plan_fn=fake_plan_formula_render)

    queued = service.enqueue_render(algorithm_id=algo_id, quality="draft")
    assert queued["reused"] is True
    assert queued["job"]["status"] == "DONE"
    assert queued["job"]["plan_action"] == "reuse_existing"


def test_pending_queue_prioritizes_draft_before_high(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "cards.db"
    service = CardsService.create(repo_root=repo_root, db_path=db_path)
    algos = [item for item in service.list_algorithms(group="PLL") if item["formula"]]
    assert len(algos) >= 3

    high_algo_id = int(algos[0]["id"])
    draft_a_algo_id = int(algos[1]["id"])
    draft_b_algo_id = int(algos[2]["id"])

    with connect(db_path) as conn:
        repository.insert_render_job(conn, algorithm_id=high_algo_id, quality="high", status="PENDING")
        repository.insert_render_job(conn, algorithm_id=draft_a_algo_id, quality="draft", status="PENDING")
        repository.insert_render_job(conn, algorithm_id=draft_b_algo_id, quality="draft", status="PENDING")

        first = repository.claim_next_pending_job(conn)
        second = repository.claim_next_pending_job(conn)
        third = repository.claim_next_pending_job(conn)

    assert first is not None and first["quality"] == "draft"
    assert second is not None and second["quality"] == "draft"
    assert third is not None and third["quality"] == "high"
    assert int(first["algorithm_id"]) == draft_a_algo_id
    assert int(second["algorithm_id"]) == draft_b_algo_id
    assert int(third["algorithm_id"]) == high_algo_id


def test_storage_name_is_formula_based_not_algorithm_name(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "cards.db"
    service = CardsService.create(repo_root=repo_root, db_path=db_path)

    algos = [item for item in service.list_algorithms(group="PLL") if item["formula"]]
    target = algos[0]

    with connect(db_path) as conn:
        original = repository.get_algorithm(conn, int(target["id"]))
    assert original is not None
    request_a = service._build_request(original, quality="draft")
    assert request_a.name != original["name"]
    assert request_a.display_name == original["case_title"]

    case_id = int(target["case_id"])
    same_formula_case = service.create_case_custom_algorithm(
        case_id=case_id,
        formula=str(target["formula"]),
        name="Custom Alias",
        activate=True,
    )
    custom_id = int(same_formula_case["active_algorithm_id"])
    with connect(db_path) as conn:
        custom_algorithm = repository.get_algorithm(conn, custom_id)
    assert custom_algorithm is not None
    request_b = service._build_request(custom_algorithm, quality="draft")
    assert request_b.name == request_a.name
    assert request_b.display_name == custom_algorithm["case_title"]


def test_enqueue_reuses_same_case_formula_artifact(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "cards.db"
    service = CardsService.create(repo_root=repo_root, db_path=db_path)
    algos = [item for item in service.list_algorithms(group="PLL") if item["formula"]]
    target = algos[0]
    target_id = int(target["id"])

    rel_output = Path("media/videos/PLL/draft/legacy_named_video.mp4")
    full_output = repo_root / rel_output
    full_output.parent.mkdir(parents=True, exist_ok=True)
    full_output.write_bytes(b"legacy")

    formula_norm = " ".join(str(target["formula"]).split())
    with connect(db_path) as conn:
        repository.upsert_render_artifact(
            conn,
            algorithm_id=target_id,
            quality="draft",
            output_name="F",
            output_path=str(rel_output),
            formula_norm=formula_norm,
            repeat=1,
        )

    case_id = int(target["case_id"])
    custom_case = service.create_case_custom_algorithm(
        case_id=case_id,
        formula=str(target["formula"]),
        name="User Input Formula",
        activate=True,
    )
    custom_id = int(custom_case["active_algorithm_id"])
    queued = service.enqueue_render(algorithm_id=custom_id, quality="draft")

    assert queued["reused"] is True
    assert queued["job"]["status"] == "DONE"
    assert queued["job"]["plan_action"] == "reuse_case_formula_artifact"
    assert queued["job"]["output_name"] == "F"


def test_three_workers_drain_thirty_jobs_without_duplicate_claims(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "cards.db"
    service = CardsService.create(repo_root=repo_root, db_path=db_path)
    target = next(item for item in service.list_algorithms(group="PLL") if item["formula"])
    algorithm_id = int(target["id"])

    with connect(db_path) as conn:
        for _ in range(30):
            repository.insert_render_job(conn, algorithm_id=algorithm_id, quality="draft", status="PENDING")

    lock = threading.Lock()
    claimed_ids: list[int] = []
    processed_by_worker = {1: 0, 2: 0, 3: 0}

    def run_worker(worker_id: int) -> None:
        while True:
            with connect(db_path) as conn:
                job = repository.claim_next_pending_job(conn)
                if job is None:
                    return
                job_id = int(job["id"])
                repository.mark_job_done(
                    conn,
                    job_id=job_id,
                    plan_action="test_complete",
                    output_name=f"job_{job_id}",
                    output_path=f"media/videos/PLL/draft/job_{job_id}.mp4",
                )
            with lock:
                claimed_ids.append(job_id)
                processed_by_worker[worker_id] += 1
            time.sleep(0.005)

    threads = [threading.Thread(target=run_worker, args=(idx,), daemon=True) for idx in (1, 2, 3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10.0)

    with connect(db_path) as conn:
        pending = int(conn.execute("SELECT COUNT(*) FROM render_jobs WHERE status = 'PENDING'").fetchone()[0])
        running = int(conn.execute("SELECT COUNT(*) FROM render_jobs WHERE status = 'RUNNING'").fetchone()[0])
        done = int(conn.execute("SELECT COUNT(*) FROM render_jobs WHERE status = 'DONE'").fetchone()[0])

    assert len(claimed_ids) == 30
    assert len(set(claimed_ids)) == 30
    assert pending == 0
    assert running == 0
    assert done == 30
    assert all(processed_by_worker[idx] > 0 for idx in (1, 2, 3))
