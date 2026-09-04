#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) M. Boerger, the MBO Works authors
# SPDX-License-Identifier: Apache-2.0
"""Generate cross-linked per-run and retained-site coverage overviews."""

from __future__ import annotations

import argparse
import datetime
import html
import json
import re
from pathlib import Path

import coverage_policy

METRICS = ("lines", "branches", "functions")


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{html.escape(title)}</title>
    <style>
      body {{ font: 16px/1.5 system-ui, sans-serif; margin: 2rem auto; max-width: 96rem; padding: 0 1rem; }}
      a {{ color: #0969da; }}
      table {{ border-collapse: collapse; margin: 1rem 0 2rem; }}
      th, td {{ border: 1px solid #d0d7de; padding: .35rem .65rem; text-align: right; }}
      th:first-child, td:first-child, .reports th:nth-child(-n+5), .reports td:nth-child(-n+5) {{ text-align: left; }}
      td {{ font-variant-numeric: tabular-nums; }}
      .low {{ background: #f8cecc; }}
      .medium {{ background: #fff2cc; }}
      .high {{ background: #d5e8d4; }}
    </style>
  </head>
  <body>
{body}
  </body>
</html>
"""


def _percent(value: dict) -> str:
    return "n/a" if value["percent"] is None else f'{value["percent"]:.2f}%'


def _rating(value: float | None, minimum: float, target: float) -> str:
    if value is None or value < minimum:
        return "low"
    return "high" if value >= target else "medium"


def render_report(summary: dict, target: str) -> str:
    """Render the overview landing page for one retained report."""
    rows = []
    for category, measurements in summary["measurements"].items():
        cells = [f"<td>{html.escape(category)}</td>"]
        for metric in METRICS:
            value = measurements[metric]
            rating = _rating(
                value["percent"],
                summary["minimums"][category][metric],
                summary["targets"][category][metric],
            )
            cells.extend(
                (
                    f'<td class="{rating}">{_percent(value)}</td>',
                    f'<td class="{rating}">{value["covered"]} / {value["total"]}</td>',
                )
            )
        rows.append("      <tr>" + "".join(cells) + "</tr>")
    overview = "../" * len(target.split("/"))
    body = f"    <h1>Carve coverage: {html.escape(target)}</h1>\n"
    body += """    <table>
      <thead><tr><th>Category</th><th>Lines</th><th>Covered</th><th>Branches</th><th>Covered</th><th>Functions</th><th>Covered</th></tr></thead>
      <tbody>
""" + "\n".join(rows) + """
      </tbody>
    </table>
"""
    body += (
        '    <p><a href="lcov/">Detailed source coverage</a> · '
        '<a href="coverage-summary.json">Summary JSON</a> · '
        '<a href="coverage-meta.json">Metadata JSON</a> · '
        f'<a href="{overview}">All coverage reports</a></p>'
    )
    return _page(f"Carve coverage: {target}", body)


def report_metadata(summary: dict, target: str, source: dict) -> dict:
    """Return retained identity and global-overview data for one report."""
    return {
        "schema": 1,
        "target": target,
        "source": source,
        "coverage": summary["measurements"]["overall"],
    }


def is_newer(candidate: dict, current: dict) -> bool:
    """Whether candidate may replace current, including an idempotent replay."""
    def key(value: dict) -> tuple[str, int, int]:
        source = value["source"]
        return source["created_at"], source["run_id"], source["run_attempt"]

    return key(candidate) >= key(current)


def _version_key(target: str) -> tuple[int, ...]:
    match = re.fullmatch(r"tag/(\d+)\.(\d+)\.(\d+)", target)
    return tuple(map(int, match.groups())) if match else (-1,)


def _report_row(metadata: dict) -> str:
    target = metadata["target"]
    if target == "main":
        label = "main"
        source = '<a href="https://github.com/mboworks/carve/tree/main">main branch</a>'
    elif target.startswith("tag/"):
        version = target.removeprefix("tag/")
        label = f"release {version}"
        source = f'<a href="https://github.com/mboworks/carve/releases/tag/{html.escape(version)}">release {html.escape(version)}</a>'
    else:
        number = target.removeprefix("pr/")
        label = f"PR {number}"
        source = f'<a href="https://github.com/mboworks/carve/pull/{html.escape(number)}">PR #{html.escape(number)}</a>'
    run = metadata["source"]
    completed = datetime.datetime.fromisoformat(run["completed_at"].replace("Z", "+00:00"))
    timestamp = completed.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    sha = html.escape(run["head_sha"])
    links = (
        f'<a href="{target}/">{html.escape(label)}</a>',
        source,
        timestamp,
        f'<a href="https://github.com/mboworks/carve/commit/{sha}"><code>{sha[:7]}</code></a>',
        f'<a href="https://github.com/mboworks/carve/actions/runs/{run["run_id"]}">run {run["run_id"]}</a>',
    )
    values = tuple(_percent(metadata["coverage"][metric]) for metric in METRICS)
    return "      <tr>" + "".join(f"<td>{value}</td>" for value in (*links, *values)) + "</tr>"


def render_site(root: Path) -> str:
    """Render the global overview for main, all releases, and all PRs."""
    paths = list((root / "main").glob("coverage-meta.json"))
    paths.extend((root / "tag").glob("*/coverage-meta.json"))
    paths.extend((root / "pr").glob("*/coverage-meta.json"))
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    reports.sort(
        key=lambda value: (
            0 if value["target"] == "main" else 1 if value["target"].startswith("tag/") else 2,
            tuple(-part for part in _version_key(value["target"]))
            if value["target"].startswith("tag/")
            else -int(value["target"].removeprefix("pr/"))
            if value["target"].startswith("pr/")
            else 0,
        )
    )
    body = "    <h1>Carve coverage reports</h1>\n"
    if reports:
        body += """    <table class="reports">
      <thead><tr><th>Report</th><th>Source</th><th>Completed</th><th>Commit</th><th>Workflow</th><th>Lines</th><th>Branches</th><th>Functions</th></tr></thead>
      <tbody>
""" + "\n".join(_report_row(report) for report in reports) + """
      </tbody>
    </table>
"""
    else:
        body += "    <p>No coverage reports are available.</p>\n"
    return _page("Carve coverage reports", body)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    report = commands.add_parser("report")
    report.add_argument("summary", type=Path)
    report.add_argument("target")
    report.add_argument("output", type=Path)
    site = commands.add_parser("site")
    site.add_argument("root", type=Path)
    site.add_argument("output", type=Path)
    metadata = commands.add_parser("metadata")
    metadata.add_argument("summary", type=Path)
    metadata.add_argument("target")
    metadata.add_argument("output", type=Path)
    for name in ("created-at", "started-at", "completed-at", "head-sha"):
        metadata.add_argument(f"--{name}", required=True)
    metadata.add_argument("--run-attempt", required=True, type=int)
    metadata.add_argument("--run-id", required=True, type=int)
    newer = commands.add_parser("newer")
    newer.add_argument("candidate", type=Path)
    newer.add_argument("current", type=Path)
    args = parser.parse_args()
    if args.command == "report":
        args.output.write_text(render_report(json.loads(args.summary.read_text()), args.target), encoding="utf-8")
    elif args.command == "site":
        args.output.write_text(render_site(args.root), encoding="utf-8")
    elif args.command == "metadata":
        summary = json.loads(args.summary.read_text())
        source = {name: getattr(args, name) for name in ("created_at", "started_at", "completed_at", "head_sha", "run_attempt", "run_id")}
        args.output.write_text(json.dumps(report_metadata(summary, args.target, source), indent=2) + "\n", encoding="utf-8")
    else:
        return 0 if is_newer(json.loads(args.candidate.read_text()), json.loads(args.current.read_text())) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
