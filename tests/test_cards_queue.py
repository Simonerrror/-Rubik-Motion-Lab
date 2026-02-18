from __future__ import annotations

from pathlib import Path

from cubeanim.cards.services import CardsService
from cubeanim.render_service import RenderPlan
import cubeanim.cards.services as cards_services


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

    monkeypatch.setattr(cards_services, "plan_formula_render", fake_plan_formula_render)

    queued = service.enqueue_render(algorithm_id=algo_id, quality="draft")
    assert queued["reused"] is True
    assert queued["job"]["status"] == "DONE"
    assert queued["job"]["plan_action"] == "reuse_existing"
