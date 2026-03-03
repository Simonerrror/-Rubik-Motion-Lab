from __future__ import annotations

import pytest

from cubeanim.cards.renderer_client import (
    HttpRendererClient,
    LocalRendererClient,
    build_renderer_client_from_env,
)


def test_renderer_client_defaults_to_local(monkeypatch) -> None:
    monkeypatch.delenv("CUBEANIM_RENDER_BACKEND", raising=False)
    monkeypatch.delenv("CUBEANIM_RENDER_API_URL", raising=False)
    client = build_renderer_client_from_env()
    assert isinstance(client, LocalRendererClient)
    assert client.local_paths is True


def test_renderer_client_http_requires_url(monkeypatch) -> None:
    monkeypatch.setenv("CUBEANIM_RENDER_BACKEND", "http")
    monkeypatch.delenv("CUBEANIM_RENDER_API_URL", raising=False)
    with pytest.raises(ValueError):
        build_renderer_client_from_env()


def test_renderer_client_http_reads_timeout(monkeypatch) -> None:
    monkeypatch.setenv("CUBEANIM_RENDER_BACKEND", "remote")
    monkeypatch.setenv("CUBEANIM_RENDER_API_URL", "http://127.0.0.1:9000")
    monkeypatch.setenv("CUBEANIM_RENDER_API_TIMEOUT_SEC", "12.5")
    client = build_renderer_client_from_env()
    assert isinstance(client, HttpRendererClient)
    assert client.base_url == "http://127.0.0.1:9000"
    assert client.timeout_sec == pytest.approx(12.5)
    assert client.local_paths is False


def test_renderer_client_rejects_unknown_backend(monkeypatch) -> None:
    monkeypatch.setenv("CUBEANIM_RENDER_BACKEND", "grpc")
    with pytest.raises(ValueError):
        build_renderer_client_from_env()
