#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) M. Boerger, the MBO Works authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for source-owned LCOV normalization."""

import tempfile
import unittest
from pathlib import Path

from tools import coverage_sources


class CoverageSourcesTest(unittest.TestCase):
    def test_applies_line_branch_function_and_block_exclusions(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            source = workspace / "carve/process/example.cc"
            source.parent.mkdir(parents=True)
            source.write_text(
                "int excluded() {  // LCOV_EXCL_FUNC_LINE, LCOV_EXCL_LINE\n"
                "if (runtime) {}  // LCOV_EXCL_BR_LINE\n"
                "// LCOV_EXCL_START: child profile cannot flush.\n"
                "child_only();\n"
                "// LCOV_EXCL_STOP\n"
                "return covered;\n",
                encoding="utf-8",
            )
            report = (
                "SF:carve/process/example.cc\n"
                "FN:1,excluded\nFN:6,covered\nFNDA:0,excluded\nFNDA:1,covered\n"
                "FNF:2\nFNH:1\n"
                "BRDA:2,0,0,0\nBRDA:2,0,1,1\nBRDA:4,0,0,0\n"
                "BRF:3\nBRH:1\n"
                "DA:1,0\nDA:2,1\nDA:3,1\nDA:4,0\nDA:5,1\nDA:6,1\n"
                "LF:6\nLH:4\nend_of_record\n"
            )

            actual = coverage_sources.normalized(report, workspace)

            self.assertNotIn("excluded", actual)
            self.assertIn("FN:6,covered\nFNDA:1,covered\nFNF:1\nFNH:1", actual)
            self.assertNotIn("BRDA:", actual)
            self.assertIn("BRF:0\nBRH:0", actual)
            self.assertIn("DA:2,1\nDA:6,1\nLF:2\nLH:2", actual)

    def test_rejects_unbalanced_exclusion_blocks(self):
        with self.assertRaisesRegex(ValueError, "has no LCOV_EXCL_STOP"):
            coverage_sources._excluded_blocks(["// LCOV_EXCL_START"])
        with self.assertRaisesRegex(ValueError, "without LCOV_EXCL_START"):
            coverage_sources._excluded_blocks(["// LCOV_EXCL_STOP"])
        with self.assertRaisesRegex(ValueError, "nested LCOV_EXCL_START"):
            coverage_sources._excluded_blocks(
                ["// LCOV_EXCL_START", "// LCOV_EXCL_START"]
            )

    def test_preserves_records_without_checked_in_sources(self):
        report = "SF:external/dependency/example.cc\nDA:1,1\nLF:1\nLH:1\nend_of_record\n"
        self.assertEqual(report, coverage_sources.normalized(report))


if __name__ == "__main__":
    unittest.main()
