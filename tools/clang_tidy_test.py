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

    @mock.patch("clang_tidy.subprocess.Popen")
    def test_run_limits_header_diagnostics_to_first_party_code(self, run):
        run.return_value = mock.Mock(returncode=0)
        run.return_value.communicate.return_value = ("", None)
        clang_tidy.run_one("clang-tidy", Path("compile_commands.json"), "carve/a/a.cc", clang_tidy.ProcessRegistry())
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

    def test_stopped_pool_does_not_start_queued_processes(self):
        registry = clang_tidy.ProcessRegistry()
        registry.terminate_all()
        with mock.patch("clang_tidy.subprocess.Popen") as spawn:
            result = clang_tidy.run_one("clang-tidy", Path("compile_commands.json"), "carve/a/a.cc", registry)
        spawn.assert_not_called()
        self.assertEqual(result, ("carve/a/a.cc", 130, ""))

    def test_default_workers_are_bounded_and_explicit_zero_is_rejected(self):
        import contextlib
        import io
        import json
        import threading
        import time
        with tempfile.TemporaryDirectory() as raw:
            database = Path(raw) / "compile_commands.json"
            database.write_text(json.dumps([
                {"file": f"carve/a/{index}.cc", "directory": str(Path.cwd())}
                for index in range(8)
            ]))
            for cpus, jobs, expected in [(128, [], 2), (1, [], 1), (128, ["--jobs", "3"], 3)]:
                active = peak = 0
                lock = threading.Lock()

                def worker(_executable, _database, source, _registry):
                    nonlocal active, peak
                    with lock:
                        active += 1
                        peak = max(peak, active)
                    time.sleep(0.02)
                    with lock:
                        active -= 1
                    return source, 0, ""

                with self.subTest(cpus=cpus, jobs=jobs), mock.patch("clang_tidy.os.cpu_count", return_value=cpus), \
                        mock.patch("clang_tidy.run_one", side_effect=worker), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(clang_tidy.main(["--clang-tidy", "tidy", "--database", str(database), *jobs]), 0)
                self.assertEqual(peak, expected)
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                clang_tidy.main(["--clang-tidy", "tidy", "--jobs", "0"])

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
