#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) M. Boerger, the MBO Works authors
# SPDX-License-Identifier: Apache-2.0
"""Apply source-owned exclusion directives to an LLVM LCOV trace."""

from __future__ import annotations

import argparse
from collections import defaultdict
import re
from pathlib import Path


def _excluded_blocks(source_lines: list[str]) -> set[int]:
    """Return lines inside explicit LCOV exclusion blocks, including markers."""
    excluded = set()
    start = None
    for number, line in enumerate(source_lines, start=1):
        if "LCOV_EXCL_START" in line:
            if start is not None:
                raise ValueError(f"nested LCOV_EXCL_START at line {number}")
            start = number
        if start is not None:
            excluded.add(number)
        if "LCOV_EXCL_STOP" in line:
            if start is None:
                raise ValueError(f"LCOV_EXCL_STOP without LCOV_EXCL_START at line {number}")
            start = None
    if start is not None:
        raise ValueError(f"LCOV_EXCL_START at line {start} has no LCOV_EXCL_STOP")
    return excluded


def _excluded_functions(source_lines: list[str]) -> set[int]:
    excluded = set()
    for index, line in enumerate(source_lines):
        if "LCOV_EXCL_FUNC_LINE" not in line:
            continue
        for continuation in range(index, len(source_lines)):
            excluded.add(continuation + 1)
            if "{" in source_lines[continuation]:
                break
    return excluded


def normalize_record(record: str, source: Path) -> str:
    """Apply source coverage directives to one raw LCOV record."""
    source_lines = source.read_text(encoding="utf-8").splitlines()
    excluded_lines = _excluded_blocks(source_lines) | {
        number
        for number, line in enumerate(source_lines, start=1)
        if "LCOV_EXCL_LINE" in line
    }
    excluded_branches = excluded_lines | {
        number
        for number, line in enumerate(source_lines, start=1)
        if "LCOV_EXCL_BR_LINE" in line
    }
    excluded_functions = _excluded_functions(source_lines)

    raw_lines = record.splitlines()
    headers = [
        line
        for line in raw_lines
        if not re.match(r"^(?:FN|FNDA|FNF|FNH|DA|LF|LH|BRDA|BRF|BRH):", line)
    ]
    definitions = []
    hits_by_name = defaultdict(int)
    data_lines = []
    branches = []
    for line in raw_lines:
        if line.startswith("FN:"):
            definition = line[3:].split(",")
            definitions.append((int(definition[0]), definition[-1], line))
        elif line.startswith("FNDA:"):
            hits, name = line[5:].split(",", 1)
            hits_by_name[name] += int(hits)
        elif line.startswith("DA:"):
            number = int(line[3:].split(",", 1)[0])
            if number not in excluded_lines:
                data_lines.append(line)
        elif line.startswith("BRDA:"):
            number = int(line[5:].split(",", 1)[0])
            if number not in excluded_branches:
                branches.append(line)

    functions = [
        (name, definition)
        for number, name, definition in definitions
        if number not in excluded_functions
    ]
    result = headers
    result.extend(definition for _, definition in functions)
    result.extend(f"FNDA:{hits_by_name[name]},{name}" for name, _ in functions)
    result.extend(
        (
            f"FNF:{len(functions)}",
            f"FNH:{sum(hits_by_name[name] > 0 for name, _ in functions)}",
        )
    )
    result.extend(branches)
    result.extend(
        (
            f"BRF:{len(branches)}",
            f"BRH:{sum(line.rsplit(',', 1)[1] not in ('-', '0') for line in branches)}",
        )
    )
    result.extend(data_lines)
    result.extend(
        (
            f"LF:{len(data_lines)}",
            f"LH:{sum(int(line.split(',', 2)[1]) > 0 for line in data_lines)}",
        )
    )
    return "\n".join(result) + "\n"


def normalized(report: str, workspace: Path = Path.cwd()) -> str:
    """Return an LCOV report with source coverage directives applied."""
    result = []
    for record in report.split("end_of_record\n"):
        match = re.search(r"(?m)^SF:(.+)$", record)
        if not match:
            continue
        physical = Path(match.group(1))
        source = physical if physical.is_absolute() else workspace / physical
        result.append(
            (normalize_record(record, source) if source.is_file() else record)
            + "end_of_record\n"
        )
    return "".join(result)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(
        normalized(args.input.read_text(encoding="utf-8")), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
