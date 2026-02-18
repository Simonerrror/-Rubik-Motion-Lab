from __future__ import annotations

from pathlib import Path

from cubeanim.cards.db import connect
from cubeanim.cards.services import CardsService
from cubeanim.render_service import RenderPlan, RenderResult
import cubeanim.cards.services as cards_services


def test_worker_processes_pending_job_without_real_manim(tmp_path: Path, monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    service = CardsService.create(repo_root=repo_root, db_path=tmp_path / "cards.db")

    algos = service.list_algorithms(group="PLL")
    target = next(item for item in algos if item["formula"])
    algorithm_id = int(target["id"])

    queued = service.enqueue_render(algorithm_id=algorithm_id, quality="draft")
    assert queued["job"]["status"] in {"PENDING", "DONE"}

    if queued["job"]["status"] == "DONE":
        return

    fake_final = repo_root / "media" / "videos" / "PLL" / "draft" / "TEST_CARD.mp4"

    def fake_plan_formula_render(request, repo_root):
        return RenderPlan(
            action="render",
            output_name=request.name or "TEST_CARD",
            final_path=fake_final,
            reason="forced for test",
        )

    def fake_render_formula(request, repo_root, allow_rerender=False):
        fake_final.parent.mkdir(parents=True, exist_ok=True)
        fake_final.write_bytes(b"fake")
        return RenderResult(
            output_name=request.name or "TEST_CARD",
            final_path=fake_final,
            action="render",
        )

    monkeypatch.setattr(cards_services, "plan_formula_render", fake_plan_formula_render)
    monkeypatch.setattr(cards_services, "render_formula", fake_render_formula)

    processed = service.process_next_job()
    assert processed is not None
    assert processed["status"] == "DONE"

    with connect(service.db_path) as conn:
        artifact = conn.execute(
            "SELECT output_path FROM render_artifacts WHERE algorithm_id = ? AND quality = 'draft'",
            (algorithm_id,),
        ).fetchone()
    assert artifact is not None
