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
        policy = {"include": ["carve/**"], "exclude": ["carve/*_test.cc", "carve/**/*_test.cc"]}
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "coverage.dat"
            path.write_text(report)
            totals = coverage_policy.parse_lcov(path, policy)
        self.assertEqual((totals["lines"].hit, totals["lines"].found), (1, 2))
        self.assertEqual((totals["functions"].hit, totals["functions"].found), (1, 1))
        self.assertEqual((totals["branches"].hit, totals["branches"].found), (1, 2))

    def test_thresholds_fail_below_minimum(self):
        totals = {metric: coverage_policy.Counts(found=10, hit=5) for metric in coverage_policy.METRICS}
        report, passed = coverage_policy.render(
            totals, {"minimum": {"lines": 60, "functions": 50, "branches": 40}}
        )
        self.assertFalse(passed)
        self.assertIn("50.00%", report)

    def test_empty_report_fails_policy(self):
        totals = {metric: coverage_policy.Counts() for metric in coverage_policy.METRICS}
        report, passed = coverage_policy.render(
            totals, {"minimum": {"lines": 60, "functions": 50, "branches": 40}}
        )
        self.assertFalse(passed)
        self.assertIn("0 / 0 | 0.00%", report)

    def test_policy_requires_every_metric(self):
        with self.assertRaisesRegex(ValueError, "lines, functions, and branches"):
            coverage_policy.validate({"include": ["carve/**"], "minimum": {"lines": 80}})


if __name__ == "__main__":
    unittest.main()
