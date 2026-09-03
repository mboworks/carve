#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) M. Boerger, the MBO Works authors
# SPDX-License-Identifier: Apache-2.0
"""Create overview-compatible metadata for one coverage report."""

import argparse
import json
from pathlib import Path


def report_metadata(summary: dict, target: str, source: dict) -> dict:
    return {
        "schema": 1,
        "target": target,
        "source": source,
        "coverage": summary["measurements"]["overall"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path)
    parser.add_argument("target")
    parser.add_argument("output", type=Path)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--completed-at", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--run-attempt", required=True, type=int)
    parser.add_argument("--run-id", required=True, type=int)
    args = parser.parse_args()
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    source = {
        "created_at": args.created_at,
        "started_at": args.started_at,
        "completed_at": args.completed_at,
        "run_id": args.run_id,
        "run_attempt": args.run_attempt,
        "head_sha": args.head_sha,
    }
    args.output.write_text(
        json.dumps(report_metadata(summary, args.target, source), indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
