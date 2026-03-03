#!/usr/bin/env python3
from __future__ import annotations

import argparse
import multiprocessing as mp
import os
import signal
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_SRC = REPO_ROOT / "packages" / "cubeanim" / "src"
for entry in (REPO_ROOT, PACKAGE_SRC):
    token = str(entry)
    if token not in sys.path:
        sys.path.insert(0, token)

from cubeanim.cards.services import CardsService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render queue worker for cards web UI")
    parser.add_argument("--interval", type=float, default=1.0, help="Polling interval in seconds")
    parser.add_argument("--once", action="store_true", help="Process one pending job and exit")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes")
    parser.add_argument(
        "--manim-threads",
        type=int,
        default=1,
        help="Thread budget passed to render subprocess via environment",
    )
    return parser.parse_args()


def run_worker(service: CardsService, interval: float, once: bool, manim_threads: int, worker_label: str) -> int:
    while True:
        job = service.process_next_job(manim_threads=manim_threads)
        if job is not None:
            print(f"[{worker_label}] Processed job #{job['id']} -> {job['status']}")
            if once:
                return 0
            continue

        if once:
            print(f"[{worker_label}] No pending jobs")
            return 0

        time.sleep(interval)


def _worker_main(repo_root: str, interval: float, once: bool, manim_threads: int, worker_index: int) -> int:
    service = CardsService.create(repo_root=Path(repo_root))
    label = f"worker-{worker_index}"
    return run_worker(
        service=service,
        interval=max(interval, 0.1),
        once=once,
        manim_threads=max(manim_threads, 1),
        worker_label=label,
    )


def _spawn_worker(ctx: mp.context.BaseContext, repo_root: Path, interval: float, manim_threads: int, index: int) -> mp.Process:
    process = ctx.Process(
        target=_worker_entry,
        args=(str(repo_root), interval, manim_threads, index),
        daemon=False,
    )
    process.start()
    return process


def _worker_entry(repo_root: str, interval: float, manim_threads: int, index: int) -> None:
    code = _worker_main(repo_root, interval=interval, once=False, manim_threads=manim_threads, worker_index=index)
    raise SystemExit(code)


def _worker_once_entry(repo_root: str, interval: float, manim_threads: int, index: int) -> None:
    code = _worker_main(repo_root, interval=interval, once=True, manim_threads=manim_threads, worker_index=index)
    raise SystemExit(code)


def _terminate_all(processes: list[mp.Process]) -> None:
    for process in processes:
        if process.is_alive():
            process.terminate()
    for process in processes:
        process.join(timeout=2.0)


def _install_sigterm_handler() -> None:
    def _handle_sigterm(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _handle_sigterm)


def main() -> int:
    args = parse_args()
    workers = max(1, int(args.workers))
    interval = max(args.interval, 0.1)
    manim_threads = max(int(args.manim_threads), 1)

    _install_sigterm_handler()

    if args.once:
        if workers == 1:
            service = CardsService.create(repo_root=REPO_ROOT)
            return run_worker(
                service=service,
                interval=interval,
                once=True,
                manim_threads=manim_threads,
                worker_label="worker-1",
            )

        ctx = mp.get_context("spawn")
        processes = [
            ctx.Process(
                target=_worker_once_entry,
                args=(str(REPO_ROOT), interval, manim_threads, index),
                daemon=False,
            )
            for index in range(1, workers + 1)
        ]
        for process in processes:
            process.start()
        exit_code = 0
        for process in processes:
            process.join()
            if process.exitcode not in (0, None):
                exit_code = 1
        return exit_code

    ctx = mp.get_context("spawn")
    processes = [_spawn_worker(ctx, REPO_ROOT, interval, manim_threads, i) for i in range(1, workers + 1)]

    try:
        while True:
            for process in processes:
                if process.exitcode is not None:
                    print(f"Worker process {process.pid} exited with code {process.exitcode}")
                    _terminate_all(processes)
                    return 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Stopping workers...")
        _terminate_all(processes)
        return 0


if __name__ == "__main__":
    # Avoid inheriting stale launcher paths when called from non-standard shells.
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    raise SystemExit(main())
