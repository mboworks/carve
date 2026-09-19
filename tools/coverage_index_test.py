#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) M. Boerger, the MBO Works authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for coverage overview generation."""

import json
import tempfile
import subprocess
import sys
from unittest import mock
import unittest
from pathlib import Path

from tools import coverage_index


def summary(percent: float = 75.0) -> dict:
    metric = {"covered": 3, "total": 4, "percent": percent}
    policy = {name: 60 for name in coverage_index.METRICS}
    target = {name: 85 for name in coverage_index.METRICS}
    enforcement = {name: "medium" for name in coverage_index.METRICS}
    return {
        "measurements": {"overall": {name: metric for name in coverage_index.METRICS}},
        "minimums": {"overall": policy},
        "targets": {"overall": target},
        "enforcement": {"overall": enforcement},
    }


def metadata(target: str, percent: float = 75.0) -> dict:
    source = {
        "created_at": "2026-09-04T10:00:00Z",
        "started_at": "2026-09-04T10:01:00Z",
        "completed_at": "2026-09-04T10:02:00Z",
        "head_sha": "abcdef012345",
        "run_attempt": 1,
        "run_id": 42,
    }
    return coverage_index.report_metadata(summary(percent), target, source)


class CoverageIndexTest(unittest.TestCase):
    def test_archive_preserves_each_run_attempt_and_late_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "main"
            report.mkdir()
            for run, attempt in ((100, 1), (100, 2), (99, 1)):
                value = metadata("main")
                value["source"]["run_id"] = run
                value["source"]["run_attempt"] = attempt
                value["source"]["head_sha"] = f"head-{run}-{attempt}"
                value["source"]["created_at"] = f"2026-09-0{attempt}T00:00:00Z"
                (report / "coverage-meta.json").write_text(json.dumps(value))
                (report / "index.html").write_text(f"report-{run}-{attempt}")
                coverage_index.archive_reports(root)
            self.assertEqual((root / "runs/100/1/index.html").read_text(), "report-100-1")
            self.assertEqual((root / "runs/100/2/index.html").read_text(), "report-100-2")
            self.assertEqual((root / "runs/99/1/index.html").read_text(), "report-99-1")
            self.assertIn('href="100/2/"', (root / "runs/index.html").read_text())

    def test_closed_unmerged_reports_are_hidden_but_reopened_reports_return(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for target in ("main", "pr/10"):
                path = root / target
                path.mkdir(parents=True)
                value = metadata(target)
                value["pull_state"] = "closed" if target == "pr/10" else None
                value["reference_time"] = "2026-09-01T00:00:00Z"
                (path / "coverage-meta.json").write_text(json.dumps(value))
            rendered = coverage_index.render_site(root)
            self.assertIn('href="main/"', rendered)
            self.assertNotIn('href="pr/10/"', rendered)
            value = json.loads((root / "pr/10/coverage-meta.json").read_text())
            value["pull_state"] = "open"
            (root / "pr/10/coverage-meta.json").write_text(json.dumps(value))
            self.assertIn('href="pr/10/"', coverage_index.render_site(root))

    def test_report_has_category_overview_and_global_cross_link(self):
        rendered = coverage_index.render_report(summary(), "pr/81")
        self.assertIn("Carve coverage: pr/81", rendered)
        self.assertIn("75.00%", rendered)
        self.assertIn('<td class="status-ok">OK</td>', rendered)
        self.assertIn("Policy vs default<sup>*</sup>", rendered)
        self.assertIn("3</td>", rendered)
        self.assertIn("4</td>", rendered)
        self.assertIn('href="lcov/"', rendered)
        self.assertIn('href="coverage-data.json"', rendered)
        self.assertIn('href="coverage.lcov"', rendered)
        self.assertIn('href="coverage-summary.json"', rendered)
        self.assertIn('href="coverage-meta.json"', rendered)
        self.assertIn('href="../../"', rendered)

    def test_site_contains_main_all_releases_and_all_prs_in_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for target in ("main", "tag/0.9.0", "tag/0.10.0", "pr/9", "pr/81"):
                destination = root / target
                destination.mkdir(parents=True)
                value = metadata(target)
                positions = {"main": 0, "pr/9": 4, "tag/0.10.0": 3, "pr/81": 2, "tag/0.9.0": 1}
                value["history"] = {"position": positions[target], "commit": "abc"}
                (destination / "coverage-meta.json").write_text(json.dumps(value))

            rendered = coverage_index.render_site(root)

        self.assertIn("main branch", rendered)
        self.assertIn("release 0.10.0", rendered)
        self.assertIn("PR #81", rendered)
        # Legacy fixtures have no reference_time; all retained reports remain visible
        # while the new publisher refreshes timestamps on its next deployment.
        for target in ("main", "pr/9", "tag/0.10.0", "pr/81", "tag/0.9.0"):
            self.assertIn(f'href="{target}/"', rendered)

    def test_each_global_row_links_to_report_source_commit_and_run(self):
        rendered = coverage_index._report_row(metadata("pr/81"))
        self.assertIn('href="pr/81/"', rendered)
        self.assertIn('href="pr/81/coverage-data.json">JSON</a>', rendered)
        self.assertIn("/mboworks/carve/pull/81", rendered)
        self.assertIn("/mboworks/carve/commit/abcdef012345", rendered)
        self.assertIn("/mboworks/carve/actions/runs/42", rendered)

    def test_newer_source_run_replaces_older_report(self):
        old = metadata("main")
        new = {**old, "source": {**old["source"], "created_at": "2026-09-04T11:00:00Z"}}
        self.assertTrue(coverage_index.is_newer(new, old))
        self.assertFalse(coverage_index.is_newer(old, new))

    def test_history_uses_merge_and_peeled_tag_commits_and_refreshes_old_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = root / "source"
            repository.mkdir()
            def git(*args):
                return subprocess.check_output(
                    ["git", "-C", str(repository), "-c", "user.name=Coverage Test",
                     "-c", "user.email=coverage@example.invalid", "-c", "commit.gpgsign=false",
                     "-c", "tag.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args], text=True,
                    stderr=subprocess.DEVNULL,
                ).strip()
            git("init")
            git("commit", "--allow-empty", "-m", "older merge")
            older = git("rev-parse", "HEAD")
            git("tag", "0.9.0")
            git("commit", "--allow-empty", "-m", "release commit")
            release = git("rev-parse", "HEAD")
            git("tag", "-a", "0.10.0", "-m", "release")
            git("commit", "--allow-empty", "-m", "newer merge")
            newer = git("rev-parse", "HEAD")
            reports = root / "reports"
            for target in ("main", "pr/900", "pr/1", "pr/2", "tag/0.9.0", "tag/0.10.0", "tag/9.9.9"):
                folder = reports / target
                folder.mkdir(parents=True)
                metadata = coverage_index.report_metadata(summary(95), target, {
                    "created_at": "2026-08-22T10:00:00Z", "completed_at": "2026-08-22T10:01:00Z",
                    "started_at": "2026-08-22T10:00:00Z", "run_attempt": 1, "run_id": 1,
                    "head_sha": "tested-pr-head",
                })
                metadata["history"] = {"position": 999, "commit": "stale"}
                (folder / "coverage-meta.json").write_text(json.dumps(metadata))
            pulls = [
                {"number": 900, "merged_at": "2026-08-20T10:00:00Z", "merge_commit_sha": older},
                {"number": 1, "merged_at": "2026-08-21T10:00:00Z", "merge_commit_sha": newer},
                {"number": 2, "merged_at": None, "merge_commit_sha": older},
            ]
            pages = root / "pulls.json"
            pages.write_text(json.dumps([pulls[:1], pulls[1:]]))
            with mock.patch.object(sys, "argv", [
                "coverage_index.py", "history", str(reports), str(repository), str(pages)
            ]):
                self.assertEqual(coverage_index.main(), 0)
            expected = {"pr/900": (0, older), "tag/0.9.0": (0, older),
                        "tag/0.10.0": (1, release), "pr/1": (2, newer)}
            for target, (position, commit) in expected.items():
                metadata = json.loads((reports / target / "coverage-meta.json").read_text())
                self.assertEqual(metadata["history"], {"position": position, "commit": commit})
                self.assertEqual(metadata["source"]["head_sha"], "tested-pr-head")
            for target in ("main", "pr/2", "tag/9.9.9"):
                metadata = json.loads((reports / target / "coverage-meta.json").read_text())
                self.assertIsNone(metadata["history"])
            rendered = coverage_index.render_site(reports)
            for target in ("main", "pr/1", "tag/0.10.0", "tag/0.9.0", "pr/900"):
                self.assertIn(f'href="{target}/"', rendered)
            self.assertLess(rendered.index('href="main/"'), rendered.index('href="pr/2/"'))
            # A PR report can be published before the PR is merged. Refreshing must move it
            # into the main chronology without replacing its coverage or workflow identity.
            pulls[-1]["merged_at"] = "2026-08-22T10:00:00Z"
            coverage_index.update_history(reports, repository, pulls)
            refreshed = json.loads((reports / "pr/2/coverage-meta.json").read_text())
            self.assertEqual(refreshed["history"]["position"], 0)

    def test_unpositioned_reports_use_creation_time(self):
        old = metadata("pr/900")
        new = metadata("pr/1")
        new["source"]["created_at"] = "2026-09-05T10:00:00Z"
        old["source"]["completed_at"] = "2026-09-06T10:00:00Z"
        ordered = sorted([old, new], key=coverage_index._report_order, reverse=True)
        self.assertEqual([value["target"] for value in ordered], ["pr/1", "pr/900"])

    def test_regenerate_rebuilds_all_indexes_from_retained_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for target in ("main", "tag/0.1.0", "pr/83"):
                destination = root / target
                destination.mkdir(parents=True)
                (destination / "coverage-summary.json").write_text(json.dumps(summary()))
                (destination / "coverage-meta.json").write_text(
                    json.dumps(metadata(target))
                )
                (destination / "coverage-data.json").write_text('{"retained": true}\n')
                lcov = destination / "lcov"
                lcov.mkdir()
                (lcov / "index.html").write_text("detailed")
                (destination / "index.html").write_text("stale")

            count = coverage_index.regenerate(root)

            self.assertEqual(3, count)
            self.assertIn("Carve coverage reports", (root / "index.html").read_text())
            self.assertIn(
                "Policy vs default",
                (root / "pr/83/index.html").read_text(),
            )
            self.assertEqual(
                '{"retained": true}\n',
                (root / "pr/83/coverage-data.json").read_text(),
            )
            self.assertEqual("detailed", (root / "pr/83/lcov/index.html").read_text())


if __name__ == "__main__":
    unittest.main()
