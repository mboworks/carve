#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) M. Boerger, the MBO Works authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for the LCOV coverage policy gate."""

import tempfile
import unittest
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coverage_policy


def policy():
    return {
        "include": ["carve/**"],
        "minimum": {"lines": 60, "functions": 50, "branches": 40},
        "target": {"lines": 80, "functions": 75, "branches": 70},
        "enforce": {"lines": "medium", "functions": "medium", "branches": "medium"},
    }


class CoveragePolicyTest(unittest.TestCase):
    def test_checkout_directories_named_carve_are_removed(self):
        self.assertEqual(
            coverage_policy.repo_path("/home/runner/work/carve/carve/carve/foo.cc"),
            "carve/foo.cc",
        )

    def test_parses_first_party_records_and_excludes_tests(self):
        report = """SF:/src/carve/foo.cc
DA:1,1
DA:2,0
FN:1,Foo
FNDA:2,Foo
BRDA:1,0,0,1
BRDA:1,0,1,-
end_of_record
SF:/src/carve/foo_test.cc
DA:1,0
end_of_record
"""
        config = {
            **policy(),
            "exclude": ["carve/*_test.cc", "carve/**/*_test.cc"],
            "categories": {"foo": {"include": ["carve/foo.cc"]}},
        }
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "coverage.dat"
            path.write_text(report)
            totals = coverage_policy.parse_lcov(path, config)
        for category in ("overall", "foo"):
            self.assertEqual((totals[category]["lines"].hit, totals[category]["lines"].found), (1, 2))
            self.assertEqual((totals[category]["functions"].hit, totals[category]["functions"].found), (1, 1))
            self.assertEqual((totals[category]["branches"].hit, totals[category]["branches"].found), (1, 2))

    def test_thresholds_fail_below_minimum(self):
        totals = {"overall": {metric: coverage_policy.Counts(found=10, hit=5) for metric in coverage_policy.METRICS}}
        report, passed = coverage_policy.render(totals, policy())
        self.assertFalse(passed)
        self.assertIn("50.00%", report)

    def test_empty_report_fails_policy(self):
        totals = {"overall": {metric: coverage_policy.Counts() for metric in coverage_policy.METRICS}}
        report, passed = coverage_policy.render(totals, policy())
        self.assertFalse(passed)
        self.assertIn("0 / 0 | n/a", report)

    def test_summary_has_overview_compatible_schema_and_resolved_policy(self):
        totals = {
            "overall": {metric: coverage_policy.Counts(found=10, hit=9) for metric in coverage_policy.METRICS},
            "cli": {metric: coverage_policy.Counts(found=4, hit=3) for metric in coverage_policy.METRICS},
        }
        config = {
            **policy(),
            "categories": {
                "cli": {
                    "include": ["carve/cli/**"],
                    "minimum": {"branches": 30},
                    "reason": "Generated dispatch code.",
                }
            },
        }
        value = coverage_policy.summary(totals, config)
        self.assertEqual(value["schema"], 2)
        self.assertEqual(value["measurements"]["overall"]["lines"], {"covered": 9, "total": 10, "percent": 90.0})
        self.assertEqual(value["minimums"]["cli"], {"lines": 60, "functions": 50, "branches": 30})
        self.assertEqual(value["targets"]["cli"], config["target"])
        self.assertEqual(value["enforcement"]["cli"], config["enforce"])
        self.assertEqual(value["reasons"]["cli"], "Generated dispatch code.")

    def test_policy_requires_every_metric(self):
        with self.assertRaisesRegex(ValueError, "lines, functions, and branches"):
            coverage_policy.validate({"include": ["carve/**"], "minimum": {"lines": 80}})


if __name__ == "__main__":
    unittest.main()
