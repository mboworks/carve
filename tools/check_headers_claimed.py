#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) M. Boerger, the MBO Works authors
# SPDX-License-Identifier: Apache-2.0
"""Assert every tracked first-party header is claimed by its package BUILD file."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
    )
    return Path(result.stdout.strip())


def tracked_headers(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "carve/**/*.h", "carve/*.h"],
        capture_output=True,
        text=True,
        check=True,
        cwd=root,
    )
    return [line for line in result.stdout.splitlines() if line]


def owning_build_file(root: Path, header: str) -> Path | None:
    directory = (root / header).parent
    while True:
        build = directory / "BUILD.bazel"
        if build.is_file():
            return build
        if directory == root:
            return None
        directory = directory.parent


def check(headers: list[str], root: Path) -> list[str]:
    errors = []
    for header in sorted(headers):
        build = owning_build_file(root, header)
        if build is None:
            errors.append(f"{header}: no owning BUILD.bazel")
            continue
        relative = (root / header).relative_to(build.parent).as_posix()
        if f'"{relative}"' not in build.read_text(encoding="utf-8"):
            errors.append(f"{header}: not listed in {build.relative_to(root)}")
    return errors


def main(argv: list[str]) -> int:
    root = repo_root()
    headers = [arg for arg in argv if arg.startswith("carve/") and arg.endswith(".h")]
    errors = check(headers or tracked_headers(root), root)
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        print("every first-party header must be listed in its package BUILD target", file=sys.stderr)
    return int(bool(errors))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
