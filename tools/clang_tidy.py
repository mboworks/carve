#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) M. Boerger, the MBO Works authors
# SPDX-License-Identifier: Apache-2.0
"""Run the pinned clang-tidy over selected first-party translation units."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import signal
import threading
import time
from typing import Optional, Sequence
from pathlib import Path


def selected_sources(database: list[dict], requested: set[str] | None, root: Path) -> list[str]:
    """Return unique first-party .cc files present in the compilation database."""
    selected = set()
    for entry in database:
        raw = Path(entry["file"])
        path = raw if raw.is_absolute() else Path(entry.get("directory", root)) / raw
        try:
            relative = path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
        if not relative.startswith("carve/") or not relative.endswith(".cc"):
            continue
        if requested is None or relative in requested:
            selected.add(relative)
    return sorted(selected)


class ProcessRegistry:
    """Tracks active children so interruption terminates the complete pool."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._processes: set[subprocess.Popen[str]] = set()
        self._stopping = False

    def start(self, command: Sequence[str]) -> Optional[subprocess.Popen[str]]:
        # Starting and registration are atomic with respect to shutdown: queued
        # tasks cannot launch a child after the stop signal has been observed.
        with self._lock:
            if self._stopping:
                return None
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            self._processes.add(process)
            return process

    def remove(self, process: subprocess.Popen[str]) -> None:
        with self._lock:
            self._processes.discard(process)

    def terminate_all(self) -> None:
        with self._lock:
            self._stopping = True
            processes = list(self._processes)
        for process in processes:
            if process.poll() is None:
                process.terminate()
        deadline = time.monotonic() + 2.0
        for process in processes:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                pass
        for process in processes:
            if process.poll() is None:
                process.kill()


def run_one(executable: str, database: Path, source: str,
            registry: ProcessRegistry) -> tuple[str, int, str]:
    process = registry.start([
        executable, "-p", str(database.parent), "--header-filter=^carve/",
        "--exclude-header-filter=(^|.*/)(bazel-out|external)/", source,
    ])
    if process is None:
        return source, 130, ""
    try:
        output, _ = process.communicate()
        return source, process.returncode, output
    finally:
        registry.remove(process)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clang-tidy", required=True)
    parser.add_argument("--database", type=Path, default=Path("compile_commands.json"))
    parser.add_argument("--files-from", type=Path)
    parser.add_argument("--jobs", type=int, default=max(1, min(2, (os.cpu_count() or 1) - 1)))
    args = parser.parse_args(argv)

    if args.jobs < 1:
        parser.error("--jobs must be at least 1")

    requested = None
    if args.files_from:
        requested = {line.strip() for line in args.files_from.read_text().splitlines() if line.strip()}
    database = json.loads(args.database.read_text(encoding="utf-8"))
    sources = selected_sources(database, requested, Path.cwd())
    workers = min(args.jobs, len(sources))
    print(f"clang-tidy: {len(sources)} translation unit(s), {workers} worker(s)", flush=True)
    if not sources:
        return 0
    failed = 0
    registry = ProcessRegistry()

    def interrupt(_signum, _frame):
        raise KeyboardInterrupt

    old_sigterm = signal.signal(signal.SIGTERM, interrupt)
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(run_one, args.clang_tidy, args.database, source, registry)
                       for source in sources]
            try:
                for completed, future in enumerate(concurrent.futures.as_completed(futures), 1):
                    source, returncode, output = future.result()
                    print(f"[{completed}/{len(sources)}] {'FAIL' if returncode else 'PASS'} {source}", flush=True)
                    if output:
                        print(output, end="" if output.endswith("\n") else "\n", flush=True)
                    if returncode:
                        failed += 1
            except BaseException as error:
                registry.terminate_all()
                for future in futures:
                    future.cancel()
                if not isinstance(error, KeyboardInterrupt):
                    raise
                print("clang-tidy: interrupted; worker pool terminated", flush=True)
                return 130
    finally:
        signal.signal(signal.SIGTERM, old_sigterm)
    print(f"clang-tidy: {len(sources) - failed} passed, {failed} failed")
    return int(failed != 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
