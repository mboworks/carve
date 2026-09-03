#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) M. Boerger, the MBO Works authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for the clang-tidy translation-unit selector."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clang_tidy


class SelectedSourcesTest(unittest.TestCase):
    def test_selects_unique_first_party_cc_files(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            database = [
                {"file": "carve/a/a.cc", "directory": raw},
                {"file": str(root / "carve/a/a.cc"), "directory": "/ignored"},
                {"file": "external/dep.cc", "directory": raw},
                {"file": "carve/a/a.h", "directory": raw},
            ]
            self.assertEqual(clang_tidy.selected_sources(database, None, root), ["carve/a/a.cc"])

    def test_requested_files_limit_the_database(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            database = [
                {"file": "carve/a/a.cc", "directory": raw},
                {"file": "carve/b/b.cc", "directory": raw},
            ]
            self.assertEqual(
                clang_tidy.selected_sources(database, {"carve/b/b.cc", "README.md"}, root),
                ["carve/b/b.cc"],
            )

    def test_outside_absolute_path_is_ignored(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.assertEqual(
                clang_tidy.selected_sources([{"file": "/external/dep.cc", "directory": raw}], None, root),
                [],
            )


if __name__ == "__main__":
    unittest.main()
