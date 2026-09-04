#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) M. Boerger, the MBO Works authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for the clang-tidy translation-unit selector."""

import os
import sys
import tempfile
import unittest
from unittest import mock
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

    @mock.patch("clang_tidy.subprocess.run")
    def test_run_limits_header_diagnostics_to_first_party_code(self, run):
        run.return_value = mock.Mock(returncode=0, stdout="")
        clang_tidy.run_one("clang-tidy", Path("compile_commands.json"), "carve/a/a.cc")
        self.assertEqual(
            run.call_args.args[0],
            [
                "clang-tidy",
                "-p",
                ".",
                "--header-filter=^carve/",
                "--exclude-header-filter=(^|.*/)(bazel-out|external)/",
                "carve/a/a.cc",
            ],
        )

    def test_crashing_llvm_check_is_disabled(self):
        config = (Path(__file__).parent.parent / ".clang-tidy").read_text(encoding="utf-8")
        checks = config.split("Checks: >", 1)[1].split("WarningsAsErrors:", 1)[0]
        self.assertGreater(
            checks.rfind("-abseil-unchecked-statusor-access,"),
            checks.rfind("abseil-*"),
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
