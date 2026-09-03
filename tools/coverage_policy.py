#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) M. Boerger, the MBO Works authors
# SPDX-License-Identifier: Apache-2.0
"""Apply Carve's checked-in coverage policy to a Bazel LCOV report."""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from dataclasses import dataclass
from pathlib import Path

METRICS = ("lines", "functions", "branches")


@dataclass
class Counts:
    found: int = 0
    hit: int = 0

    @property
    def percent(self) -> float:
        return 0.0 if self.found == 0 else 100.0 * self.hit / self.found


def repo_path(value: str) -> str | None:
    normalized = value.replace("\\", "/")
    if normalized.startswith("carve/"):
        return normalized
    marker = "/carve/"
    return "carve/" + normalized.rsplit(marker, 1)[1] if marker in normalized else None


def included(path: str, policy: dict) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in policy["include"]) and not any(
        fnmatch.fnmatch(path, pattern) for pattern in policy.get("exclude", [])
    )


def parse_lcov(path: Path, policy: dict) -> dict[str, Counts]:
    totals = {metric: Counts() for metric in METRICS}
    current = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("SF:"):
            source = repo_path(line[3:])
            current = source is not None and included(source, policy)
        elif current and line.startswith("DA:"):
            totals["lines"].found += 1
            totals["lines"].hit += int(line[3:].split(",", 1)[1]) > 0
        elif current and line.startswith("FNDA:"):
            totals["functions"].found += 1
            totals["functions"].hit += int(line[5:].split(",", 1)[0]) > 0
        elif current and line.startswith("BRDA:"):
            taken = line[5:].rsplit(",", 1)[1]
            totals["branches"].found += 1
            totals["branches"].hit += taken not in ("-", "0")
        elif line == "end_of_record":
            current = False
    return totals


def validate(policy: dict) -> None:
    if not policy.get("include"):
        raise ValueError("coverage policy needs at least one include pattern")
    minimum = policy.get("minimum", {})
    if set(minimum) != set(METRICS):
        raise ValueError("coverage minimum must specify lines, functions, and branches")
    if any(not isinstance(minimum[name], (int, float)) or not 0 <= minimum[name] <= 100 for name in METRICS):
        raise ValueError("coverage minimums must be numbers between 0 and 100")


def render(totals: dict[str, Counts], policy: dict) -> tuple[str, bool]:
    rows = ["| Metric | Hit / found | Coverage | Minimum |", "| --- | ---: | ---: | ---: |"]
    passed = True
    for metric in METRICS:
        count = totals[metric]
        minimum = float(policy["minimum"][metric])
        passed = passed and count.percent >= minimum
        rows.append(f"| {metric.title()} | {count.hit} / {count.found} | {count.percent:.2f}% | {minimum:.2f}% |")
    return "\n".join(rows) + "\n", passed


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("lcov", type=Path)
    parser.add_argument("policy", type=Path)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args(argv)
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    validate(policy)
    report, passed = render(parse_lcov(args.lcov, policy), policy)
    print(report, end="")
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as output:
            output.write("## Coverage\n\n" + report)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
