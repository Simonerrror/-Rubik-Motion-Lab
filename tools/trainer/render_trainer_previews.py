from __future__ import annotations

import argparse
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright


REPO_ROOT = Path(__file__).resolve().parents[2]
TRAINER_ROOT = REPO_ROOT / "apps" / "trainer"
DEFAULT_OUTPUT_DIR = TRAINER_ROOT / "assets" / "previews"
GROUPS = ("F2L", "OLL", "PLL")


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


def render_previews(*, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    with _StaticServer(TRAINER_ROOT) as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1100, "height": 680, "deviceScaleFactor": 1})
        try:
            for group in GROUPS:
                page.goto(
                    f"{base_url}/preview-renderer.html?group={group}",
                    wait_until="domcontentloaded",
                    timeout=20000,
                )
                page.wait_for_selector("body[data-ready='true']", timeout=20000)
                target = output_dir / f"trainer-preview-{group.lower()}.png"
                page.locator("#preview-capture").screenshot(path=str(target))
                written.append(target)
        finally:
            browser.close()

    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render baked trainer preview cubes")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for rendered preview PNG files",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    written = render_previews(output_dir=args.output_dir)
    for path in written:
        print(path)


if __name__ == "__main__":
    main()
