#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) M. Boerger, the MBO Works authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for header ownership and guard checks."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_header_guards
import check_headers_claimed


class HeaderGuardsTest(unittest.TestCase):
    def test_expected_guard_uses_full_path(self):
        self.assertEqual(check_header_guards.expected_guard("carve/io/io.h"), "CARVE_IO_IO_H_")

    def test_accepts_matching_guard_and_closing_comment(self):
        with tempfile.TemporaryDirectory() as raw:
            current = Path.cwd()
            try:
                os.chdir(raw)
                path = Path("carve/io/io.h")
                path.parent.mkdir(parents=True)
                path.write_text("#ifndef CARVE_IO_IO_H_\n#define CARVE_IO_IO_H_\n#endif  // CARVE_IO_IO_H_\n")
                self.assertEqual(check_header_guards.check(path), [])
            finally:
                os.chdir(current)

    def test_rejects_wrong_guard(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "carve/io/io.h"
            path.parent.mkdir(parents=True)
            path.write_text("#ifndef WRONG_\n#define WRONG_\n#endif  // WRONG_\n")
            self.assertTrue(check_header_guards.check(path))


class HeadersClaimedTest(unittest.TestCase):
    def test_finds_nearest_owning_build_and_claim(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "carve/io/sub").mkdir(parents=True)
            (root / "carve/io/sub/detail.h").write_text("header")
            (root / "carve/io/BUILD.bazel").write_text('cc_library(hdrs = ["sub/detail.h"])\n')
            self.assertEqual(check_headers_claimed.check(["carve/io/sub/detail.h"], root), [])

    def test_reports_unclaimed_header(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "carve/io").mkdir(parents=True)
            (root / "carve/io/io.h").write_text("header")
            (root / "carve/io/BUILD.bazel").write_text("cc_library()\n")
            self.assertEqual(
                check_headers_claimed.check(["carve/io/io.h"], root),
                ["carve/io/io.h: not listed in carve/io/BUILD.bazel"],
            )


if __name__ == "__main__":
    unittest.main()
