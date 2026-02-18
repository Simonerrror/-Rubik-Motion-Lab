#!/usr/bin/env python3
from __future__ import annotations

import sys
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cubeanim.cards.services import CardsService

INDEX_HTML = REPO_ROOT / "index.html"
STATIC_DIR = REPO_ROOT / "static"
RUNTIME_ASSETS_DIR = REPO_ROOT / "data" / "cards" / "runtime"
MEDIA_DIR = REPO_ROOT / "media"

def _create_service() -> CardsService:
    db_env = os.environ.get("CUBEANIM_CARDS_DB", "").strip()
    db_path = Path(db_env) if db_env else None
    return CardsService.create(repo_root=REPO_ROOT, db_path=db_path)


service = _create_service()
app = FastAPI(title="Rubik Motion Lab Cards API", version="1.0.0")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
if RUNTIME_ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=RUNTIME_ASSETS_DIR), name="assets")
if MEDIA_DIR.exists():
    app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")


class CustomAlgorithmRequest(BaseModel):
    name: str
    formula: str
    group: str = Field(pattern="^(F2L|OLL|PLL)$")
    case_code: str


class ProgressRequest(BaseModel):
    algorithm_id: int
    status: str = Field(pattern="^(NEW|IN_PROGRESS|LEARNED)$")


class QueueRequest(BaseModel):
    algorithm_id: int
    quality: str = Field(pattern="^(draft|high)$")


class CaseQueueRequest(BaseModel):
    quality: str = Field(pattern="^(draft|high)$")


class ActivateCaseRequest(BaseModel):
    algorithm_id: int


class CaseCustomAlgorithmRequest(BaseModel):
    formula: str
    name: str | None = None
    activate: bool = True


@app.get("/")
def root() -> FileResponse:
    if not INDEX_HTML.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(INDEX_HTML)


@app.get("/api/algorithms")
def api_list_algorithms(group: str = Query(default="ALL")) -> dict:
    normalized_group = group.strip().upper() or "ALL"
    if normalized_group not in {"ALL", "F2L", "OLL", "PLL"}:
        raise HTTPException(status_code=400, detail="Invalid group")

    try:
        items = service.list_algorithms(group=normalized_group)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "data": items}


@app.get("/api/cases")
def api_list_cases(group: str = Query(...)) -> dict:
    normalized_group = group.strip().upper()
    if normalized_group not in {"F2L", "OLL", "PLL"}:
        raise HTTPException(status_code=400, detail="Invalid group")
    try:
        items = service.list_cases(group=normalized_group)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "data": items}


@app.get("/api/reference/sets")
def api_list_reference_sets(category: str = Query(...)) -> dict:
    normalized = category.strip().upper()
    if normalized not in {"F2L", "OLL", "PLL"}:
        raise HTTPException(status_code=400, detail="Invalid category")
    try:
        items = service.list_reference_sets(category=normalized)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "data": items}


@app.get("/api/cases/{case_id}")
def api_get_case(case_id: int) -> dict:
    try:
        item = service.get_case(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "data": item}


@app.post("/api/cases/{case_id}/activate")
def api_activate_case_algorithm(case_id: int, payload: ActivateCaseRequest) -> dict:
    try:
        item = service.activate_case_algorithm(case_id=case_id, algorithm_id=payload.algorithm_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "data": item}


@app.post("/api/cases/{case_id}/custom")
def api_create_case_custom_algorithm(case_id: int, payload: CaseCustomAlgorithmRequest) -> dict:
    try:
        item = service.create_case_custom_algorithm(
            case_id=case_id,
            formula=payload.formula,
            name=payload.name,
            activate=payload.activate,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "data": item}


@app.delete("/api/cases/{case_id}/algorithms/{algorithm_id}")
def api_delete_case_algorithm(
    case_id: int,
    algorithm_id: int,
    purge_media: bool = Query(default=True),
) -> dict:
    try:
        item = service.delete_case_algorithm(
            case_id=case_id,
            algorithm_id=algorithm_id,
            purge_media=purge_media,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "data": item}


@app.post("/api/cases/{case_id}/queue")
def api_enqueue_case_render(case_id: int, payload: CaseQueueRequest) -> dict:
    try:
        item = service.enqueue_case_render(case_id=case_id, quality=payload.quality)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "data": item}


@app.get("/api/algorithms/{algorithm_id}")
def api_get_algorithm(algorithm_id: int) -> dict:
    try:
        item = service.get_algorithm(algorithm_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "data": item}


@app.post("/api/algorithms/custom")
def api_create_custom_algorithm(payload: CustomAlgorithmRequest) -> dict:
    try:
        item = service.create_custom_algorithm(
            name=payload.name,
            formula=payload.formula,
            group=payload.group,
            case_code=payload.case_code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "data": item}


@app.post("/api/progress")
def api_update_progress(payload: ProgressRequest) -> dict:
    try:
        item = service.set_progress(payload.algorithm_id, payload.status)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "data": item}


@app.post("/api/queue")
def api_enqueue_render(payload: QueueRequest) -> dict:
    try:
        item = service.enqueue_render(payload.algorithm_id, payload.quality)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "data": item}


@app.get("/api/queue/status")
def api_queue_status(
    algorithm_id: int | None = Query(default=None, ge=1),
    case_id: int | None = Query(default=None, ge=1),
) -> dict:
    if algorithm_id is None and case_id is None:
        raise HTTPException(status_code=400, detail="algorithm_id or case_id is required")
    try:
        item = service.queue_status(algorithm_id=algorithm_id, case_id=case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "data": item}


@app.get("/api/recognizers/{algorithm_id}")
def api_get_recognizer(algorithm_id: int) -> dict:
    try:
        item = service.get_algorithm(algorithm_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    recognizer_url = item.get("recognizer_url")
    return {
        "ok": True,
        "data": {
            "algorithm_id": algorithm_id,
            "recognizer_url": recognizer_url,
        },
    }


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/api/admin/reset-runtime")
def api_admin_reset_runtime() -> dict:
    try:
        item = service.reset_runtime()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "data": item}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("scripts.cards_api:app", host="127.0.0.1", port=8008, reload=True)
