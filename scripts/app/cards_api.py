#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[2]
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
app = FastAPI(title="Rubik Motion Lab Cards API", version="2.0.0")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
if RUNTIME_ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=RUNTIME_ASSETS_DIR), name="assets")
if MEDIA_DIR.exists():
    app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")


class ActivateAlternativeRequest(BaseModel):
    algorithm_id: int


class CreateAlternativeRequest(BaseModel):
    formula: str
    name: str | None = None
    activate: bool = True


class CaseRenderRequest(BaseModel):
    quality: str = Field(pattern="^(draft|high)$")


class CaseProgressRequest(BaseModel):
    status: str = Field(pattern="^(NEW|IN_PROGRESS|LEARNED)$")


@app.get("/")
def root() -> FileResponse:
    if not INDEX_HTML.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(INDEX_HTML)


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


@app.get("/api/cases/{case_id}")
def api_get_case(case_id: int) -> dict:
    try:
        item = service.get_case(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "data": item}


@app.get("/api/cases/{case_id}/alternatives")
def api_list_alternatives(case_id: int) -> dict:
    try:
        items = service.list_alternatives(case_id=case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "data": items}


@app.post("/api/cases/{case_id}/alternatives")
def api_create_alternative(case_id: int, payload: CreateAlternativeRequest) -> dict:
    try:
        item = service.create_alternative(
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


@app.post("/api/cases/{case_id}/active-algorithm")
def api_activate_alternative(case_id: int, payload: ActivateAlternativeRequest) -> dict:
    try:
        item = service.activate_alternative(case_id=case_id, algorithm_id=payload.algorithm_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "data": item}


@app.delete("/api/cases/{case_id}/alternatives/{algorithm_id}")
def api_delete_alternative(
    case_id: int,
    algorithm_id: int,
    purge_media: bool = Query(default=True),
) -> dict:
    try:
        item = service.delete_alternative(
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


@app.post("/api/cases/{case_id}/renders")
def api_enqueue_case_render(case_id: int, payload: CaseRenderRequest) -> dict:
    try:
        item = service.queue_case_render(case_id=case_id, quality=payload.quality)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "data": item}


@app.get("/api/cases/{case_id}/renders/status")
def api_case_render_status(case_id: int) -> dict:
    try:
        item = service.case_queue_status(case_id=case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "data": item}


@app.patch("/api/cases/{case_id}/progress")
def api_set_case_progress(case_id: int, payload: CaseProgressRequest) -> dict:
    try:
        item = service.set_case_progress(case_id=case_id, status=payload.status)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "data": item}


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

    host = os.environ.get("CUBEANIM_CARDS_HOST", "127.0.0.1").strip() or "127.0.0.1"
    raw_port = os.environ.get("CUBEANIM_CARDS_PORT", "8008").strip() or "8008"
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise SystemExit(f"Invalid CUBEANIM_CARDS_PORT: {raw_port}") from exc

    uvicorn.run("scripts.app.cards_api:app", host=host, port=port, reload=True)
