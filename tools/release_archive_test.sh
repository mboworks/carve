#!/usr/bin/env bash

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

set -euo pipefail

function die() {
  echo "ERROR: ${*}" 1>&2
  exit 1
}

if (( $# < 1 )); then
  echo "Usage: $0 ARCHIVE [bazel build options...]" >&2
  exit 2
fi

archive="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
shift
[[ -f ${archive} ]] || die "Release archive not found: ${archive}"

work="$(mktemp -d)"
trap 'rm -rf "${work}"' EXIT
tar -xzf "${archive}" -C "${work}"

root="$(find "${work}" -mindepth 1 -maxdepth 1 -type d -print -quit)"
[[ -n ${root} ]] || die "Release archive has no root directory."
version="$(<"${root}/VERSION")"
[[ $(basename "${root}") == "carve-${version}" ]] || die "Release archive root does not match VERSION."
grep -q "version = \"${version}\"" "${root}/MODULE.bazel" || die "MODULE.bazel version does not match VERSION."
grep -q '^# include("//bazelmod:dev.MODULE.bazel")' "${root}/MODULE.bazel" || die "Development module include is not disabled."
[[ -f ${root}/carve.bazelrc ]] || die "Release archive is missing carve.bazelrc."
[[ -f ${root}/bazelmod/BUILD.bazel ]] || die "Release archive is missing the bazelmod package."
[[ -f ${root}/bazelmod/toolchains_llvm-clang-headers.patch ]] || die "Release archive is missing the toolchains_llvm patch."

for excluded in .bcr .github bazelmod/dev.MODULE.bazel tools; do
  [[ ! -e ${root}/${excluded} ]] || die "Release archive contains excluded path: ${excluded}"
done

consumer="${work}/consumer"
mkdir "${consumer}"
cp "${root}/carve.bazelrc" "${consumer}/carve.bazelrc"

{
  echo 'module(name = "carve_release_consumer")'
  echo "bazel_dep(name = \"mboworks_carve\", version = \"${version}\")"
  echo "local_path_override(module_name = \"mboworks_carve\", path = \"${root}\")"
} >"${consumer}/MODULE.bazel"

cat >"${consumer}/BUILD.bazel" <<'EOF'
alias(
    name = "carve",
    actual = "@mboworks_carve//carve:carve",
)
EOF

echo 'try-import %workspace%/carve.bazelrc' >"${consumer}/.bazelrc"

(
  cd "${consumer}"
  bazel build --config=clang //:carve "$@"
)
