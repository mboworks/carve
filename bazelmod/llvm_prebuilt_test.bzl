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

"""Tests for the prebuilt LLVM distribution extension."""

load("@bazel_skylib//lib:unittest.bzl", "asserts", "unittest")
load(":llvm_prebuilt.bzl", _normalize_arch = "normalize_arch")

def _normalize_arch_test_impl(ctx):
    env = unittest.begin(ctx)
    asserts.equals(env, "x86_64", _normalize_arch("amd64"))
    asserts.equals(env, "x86_64", _normalize_arch("x86_64"))
    asserts.equals(env, "aarch64", _normalize_arch("arm64"))
    asserts.equals(env, "aarch64", _normalize_arch("aarch64"))
    return unittest.end(env)

_normalize_arch_test = unittest.make(_normalize_arch_test_impl)

def llvm_prebuilt_test_suite(name):
    """Defines tests for the prebuilt LLVM extension."""
    _normalize_arch_test(name = name)
