#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) M. Boerger, the MBO Works authors
# SPDX-License-Identifier: Apache-2.0

import subprocess
import tempfile
import unittest
from pathlib import Path


class ShellPolicyTest(unittest.TestCase):
    def run_check(self, script: str, source: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "sample_test.cc"
            path.write_text(source)
            return subprocess.run(
                [str(Path(__file__).parent / script), str(path)], capture_output=True, text=True, check=False
            )

    def test_matcher_check_rejects_comparison_macro(self):
        self.assertNotEqual(self.run_check("check_test_matchers.sh", "EXPECT_EQ(got, want);\n").returncode, 0)

    def test_matcher_check_accepts_imported_matcher(self):
        self.assertEqual(self.run_check("check_test_matchers.sh", "EXPECT_THAT(got, Eq(want));\n").returncode, 0)

    def test_check_macro_check_rejects_boolean_comparison(self):
        self.assertNotEqual(self.run_check("check_check_macros.sh", "CHECK(got == want);\n").returncode, 0)

    def test_check_macro_check_accepts_comparing_macro(self):
        self.assertEqual(self.run_check("check_check_macros.sh", "CHECK_EQ(got, want);\n").returncode, 0)


if __name__ == "__main__":
    unittest.main()
