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
    def percent(self) -> float | None:
        return None if self.found == 0 else 100.0 * self.hit / self.found

    def serialize(self) -> dict:
        return {
            "covered": self.hit,
            "total": self.found,
            "percent": None if self.percent is None else round(self.percent, 2),
        }


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


def parse_lcov(path: Path, policy: dict) -> dict[str, dict[str, Counts]]:
    totals = {
        category: {metric: Counts() for metric in METRICS}
        for category in ("overall", *policy.get("categories", {}))
    }
    current: tuple[str, ...] = ()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("SF:"):
            source = repo_path(line[3:])
            if source is None or not included(source, policy):
                current = ()
            else:
                current = ("overall",) + tuple(
                    name
                    for name, category in policy.get("categories", {}).items()
                    if included(source, category)
                )
        elif current and line.startswith("DA:"):
            for category in current:
                totals[category]["lines"].found += 1
                totals[category]["lines"].hit += int(line[3:].split(",", 1)[1]) > 0
        elif current and line.startswith("FNDA:"):
            for category in current:
                totals[category]["functions"].found += 1
                totals[category]["functions"].hit += int(line[5:].split(",", 1)[0]) > 0
        elif current and line.startswith("BRDA:"):
            taken = line[5:].rsplit(",", 1)[1]
            for category in current:
                totals[category]["branches"].found += 1
                totals[category]["branches"].hit += taken not in ("-", "0")
        elif line == "end_of_record":
            current = ()
    return totals


def validate(policy: dict) -> None:
    if not policy.get("include"):
        raise ValueError("coverage policy needs at least one include pattern")
    for field in ("minimum", "target", "enforce"):
        value = policy.get(field, {})
        if set(value) != set(METRICS):
            raise ValueError(f"coverage {field} must specify lines, functions, and branches")
    for field in ("minimum", "target"):
        if any(
            not isinstance(policy[field][name], (int, float))
            or not 0 <= policy[field][name] <= 100
            for name in METRICS
        ):
            raise ValueError(f"coverage {field}s must be numbers between 0 and 100")
    if any(policy["target"][name] < policy["minimum"][name] for name in METRICS):
        raise ValueError("coverage targets must not be below minimums")
    if any(policy["enforce"][name] not in ("medium", "high") for name in METRICS):
        raise ValueError("coverage enforcement must be medium or high")
    for name, category in policy.get("categories", {}).items():
        if not category.get("include"):
            raise ValueError(f"coverage category {name!r} needs an include pattern")


def effective_policy(policy: dict, category: str, field: str) -> dict:
    return {**policy[field], **policy.get("categories", {}).get(category, {}).get(field, {})}


def summary(totals: dict[str, dict[str, Counts]], policy: dict) -> dict:
    categories = totals.keys()
    return {
        "schema": 2,
        "measurements": {
            category: {metric: totals[category][metric].serialize() for metric in METRICS}
            for category in categories
        },
        "minimums": {
            category: effective_policy(policy, category, "minimum") for category in categories
        },
        "targets": {
            category: effective_policy(policy, category, "target") for category in categories
        },
        "enforcement": {
            category: effective_policy(policy, category, "enforce") for category in categories
        },
        "reasons": {
            category: value["reason"]
            for category, value in policy.get("categories", {}).items()
            if "reason" in value
        },
    }


def render(totals: dict[str, dict[str, Counts]], policy: dict) -> tuple[str, bool]:
    rows = ["| Metric | Hit / found | Coverage | Minimum |", "| --- | ---: | ---: | ---: |"]
    passed = True
    for metric in METRICS:
        count = totals["overall"][metric]
        enforced = policy["target"][metric] if policy["enforce"][metric] == "high" else policy["minimum"][metric]
        passed = passed and count.percent is not None and count.percent >= enforced
        coverage = "n/a" if count.percent is None else f"{count.percent:.2f}%"
        rows.append(f"| {metric.title()} | {count.hit} / {count.found} | {coverage} | {enforced:.2f}% |")
    return "\n".join(rows) + "\n", passed


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("lcov", type=Path)
    parser.add_argument("policy", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--json-summary", type=Path)
    args = parser.parse_args(argv)
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    validate(policy)
    totals = parse_lcov(args.lcov, policy)
    report, passed = render(totals, policy)
    print(report, end="")
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as output:
            output.write("## Coverage\n\n" + report)
    if args.json_summary:
        args.json_summary.write_text(json.dumps(summary(totals, policy), indent=2) + "\n", encoding="utf-8")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
