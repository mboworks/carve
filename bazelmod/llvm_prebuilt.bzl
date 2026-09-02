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
    ("linux", "aarch64"): ("LLVM-22.1.8-Linux-ARM64", "805efad2bb91cb4967fa569e0881d10c0f69c04461cf671cccbae19f547acc34"),
    ("linux", "x86_64"): ("LLVM-22.1.8-Linux-X64", "df0e1ecf16caf3489a272a5eea4eec9b0d82878f6477fa309504f918a0006384"),
    ("mac os x", "aarch64"): ("LLVM-22.1.8-macOS-ARM64", "f260f4f7c0d430828a81ae8a3826a1d63fc0963ec2459489308cc23b1f7eab4f"),
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
        fail("No official LLVM 22.1.8 development archive for {}-{}".format(*platform))
    basename, sha256 = distribution
    repository_ctx.download_and_extract(
        sha256 = sha256,
        stripPrefix = basename,
        url = "https://github.com/llvm/llvm-project/releases/download/llvmorg-22.1.8/{}.tar.xz".format(basename),
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
