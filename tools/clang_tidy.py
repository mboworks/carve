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


def run_one(executable: str, database: Path, source: str) -> tuple[str, int, str]:
    result = subprocess.run(
        [
            executable,
            "-p",
            str(database.parent),
            "--header-filter=^carve/",
            "--exclude-header-filter=(^|.*/)(bazel-out|external)/",
            source,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return source, result.returncode, result.stdout


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clang-tidy", required=True)
    parser.add_argument("--database", type=Path, default=Path("compile_commands.json"))
    parser.add_argument("--files-from", type=Path)
    parser.add_argument("--jobs", type=int, default=max(1, min(4, os.cpu_count() or 1)))
    args = parser.parse_args(argv)

    requested = None
    if args.files_from:
        requested = {line.strip() for line in args.files_from.read_text().splitlines() if line.strip()}
    database = json.loads(args.database.read_text(encoding="utf-8"))
    sources = selected_sources(database, requested, Path.cwd())
    print(f"clang-tidy: {len(sources)} translation unit(s), {args.jobs} worker(s)")
    failed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures = [executor.submit(run_one, args.clang_tidy, args.database, source) for source in sources]
        for future in futures:
            source, returncode, output = future.result()
            if output:
                print(f"== {source} ==\n{output}", end="" if output.endswith("\n") else "\n")
            if returncode:
                failed += 1
    print(f"clang-tidy: {len(sources) - failed} passed, {failed} failed")
    return int(failed != 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
