from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

try:
    import httpx
except Exception:  # pragma: no cover - optional for local-only workflows
    httpx = None

from cubeanim.render_service import RenderPlan, RenderRequest, RenderResult, plan_formula_render, render_formula

_RENDER_BACKEND_ENV = "CUBEANIM_RENDER_BACKEND"
_RENDER_API_URL_ENV = "CUBEANIM_RENDER_API_URL"
_RENDER_API_TIMEOUT_ENV = "CUBEANIM_RENDER_API_TIMEOUT_SEC"


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


@dataclass(frozen=True)
class HttpRendererClient:
    base_url: str
    timeout_sec: float = 60.0
    local_paths: bool = False

    @staticmethod
    def _request_payload(request: RenderRequest) -> dict[str, Any]:
        return {
            "formula": request.formula,
            "name": request.name,
            "display_name": request.display_name,
            "group": str(request.group),
            "quality": request.quality,
            "repeat": request.repeat,
            "play": request.play,
            "manim_bin": request.manim_bin,
            "manim_file": request.manim_file,
            "manim_threads": request.manim_threads,
        }

    @staticmethod
    def _unwrap_payload(payload: dict[str, Any]) -> dict[str, Any]:
        wrapped = payload.get("data")
        if isinstance(wrapped, dict):
            return wrapped
        return payload

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if httpx is None:
            raise RuntimeError("httpx is required for CUBEANIM_RENDER_BACKEND=http")
        with httpx.Client(base_url=self.base_url, timeout=self.timeout_sec) as client:
            response = client.post(path, json=payload)
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict):
                raise RuntimeError("Renderer API returned non-object response")
            return self._unwrap_payload(body)

    def plan(self, request: RenderRequest, repo_root: Path) -> RenderPlan:
        payload = self._post(
            "/plan",
            {
                "request": self._request_payload(request),
                "repo_root": str(repo_root),
            },
        )
        return RenderPlan(
            action=str(payload["action"]),
            output_name=str(payload["output_name"]),
            final_path=Path(str(payload["final_path"])),
            reason=str(payload.get("reason") or ""),
        )

    def render(
        self,
        request: RenderRequest,
        repo_root: Path,
        allow_rerender: bool = False,
    ) -> RenderResult:
        payload = self._post(
            "/render",
            {
                "request": self._request_payload(request),
                "repo_root": str(repo_root),
                "allow_rerender": allow_rerender,
            },
        )
        return RenderResult(
            output_name=str(payload["output_name"]),
            final_path=Path(str(payload["final_path"])),
            action=str(payload["action"]),
        )


def build_renderer_client_from_env() -> RendererClient:
    backend = os.environ.get(_RENDER_BACKEND_ENV, "local").strip().lower() or "local"
    if backend in {"local", "manim"}:
        return LocalRendererClient()

    if backend in {"http", "remote"}:
        base_url = os.environ.get(_RENDER_API_URL_ENV, "").strip()
        if not base_url:
            raise ValueError(f"{_RENDER_API_URL_ENV} is required when {_RENDER_BACKEND_ENV}={backend}")
        raw_timeout = os.environ.get(_RENDER_API_TIMEOUT_ENV, "60").strip() or "60"
        try:
            timeout = float(raw_timeout)
        except ValueError as exc:
            raise ValueError(f"{_RENDER_API_TIMEOUT_ENV} must be a float") from exc
        if timeout <= 0:
            raise ValueError(f"{_RENDER_API_TIMEOUT_ENV} must be > 0")
        return HttpRendererClient(base_url=base_url, timeout_sec=timeout)

    raise ValueError(f"Unsupported {_RENDER_BACKEND_ENV}: {backend}")
