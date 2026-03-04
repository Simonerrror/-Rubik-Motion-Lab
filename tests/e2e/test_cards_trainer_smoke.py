from __future__ import annotations

import os
import re
import shutil
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

playwright_sync_api = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect, sync_playwright

repo_root = Path(__file__).resolve().parents[2]
import sys

package_src = repo_root / "packages" / "cubeanim" / "src"
for entry in (repo_root, package_src):
    token = str(entry)
    if token not in sys.path:
        sys.path.insert(0, token)

from tools.trainer.build_trainer_catalog import build_trainer_catalog


def _strict_mode() -> bool:
    return os.environ.get("SMOKE_STRICT", "0") == "1"


def _smoke_enabled() -> bool:
    return _strict_mode() or os.environ.get("RUN_UI_SMOKE", "0") == "1"


def _ensure_smoke_enabled() -> None:
    if _smoke_enabled():
        return
    pytest.skip("UI smoke is opt-in. Use SMOKE_STRICT=1 or RUN_UI_SMOKE=1 to run it.")


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
def test_cards_trainer_smoke_static_no_api(tmp_path: Path) -> None:
    _ensure_smoke_enabled()

    trainer_src = repo_root / "apps" / "trainer"
    trainer_out = tmp_path / "trainer"
    shutil.copytree(trainer_src, trainer_out, dirs_exist_ok=True)

    build_trainer_catalog(
        repo_root=repo_root,
        db_path=tmp_path / "cards.db",
        output_dir=trainer_out,
        assets_dir=trainer_out / "assets",
        base_catalog_url="./assets",
    )

    api_requests: list[str] = []
    page_errors: list[str] = []

    with _StaticServer(trainer_out) as base_url:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 980})
            page = context.new_page()

            page.on("request", lambda req: api_requests.append(req.url))
            page.on("pageerror", lambda err: page_errors.append(str(err)))

            try:
                page.goto(f"{base_url}/index.html", wait_until="domcontentloaded", timeout=20000)
                expect(page.locator("[data-testid^='case-card-']").first).to_be_visible(timeout=20000)

                for tab in ("tab-f2l", "tab-oll", "tab-pll"):
                    page.get_by_test_id(tab).click()
                    expect(page.locator("[data-testid^='case-card-']").first).to_be_visible(timeout=10000)

                page.locator("[data-testid^='case-card-']").first.click()

                page.get_by_test_id("status-done").click()
                expect(page.get_by_test_id("status-done")).to_have_class(re.compile(r".*active.*"), timeout=10000)

                page.locator("#sandbox-play-pause-btn").click()
                page.wait_for_timeout(250)

                slider = page.locator("#sandbox-timeline-slider")
                slider.evaluate(
                    "el => { "
                    "el.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true })); "
                    "el.value = String(Math.min(1, Math.max(0.25, (Number(el.max) || 0) * 0.5))); "
                    "el.dispatchEvent(new Event('input', { bubbles: true })); "
                    "el.dispatchEvent(new Event('change', { bubbles: true })); "
                    "}"
                )
                page.wait_for_timeout(250)
                play_btn = page.locator("#sandbox-play-pause-btn")
                play_btn.click()
                page.wait_for_timeout(120)
                if (play_btn.inner_text() or "").strip() != "▶":
                    play_btn.click()
                expect(play_btn).to_have_text("▶", timeout=10000)

                expect(slider).to_be_enabled(timeout=10000)
                slider.evaluate("el => { el.value = String(Math.min(1, Number(el.max) || 0)); el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }")

                custom_formula = "R U R' U'"
                page.get_by_test_id("custom-formula-input").fill(custom_formula)
                page.get_by_test_id("custom-formula-apply").click()
                expect(page.locator("#m-algo-list")).to_contain_text(custom_formula, timeout=10000)

                all_algo_radios = page.locator(".algo-option input.algo-radio")
                assert all_algo_radios.count() >= 2

                page.locator("#sandbox-play-pause-btn").click()
                page.wait_for_timeout(220)

                switch_target = all_algo_radios.nth(0)
                if switch_target.is_checked():
                    switch_target = all_algo_radios.nth(1)
                switch_target.click()

                expect(page.locator("#sandbox-play-pause-btn")).to_have_text("▶", timeout=10000)
                expect(page.locator("#sandbox-timeline-slider")).to_have_value("0", timeout=10000)

                custom_option = page.locator(".algo-option", has_text=custom_formula).first
                expect(custom_option).to_be_visible(timeout=10000)
                custom_option.locator("[data-testid^='delete-algo-']").click()
                expect(page.locator("#m-algo-list")).not_to_contain_text(custom_formula, timeout=10000)

                page.get_by_test_id("export-profile").click()
                expect(page.locator("#profile-modal")).not_to_have_class(re.compile(r".*hidden.*"), timeout=10000)
                expect(page.locator("#profile-data")).to_have_value(re.compile(r".+"), timeout=10000)
                export_payload = (page.locator("#profile-data").input_value() or "").strip()
                assert export_payload
                page.locator("#profile-close-btn").click()

                page.get_by_test_id("status-new").click()
                expect(page.get_by_test_id("status-new")).to_have_class(re.compile(r".*active.*"), timeout=10000)

                page.get_by_test_id("import-profile").click()
                page.locator("#profile-data").fill(export_payload)
                page.locator("#profile-apply-btn").click()
                expect(page.get_by_test_id("status-done")).to_have_class(re.compile(r".*active.*"), timeout=10000)

                page.reload(wait_until="domcontentloaded")
                expect(page.locator("[data-testid^='case-card-']").first).to_be_visible(timeout=10000)
                expect(page.get_by_test_id("status-done")).to_have_class(re.compile(r".*active.*"), timeout=10000)
            finally:
                context.close()
                browser.close()

    if page_errors:
        pytest.fail(f"Page runtime errors found: {page_errors}")

    forbidden_api = [url for url in api_requests if "/api/" in url]
    assert not forbidden_api, f"Trainer made API requests in static mode: {forbidden_api}"
