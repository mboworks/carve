#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) M. Boerger, the MBO Works authors
# SPDX-License-Identifier: Apache-2.0

import tempfile
import unittest
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_status_assert


class CheckStatusAssertTest(unittest.TestCase):
    def check(self, source: str) -> list[str]:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "sample_test.cc"
            path.write_text(source)
            return check_status_assert.check(path)

    def test_rejects_assert_ok_then_arrow(self):
        self.assertEqual(len(self.check("ASSERT_THAT(value, IsOk());\nvalue->Run();\n")), 1)

    def test_rejects_assert_ok_then_star(self):
        self.assertEqual(len(self.check("ASSERT_THAT(value, IsOk());\nUse(*value);\n")), 1)

    def test_allows_plain_status(self):
        self.assertEqual(self.check("ASSERT_THAT(status, IsOk());\nreturn;\n"), [])

    def test_allows_combined_matcher(self):
        self.assertEqual(self.check("EXPECT_THAT(value, IsOkAndHolds(Eq(1)));\n"), [])


if __name__ == "__main__":
    unittest.main()
