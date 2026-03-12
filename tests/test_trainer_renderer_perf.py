from __future__ import annotations

import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

playwright_sync_api = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright


REPO_ROOT = Path(__file__).resolve().parents[1]
TRAINER_ROOT = REPO_ROOT / "apps" / "trainer"


class _StaticServer:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.base_url = ""

    def __enter__(self) -> str:
        handler = partial(SimpleHTTPRequestHandler, directory=str(self.root_dir))
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        host, port = self.httpd.server_address
        self.base_url = f"http://{host}:{port}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        return self.base_url

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
        if self.thread:
            self.thread.join(timeout=2.0)


@pytest.mark.e2e
def test_renderer_perf_sanity_for_baseline_and_instanced_paths() -> None:
    with _StaticServer(TRAINER_ROOT) as base_url, sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(f"{base_url}/index.html?layout=desktop", wait_until="domcontentloaded", timeout=20000)
        result = page.evaluate(
            """
            async () => {
              const core = await import('./modules/cube-core/model.js');
              const scenarios = [3, 4, 5];
              const stats = [];
              for (const size of scenarios) {
                const canvas = document.createElement('canvas');
                canvas.width = 640;
                canvas.height = 480;
                canvas.style.width = '640px';
                canvas.style.height = '480px';
                document.body.appendChild(canvas);
                const renderer = window.CubeSandbox3D.createSandbox3D(canvas);
                const slots = core.createSurfaceStateSlots(size);
                const solved = slots.map((slot) => slot.face).join('');
                const model = core.createCubeModel(size, solved, slots);
                const snapshot = core.snapshotForState(model);
                renderer.buildScene(size);
                renderer.renderSnapshot(snapshot);
                stats.push({ size, backend: renderer.getBackendName(), ...renderer.getRenderStats() });
                renderer.dispose();
                canvas.remove();
              }
              return stats;
            }
            """
        )
        browser.close()

    by_size = {int(item["size"]): item for item in result}
    assert by_size[3]["backend"] == "baseline"
    assert by_size[4]["backend"] == "instanced"
    assert by_size[5]["backend"] == "instanced"

    assert by_size[3]["cubieObjects"] == 26
    assert by_size[4]["bodyInstances"] == 56
    assert by_size[5]["bodyInstances"] == 98

    assert by_size[4]["stickerFaceMeshes"] <= 6
    assert by_size[5]["stickerFaceMeshes"] <= 6
    assert by_size[4]["drawCalls"] <= 10
    assert by_size[5]["drawCalls"] <= 10

    assert by_size[5]["drawCalls"] < by_size[3]["drawCalls"]
    assert by_size[5]["stickerInstances"] == 150
