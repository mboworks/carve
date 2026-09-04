#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) M. Boerger, the MBO Works authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for coverage overview generation."""

import json
import tempfile
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
                (destination / "coverage-meta.json").write_text(json.dumps(metadata(target)))

            rendered = coverage_index.render_site(root)

        self.assertIn("main branch", rendered)
        self.assertIn("release 0.10.0", rendered)
        self.assertIn("PR #81", rendered)
        self.assertLess(rendered.index('href="main/"'), rendered.index('href="tag/0.10.0/"'))
        self.assertLess(rendered.index('href="tag/0.10.0/"'), rendered.index('href="tag/0.9.0/"'))
        self.assertLess(rendered.index('href="tag/0.9.0/"'), rendered.index('href="pr/81/"'))
        self.assertLess(rendered.index('href="pr/81/"'), rendered.index('href="pr/9/"'))

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
