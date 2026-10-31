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

"""Downloads official LLVM distributions containing static development libraries."""

_DISTRIBUTIONS = {
    ("linux", "aarch64"): ("LLVM-23.1.4-Linux-ARM64", "9b27cf263d711aa6ebfd4045ab241d947bd09b3cd19ffa5728f48a80c9eb3a91"),
    ("linux", "x86_64"): ("LLVM-23.1.4-Linux-X64", "25d814fda50d5fb0084b42be09605d8b1595d49d5e2e03a3345d7e112ff6f9f3"),
    ("mac os x", "aarch64"): ("LLVM-23.1.4-macOS-ARM64", "5d3179db39adeca5b17a34d82708fe976bc60e055b05fe557878fb3fb64d39ef"),
}

def normalize_arch(arch):
    """Returns the canonical architecture name used by `_DISTRIBUTIONS`."""
    return {
        "amd64": "x86_64",
        "arm64": "aarch64",
    }.get(arch, arch)

def _llvm_prebuilt_repository_impl(repository_ctx):
    platform = (repository_ctx.os.name, normalize_arch(repository_ctx.os.arch))
    distribution = _DISTRIBUTIONS.get(platform)
    if distribution == None:
        fail("No official LLVM 23.1.4 development archive for {}-{}".format(*platform))
    basename, sha256 = distribution
    repository_ctx.download_and_extract(
        sha256 = sha256,
        stripPrefix = basename,
        url = "https://github.com/llvm/llvm-project/releases/download/llvmorg-23.1.4/{}.tar.xz".format(basename),
    )
    repository_ctx.file("BUILD.bazel", repository_ctx.read(repository_ctx.attr.build_file))

_llvm_prebuilt_repository = repository_rule(
    implementation = _llvm_prebuilt_repository_impl,
    attrs = {"build_file": attr.label(allow_single_file = True)},
)

def _llvm_prebuilt_impl(_):
    _llvm_prebuilt_repository(
        name = "carve_llvm_prebuilt",
        build_file = "//third_party/llvm:prebuilt.BUILD.bazel",
    )

llvm_prebuilt = module_extension(implementation = _llvm_prebuilt_impl)
