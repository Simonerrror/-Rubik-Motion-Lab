#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cubeanim.cards.services import CardsService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render queue worker for cards web UI")
    parser.add_argument("--interval", type=float, default=1.0, help="Polling interval in seconds")
    parser.add_argument("--once", action="store_true", help="Process one pending job and exit")
    return parser.parse_args()


def run_worker(service: CardsService, interval: float, once: bool) -> int:
    while True:
        job = service.process_next_job()
        if job is not None:
            print(f"Processed job #{job['id']} -> {job['status']}")
            if once:
                return 0
            continue

        if once:
            print("No pending jobs")
            return 0

        time.sleep(interval)


def main() -> int:
    args = parse_args()
    service = CardsService.create(repo_root=REPO_ROOT)
    return run_worker(service=service, interval=max(args.interval, 0.1), once=args.once)


if __name__ == "__main__":
    raise SystemExit(main())
