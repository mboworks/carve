#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) M. Boerger, the MBO Works authors
# SPDX-License-Identifier: Apache-2.0
"""Convert an LCOV trace file into complete, machine-readable JSON."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def _integer(value: str) -> int | None:
    return None if value == "-" else int(value)


def parse_lcov(contents: str) -> dict:
    """Parse LCOV lines, functions, and branches without discarding detail."""
    files = []
    current = None
    function_lines = {}
    function_counts = {}
    for raw_line in contents.splitlines():
        record, separator, value = raw_line.partition(":")
        if not separator:
            if raw_line == "end_of_record" and current is not None:
                current["functions"] = [
                    {
                        "name": name,
                        "start_line": function_lines[name][0],
                        **({"end_line": function_lines[name][1]} if function_lines[name][1] is not None else {}),
                        "execution_count": function_counts.get(name, 0),
                    }
                    for name in function_lines
                ]
                files.append(current)
                current = None
                function_lines = {}
                function_counts = {}
            continue
        if record == "SF":
            current = {"path": value, "lines": [], "functions": [], "branches": []}
        elif current is None:
            continue
        elif record == "FN":
            match = re.fullmatch(r"(\d+)(?:,(\d+))?,(.*)", value)
            if match is None:
                raise ValueError(f"Invalid FN record: {value}")
            start, end, name = match.groups()
            function_lines[name] = (int(start), int(end) if end is not None else None)
        elif record == "FNDA":
            count, name = value.split(",", 1)
            function_counts[name] = int(count)
        elif record == "DA":
            fields = value.split(",")
            line = {"line": int(fields[0]), "execution_count": int(fields[1])}
            if len(fields) == 3:
                line["checksum"] = fields[2]
            current["lines"].append(line)
        elif record == "BRDA":
            line, block, branch, taken = value.split(",", 3)
            current["branches"].append(
                {"line": int(line), "block": block, "branch": branch, "taken": _integer(taken)}
            )
    if current is not None:
        raise ValueError("LCOV record is missing end_of_record")
    totals = {
        "lines": {
            "found": sum(len(file["lines"]) for file in files),
            "hit": sum(line["execution_count"] > 0 for file in files for line in file["lines"]),
        },
        "functions": {
            "found": sum(len(file["functions"]) for file in files),
            "hit": sum(function["execution_count"] > 0 for file in files for function in file["functions"]),
        },
        "branches": {
            "found": sum(len(file["branches"]) for file in files),
            "hit": sum((branch["taken"] or 0) > 0 for file in files for branch in file["branches"]),
        },
    }
    return {"schema": 1, "totals": totals, "files": files}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = parse_lcov(args.input.read_text(encoding="utf-8"))
    args.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
