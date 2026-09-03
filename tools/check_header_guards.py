#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) M. Boerger, the MBO Works authors
# SPDX-License-Identifier: Apache-2.0
"""Check header guards against STYLE_CPP.md's `{PATH}_{FILE}_` rule."""

import re
import sys
from pathlib import Path


def expected_guard(path: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "_", path).upper() + "_"


def check(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    want = expected_guard(path.as_posix())
    match = re.search(r"^#ifndef\s+(\S+)", text, re.MULTILINE)
    if not match:
        return [f"{path}: no #ifndef header guard; expected {want}"]
    got = match.group(1)
    errors = []
    if got != want:
        errors.append(f"{path}: guard is {got}; expected {want}")
    if not re.search(rf"^#define\s+{re.escape(got)}\s*$", text, re.MULTILINE):
        errors.append(f"{path}: #ifndef {got} has no matching #define")
    closing = next((line for line in reversed(text.splitlines()) if line.startswith("#endif")), "")
    comment = re.match(r"#endif\s*//\s*(\S+)\s*$", closing)
    if not comment or comment.group(1) != got:
        errors.append(f"{path}: closing #endif must name {got}")
    return errors


def main(argv: list[str]) -> int:
    errors = [error for raw in argv if raw.endswith(".h") for error in check(Path(raw))]
    for error in errors:
        print(error, file=sys.stderr)
    return int(bool(errors))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
