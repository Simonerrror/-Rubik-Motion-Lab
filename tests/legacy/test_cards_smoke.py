from __future__ import annotations

import os
import re
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest

playwright_sync_api = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import expect, sync_playwright

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output" / "playwright"
FORBIDDEN_CONSOLE_PATTERNS = (
    "cdn.tailwindcss.com",
    "favicon.ico",
    "err_connection_refused",
    "failed to fetch",
)


def _base_url() -> str:
    return os.environ.get("CARDS_BASE_URL", "http://127.0.0.1:8008").rstrip("/")


def _strict_mode() -> bool:
    return os.environ.get("SMOKE_STRICT", "0") == "1"


def _smoke_enabled() -> bool:
    return _strict_mode() or os.environ.get("RUN_UI_SMOKE", "0") == "1"


def _ensure_smoke_enabled() -> None:
    if _smoke_enabled():
        return
    pytest.skip("UI smoke is opt-in. Use SMOKE_STRICT=1 or RUN_UI_SMOKE=1 to run it.")


def _is_http_available(url: str) -> bool:
    try:
        with urlopen(url, timeout=2.0) as response:  # nosec B310
            return 200 <= int(response.status) < 500
    except URLError:
        return False


def _ensure_api_or_skip(base_url: str) -> None:
    api_url = f"{base_url}/health"
    if _is_http_available(api_url):
        return
    message = f"Cards API is not reachable at {api_url}. Start cards_api (and worker for full render path) first."
    if _strict_mode():
        pytest.fail(message)
    pytest.skip(message)


def _wait_for_enabled(locator, page, timeout_ms: int) -> None:
    deadline = time.time() + (timeout_ms / 1000.0)
    while time.time() < deadline:
        if locator.is_enabled():
            return
        page.wait_for_timeout(500)
    pytest.fail("Button did not become enabled within timeout")


def _select_case_for_draft(page) -> None:
    draft_btn = page.get_by_test_id("btn-render-draft")
    hd_btn = page.get_by_test_id("btn-render-hd")
    case_cards = page.locator("[data-testid^='case-card-']")
    scan_count = min(case_cards.count(), 24)
    for idx in range(scan_count):
        case_cards.nth(idx).click()
        page.wait_for_timeout(250)
        hd_text = (hd_btn.text_content() or "").strip()
        if draft_btn.is_enabled() and hd_text != "HD Ready":
            return
    pytest.fail("No case suitable for draft->HD flow was found in the current tab")


def _wait_for_any_hd_enabled_case(page, timeout_ms: int) -> None:
    hd_btn = page.get_by_test_id("btn-render-hd")
    deadline = time.time() + (timeout_ms / 1000.0)
    while time.time() < deadline:
        case_cards = page.locator("[data-testid^='case-card-']")
        scan_count = min(case_cards.count(), 24)
        for idx in range(scan_count):
            case_cards.nth(idx).click()
            page.wait_for_timeout(250)
            if hd_btn.is_enabled():
                return
        page.wait_for_timeout(750)
    pytest.fail("No case with enabled HD button was found within timeout")


@pytest.mark.e2e

def test_cards_smoke_flow() -> None:
    _ensure_smoke_enabled()
    base_url = _base_url()
    _ensure_api_or_skip(base_url)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    console_messages: list[dict[str, str]] = []
    page_errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 1000})
        page = context.new_page()

        page.on(
            "console",
            lambda msg: console_messages.append(
                {
                    "type": msg.type,
                    "text": msg.text,
                }
            ),
        )
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        try:
            page.goto(base_url, wait_until="domcontentloaded", timeout=15000)
            expect(page.locator("[data-testid^='case-card-']").first).to_be_visible(timeout=15000)
            page.screenshot(path=str(OUTPUT_DIR / "smoke-01-home.png"), full_page=True)

            for testid, shot in (
                ("tab-oll", "smoke-02-oll.png"),
                ("tab-f2l", "smoke-03-f2l.png"),
                ("tab-pll", "smoke-04-pll.png"),
            ):
                page.get_by_test_id(testid).click()
                expect(page.locator("[data-testid^='case-card-']").first).to_be_visible(timeout=10000)
                page.wait_for_timeout(300)
                page.screenshot(path=str(OUTPUT_DIR / shot), full_page=True)

            first_case = page.locator("[data-testid^='case-card-']").first
            first_case.click()

            page.get_by_test_id("status-work").click()
            expect(page.get_by_test_id("status-work")).to_have_class(re.compile(r".*active.*"), timeout=10000)
            page.get_by_test_id("status-done").click()
            expect(page.get_by_test_id("status-done")).to_have_class(re.compile(r".*active.*"), timeout=10000)
            page.get_by_test_id("status-new").click()
            expect(page.get_by_test_id("status-new")).to_have_class(re.compile(r".*active.*"), timeout=10000)

            page.get_by_test_id("tab-oll").click()
            expect(page.locator("[data-testid^='case-card-']").first).to_be_visible(timeout=10000)

            oll_26_cards = page.locator("[data-testid^='case-card-']").filter(has_text="OLL #26")
            if oll_26_cards.count() > 0:
                oll_26_cards.first.click()
            else:
                page.locator("[data-testid^='case-card-']").first.click()

            custom_formula = "R U R' U R U2 R' F R U R' U' F'"
            custom_input = page.get_by_test_id("custom-formula-input")
            custom_input.fill(custom_formula)
            page.get_by_test_id("custom-formula-apply").click()
            expect(page.locator("#m-algo-list")).to_contain_text(custom_formula, timeout=10000)
            page.screenshot(path=str(OUTPUT_DIR / "smoke-05-custom-added.png"), full_page=True)

            page.locator("[data-testid^='algo-radio-']").first.click()
            page.wait_for_timeout(500)

            custom_option = page.locator(".algo-option", has_text=custom_formula).first
            expect(custom_option).to_be_visible(timeout=10000)
            page.once("dialog", lambda dialog: dialog.accept())
            custom_option.locator("[data-testid^='delete-algo-']").click()
            expect(page.locator("#m-algo-list")).not_to_contain_text(custom_formula, timeout=10000)
            page.screenshot(path=str(OUTPUT_DIR / "smoke-06-custom-deleted.png"), full_page=True)

            _select_case_for_draft(page)
            draft_btn = page.get_by_test_id("btn-render-draft")
            expect(draft_btn).to_be_enabled(timeout=15000)
            draft_btn.click()

            hd_btn = page.get_by_test_id("btn-render-hd")
            _wait_for_any_hd_enabled_case(page, timeout_ms=180000)
            _wait_for_enabled(hd_btn, page, timeout_ms=10000)
            page.once("dialog", lambda dialog: dialog.accept())
            hd_btn.click()
            page.wait_for_timeout(500)
            page.screenshot(path=str(OUTPUT_DIR / "smoke-07-hd-requested.png"), full_page=True)
        finally:
            context.close()
            browser.close()

    if page_errors:
        pytest.fail(f"Page runtime errors found: {page_errors}")

    warning_or_error = [
        f"[{entry['type']}] {entry['text']}"
        for entry in console_messages
        if entry["type"] in {"warning", "error"}
    ]
    if warning_or_error:
        pytest.fail(f"Unexpected console warnings/errors: {warning_or_error}")

    forbidden_messages = [
        f"[{entry['type']}] {entry['text']}"
        for entry in console_messages
        if any(pattern in entry["text"].lower() for pattern in FORBIDDEN_CONSOLE_PATTERNS)
    ]
    if forbidden_messages:
        pytest.fail(f"Forbidden console patterns found: {forbidden_messages}")


@pytest.mark.e2e
def test_favicon_http_not_404() -> None:
    _ensure_smoke_enabled()
    base_url = _base_url()
    _ensure_api_or_skip(base_url)

    favicon_url = f"{base_url}/favicon.ico"
    with urlopen(favicon_url, timeout=5.0) as response:  # nosec B310
        status = int(response.status)
    assert 200 <= status < 400
