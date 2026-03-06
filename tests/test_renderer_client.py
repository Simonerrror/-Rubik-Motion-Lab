from __future__ import annotations

import pytest

from cubeanim.cards.renderer_client import LocalRendererClient, build_renderer_client_from_env


def test_renderer_client_defaults_to_local(monkeypatch) -> None:
    monkeypatch.delenv("CUBEANIM_RENDER_BACKEND", raising=False)
    client = build_renderer_client_from_env()
    assert isinstance(client, LocalRendererClient)
    assert client.local_paths is True


def test_renderer_client_accepts_explicit_local_backend(monkeypatch) -> None:
    monkeypatch.setenv("CUBEANIM_RENDER_BACKEND", "local")
    client = build_renderer_client_from_env()
    assert isinstance(client, LocalRendererClient)
    assert client.local_paths is True


def test_renderer_client_rejects_removed_remote_backends(monkeypatch) -> None:
    monkeypatch.setenv("CUBEANIM_RENDER_BACKEND", "http")
    with pytest.raises(ValueError, match="Remote renderer backends were removed"):
        build_renderer_client_from_env()
