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
        cls.root_lines = {
            line.strip()
            for line in Path(".bazelrc").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        cls.public_lines = {
            line.strip()
            for line in Path("carve.bazelrc").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }

    def test_c_and_cpp_warnings_are_errors_for_target_and_host(self):
        self.assertIn(
            "common --copt=-Wall --copt=-Werror --cxxopt=-Wall --cxxopt=-Werror",
            self.root_lines,
        )
        self.assertIn(
            "common --host_copt=-Wall --host_copt=-Werror --host_cxxopt=-Wall "
            "--host_cxxopt=-Werror",
            self.root_lines,
        )

    def test_first_party_sources_enable_extra_and_pedantic_warnings(self):
        warning_flags = (
            "-Wextra,-Wpedantic,-Wno-c2y-extensions,-Wno-gcc-compat,"
            "-Wno-nullability-extension,-Wno-missing-field-initializers,"
            "-Wno-missing-designated-field-initializers"
        )
        self.assertIn(
            f"common --per_file_copt=.*,-external/.*@{warning_flags}",
            self.root_lines,
        )
        self.assertIn(
            f"common --host_per_file_copt=.*,-external/.*@{warning_flags}",
            self.root_lines,
        )

    def test_external_headers_are_system_headers_for_target_and_host(self):
        self.assertIn(
            "common --features=external_include_paths --host_features=external_include_paths",
            self.root_lines,
        )

    def test_external_source_warnings_are_muted_for_target_and_host(self):
        self.assertIn("common --per_file_copt=external/.*@-w", self.root_lines)
        self.assertIn("common --host_per_file_copt=external/.*@-w", self.root_lines)

    def test_coverage_includes_targets_excluded_only_from_sanitizers(self):
        self.assertNotIn("coverage:coverage --build_tag_filters=-no_san", self.root_lines)
        self.assertNotIn("coverage:coverage --test_tag_filters=-no_san", self.root_lines)
        for config in ("asan", "tsan", "msan"):
            self.assertIn(f"common:{config} --build_tag_filters=-no_san", self.root_lines)
            self.assertIn(f"common:{config} --test_tag_filters=-no_san", self.root_lines)

    def test_public_policy_is_strict_for_carve_and_mutes_other_external_sources(self):
        warning_flags = (
            "-Wall,-Wextra,-Wpedantic,-Werror,-Wno-c2y-extensions,-Wno-gcc-compat,"
            "-Wno-nullability-extension,-Wno-missing-field-initializers,"
            "-Wno-missing-designated-field-initializers"
        )
        self.assertIn(
            "common --features=external_include_paths --host_features=external_include_paths",
            self.public_lines,
        )
        for host in ("", "host_"):
            self.assertIn(
                f"common --{host}per_file_copt=external/.*,-external/mboworks_carve.*@-w",
                self.public_lines,
            )
            self.assertIn(
                f"common --{host}per_file_copt=external/mboworks_carve.*@{warning_flags}",
                self.public_lines,
            )


if __name__ == "__main__":
    unittest.main()
