# SPDX-FileCopyrightText: Copyright (c) M. Boerger, the MBO Works authors
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the Bazel compiler-warning policy."""

from pathlib import Path
import unittest


class BazelrcPolicyTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.lines = {
            line.strip()
            for line in Path(".bazelrc").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }

    def test_c_and_cpp_warnings_are_errors_for_target_and_host(self):
        self.assertIn(
            "common --copt=-Wall --copt=-Werror --cxxopt=-Wall --cxxopt=-Werror",
            self.lines,
        )
        self.assertIn(
            "common --host_copt=-Wall --host_copt=-Werror --host_cxxopt=-Wall "
            "--host_cxxopt=-Werror",
            self.lines,
        )

    def test_first_party_sources_enable_extra_and_pedantic_warnings(self):
        warning_flags = (
            "-Wextra,-Wpedantic,-Wno-c2y-extensions,-Wno-gcc-compat,"
            "-Wno-nullability-extension,-Wno-missing-field-initializers,"
            "-Wno-missing-designated-field-initializers"
        )
        self.assertIn(
            f"common --per_file_copt=.*,-external/.*@{warning_flags}", self.lines
        )
        self.assertIn(
            f"common --host_per_file_copt=.*,-external/.*@{warning_flags}",
            self.lines,
        )

    def test_external_headers_are_system_headers_for_target_and_host(self):
        self.assertIn(
            "common --features=external_include_paths --host_features=external_include_paths",
            self.lines,
        )

    def test_external_source_warnings_are_muted_for_target_and_host(self):
        self.assertIn("common --per_file_copt=external/.*@-w", self.lines)
        self.assertIn("common --host_per_file_copt=external/.*@-w", self.lines)


if __name__ == "__main__":
    unittest.main()
