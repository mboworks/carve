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
      .reportTitle {{ text-align: center; }}
      .coverageTable {{ border-collapse: separate; border-spacing: 1px; margin-left: auto; margin-right: auto; }}
      .coverageTable th, .coverageTable td {{ border: 0; }}
      .coverageTable th {{ background: #6688d4; color: #fff; }}
      .coverageTable thead tr:first-child th {{ font-size: 120%; text-align: center; }}
      .coverageTable th:first-child, .coverageTable td:first-child,
      .reportsTable th:nth-child(-n+6), .reportsTable td:nth-child(-n+6) {{ text-align: left; }}
      .coverageTable td:first-child {{ background: #dae7fe; color: #284fa8; }}
      .coverageTable td {{ white-space: nowrap; }}
      .coverageTable td:nth-child(n+3), .reportsTable td:nth-child(n+7) {{ font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-variant-numeric: tabular-nums; }}
      .low {{ background: #f8cecc; }}
      .medium {{ background: #fff2cc; }}
      .high {{ background: #d5e8d4; }}
      .coverageTable .policyGap {{ background: #fff; min-width: .5rem; padding: 0; }}
      .coverageTable .policyCell {{ background: #dae7fe; font: 11px/1.25 ui-monospace, SFMono-Regular, Consolas, monospace; text-align: center; }}
      .coverageTable .policy-stricter {{ background: #a7fc9d; }}
      .coverageTable .policy-weaker {{ background: #ffea20; }}
      .coverageTable .policy-mixed {{ background: #ffd580; }}
      .policyNote {{ font-size: 12px; margin: -1.5rem auto 2rem; max-width: 72rem; text-align: left; }}
      .status-good {{ background: #d5e8d4; }}
      .status-ok {{ background: #fff2cc; }}
      .status-bad {{ background: #f8cecc; color: #cf222e; font-weight: bold; }}
    </style>
  </head>
  <body>
{body}
  </body>
</html>
"""


def _percent(value: dict) -> str:
    return "n/a" if value["percent"] is None else f'{value["percent"]:.2f}%'


def _policy(summary: dict, category: str) -> dict[str, coverage_policy.MetricPolicy]:
    return {
        metric: coverage_policy.MetricPolicy(
            summary["minimums"][category][metric],
            summary["targets"][category][metric],
            summary["enforcement"][category][metric],
        )
        for metric in METRICS
    }


def _status(metrics: dict, policy: dict[str, coverage_policy.MetricPolicy]) -> str:
    failures = [
        name
        for name in METRICS
        if not coverage_policy.passes(metrics[name]["percent"], policy[name])
    ]
    if failures:
        return "BAD: " + "/".join(name[0].upper() for name in failures)
    if all(
        coverage_policy.rating(metrics[name]["percent"], policy[name]) == "high"
        for name in METRICS
    ):
        return "GOOD"
    return "OK"


def _status_class(status: str) -> str:
    return {"GOOD": "status-good", "OK": "status-ok"}.get(status, "status-bad")


def _compact_policy(policy: coverage_policy.MetricPolicy) -> str:
    limits = (
        f"{policy.minimum:g}"
        if policy.minimum == policy.target
        else f"{policy.minimum:g}/{policy.target:g}"
    )
    return f"{limits}&middot;{policy.enforce[0].upper()}"


def _policy_direction(
    value: coverage_policy.MetricPolicy, inherited: coverage_policy.MetricPolicy
) -> str:
    enforcement = {"medium": 0, "high": 1}
    weaker = (
        value.minimum < inherited.minimum
        or value.target < inherited.target
        or enforcement[value.enforce] < enforcement[inherited.enforce]
    )
    stricter = (
        value.minimum > inherited.minimum
        or value.target > inherited.target
        or enforcement[value.enforce] > enforcement[inherited.enforce]
    )
    if weaker and stricter:
        return "policy-mixed"
    return "policy-weaker" if weaker else "policy-stricter"


def _full_table(summary: dict) -> str:
    rows = []
    overall = _policy(summary, "overall")
    reasons = summary.get("reasons", {})
    for category, metrics in summary["measurements"].items():
        policy = _policy(summary, category)
        status = _status(metrics, policy)
        reason = reasons.get(category, "")
        reason_attr = f' title="{html.escape(reason, quote=True)}"' if reason else ""
        row = f'      <tr><td{reason_attr}>{html.escape(category)}</td>'
        row += f'<td class="{_status_class(status)}">{html.escape(status)}</td>'
        for metric in METRICS:
            value = metrics[metric]
            metric_policy = policy[metric]
            rating = coverage_policy.rating(value["percent"], metric_policy)
            title = (
                f"{rating}; enforce {metric_policy.enforce}; medium at "
                f"{metric_policy.minimum:g}%; high at {metric_policy.target:g}%"
            )
            attrs = f'class="{rating}" title="{html.escape(title, quote=True)}"'
            for cell in (_percent(value), str(value["covered"]), str(value["total"])):
                row += f"<td {attrs}>{cell}</td>"
        row += '<td class="policyGap"></td>'
        for metric in METRICS:
            value = policy[metric]
            if category == "overall":
                label, css = _compact_policy(value), "policyCell"
            elif value == overall[metric]:
                label, css = "default", "policyCell"
            else:
                direction = _policy_direction(value, overall[metric])
                word = {
                    "policy-weaker": "lower",
                    "policy-stricter": "higher",
                    "policy-mixed": "mixed",
                }[direction]
                label, css = f"{word}<br>{_compact_policy(value)}", f"policyCell {direction}"
            row += f'<td class="{css}">{label}</td>'
        rows.append(row + "</tr>")
    return """    <table class="coverageTable">
      <thead>
        <tr><th rowspan="2">Category</th><th rowspan="2">Status</th><th colspan="3">Lines</th><th colspan="3">Branches</th><th colspan="3">Functions</th><th class="policyGap" rowspan="2"></th><th colspan="3">Policy vs default<sup>*</sup></th></tr>
        <tr><th>Rate</th><th>Covered</th><th>Total</th><th>Rate</th><th>Covered</th><th>Total</th><th>Rate</th><th>Covered</th><th>Total</th><th>Lines</th><th>Branches</th><th>Functions</th></tr>
      </thead>
      <tbody>
""" + "\n".join(rows) + """
      </tbody>
    </table>
    <p class="policyNote"><sup>*</sup> Policy values are <code>medium/high&middot;enforced-band</code>.
    For example, <code>90/92&middot;M</code> means medium starts at 90%, high starts at 92%, and medium is
    enforced. Lower, higher, and mixed compare policy strictness, including the enforced band, not
    measured coverage.</p>"""


def render_report(summary: dict, target: str) -> str:
    """Render the overview landing page for one retained report."""
    overview = "../" * len(target.split("/"))
    body = f'    <h1 class="reportTitle">Carve coverage: {html.escape(target)}</h1>\n'
    body += _full_table(summary) + "\n"
    body += (
        '    <p><a href="lcov/">Detailed source coverage</a> · '
        '<a href="coverage-data.json">Complete coverage JSON</a> · '
        '<a href="coverage.lcov">LCOV trace</a> · '
        '<a href="coverage-summary.json">Aggregate summary JSON</a> · '
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
        f'<a href="{target}/coverage-data.json">JSON</a>',
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
        body += """    <table class="reportsTable">
      <thead><tr><th>Report</th><th>Data</th><th>Source</th><th>Completed</th><th>Commit</th><th>Workflow</th><th>Lines</th><th>Branches</th><th>Functions</th></tr></thead>
      <tbody>
""" + "\n".join(_report_row(report) for report in reports) + """
      </tbody>
    </table>
"""
    else:
        body += "    <p>No coverage reports are available.</p>\n"
    return _page("Carve coverage reports", body)


def regenerate(root: Path) -> int:
    """Regenerate every retained report index and the aggregate index."""
    summaries = list((root / "main").glob("coverage-summary.json"))
    summaries.extend((root / "tag").glob("*/coverage-summary.json"))
    summaries.extend((root / "pr").glob("*/coverage-summary.json"))
    for summary_path in summaries:
        target = summary_path.parent.relative_to(root).as_posix()
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        (summary_path.parent / "index.html").write_text(
            render_report(summary, target), encoding="utf-8"
        )
    (root / "index.html").write_text(render_site(root), encoding="utf-8")
    return len(summaries)


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
    regenerate_command = commands.add_parser("regenerate")
    regenerate_command.add_argument("root", type=Path)
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
        args.output.write_text(
            render_report(json.loads(args.summary.read_text()), args.target),
            encoding="utf-8",
        )
    elif args.command == "site":
        args.output.write_text(render_site(args.root), encoding="utf-8")
    elif args.command == "regenerate":
        regenerate(args.root)
    elif args.command == "metadata":
        summary = json.loads(args.summary.read_text())
        source = {
            name: getattr(args, name)
            for name in (
                "created_at",
                "started_at",
                "completed_at",
                "head_sha",
                "run_attempt",
                "run_id",
            )
        }
        args.output.write_text(
            json.dumps(report_metadata(summary, args.target, source), indent=2) + "\n",
            encoding="utf-8",
        )
    else:
        return (
            0
            if is_newer(
                json.loads(args.candidate.read_text()),
                json.loads(args.current.read_text()),
            )
            else 1
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
