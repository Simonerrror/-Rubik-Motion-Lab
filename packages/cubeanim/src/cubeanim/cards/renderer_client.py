from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from cubeanim_domain.render_contracts import RenderPlan, RenderRequest, RenderResult
from cubeanim_renderer.render_service import plan_formula_render, render_formula

_RENDER_BACKEND_ENV = "CUBEANIM_RENDER_BACKEND"


class RendererClient(Protocol):
    local_paths: bool

    def plan(self, request: RenderRequest, repo_root: Path) -> RenderPlan:
        raise NotImplementedError

    def render(
        self,
        request: RenderRequest,
        repo_root: Path,
        allow_rerender: bool = False,
    ) -> RenderResult:
        raise NotImplementedError


@dataclass(frozen=True)
class LocalRendererClient:
    local_paths: bool = True

    def plan(self, request: RenderRequest, repo_root: Path) -> RenderPlan:
        return plan_formula_render(request=request, repo_root=repo_root)

    def render(
        self,
        request: RenderRequest,
        repo_root: Path,
        allow_rerender: bool = False,
    ) -> RenderResult:
        return render_formula(
            request=request,
            repo_root=repo_root,
            allow_rerender=allow_rerender,
        )


def build_renderer_client_from_env() -> RendererClient:
    backend = os.environ.get(_RENDER_BACKEND_ENV, "").strip().lower()
    if backend in {"", "local", "manim"}:
        return LocalRendererClient()
    raise ValueError(
        f"Unsupported {_RENDER_BACKEND_ENV}: {backend}. "
        "Remote renderer backends were removed; use the local renderer tool."
    )
