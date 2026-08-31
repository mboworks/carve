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

function version_key() {
  awk -F. '{ printf "%010d%010d%010d\n", $1, $2, $3 }' <<<"${1}"
}

BAZELMOD_VERSION="$(sed -rne 's,.*version = "([0-9]+([.][0-9]+)+.*)".*,\1,p' <MODULE.bazel | head -n1)"
CHANGELOG_VERSION="$(sed -rne 's,^## \[([0-9]+([.][0-9]+)+)\].*,\1,p' <CHANGELOG.md | head -n1)"

[[ "${BAZELMOD_VERSION}" == "${CHANGELOG_VERSION}" ]] ||
  die "MODULE.bazel (${BAZELMOD_VERSION}) != CHANGELOG.md (${CHANGELOG_VERSION})."
[[ "${BAZELMOD_VERSION}" =~ ^(0|[1-9][0-9]*)[.](0|[1-9][0-9]*)[.](0|[1-9][0-9]*)$ ]] ||
  die "MODULE.bazel version (${BAZELMOD_VERSION}) must use numeric X.Y.Z format."

LATEST_RELEASE="$(
  git tag --list |
    awk '/^(0|[1-9][0-9]*)[.](0|[1-9][0-9]*)[.](0|[1-9][0-9]*)$/' |
    while read -r version; do
      printf '%s %s\n' "$(version_key "${version}")" "${version}"
    done |
    sort |
    tail -n1 |
    awk '{ print $2 }'
)"

if [[ -n "${LATEST_RELEASE}" ]] &&
  [[ "$(version_key "${BAZELMOD_VERSION}")" < "$(version_key "${LATEST_RELEASE}")" ]]; then
  die "Development version (${BAZELMOD_VERSION}) is older than latest release tag (${LATEST_RELEASE})."
fi

# Equality is valid only at the released commit. The first later commit must
# advance MODULE.bazel and the newest released CHANGELOG heading together.
if [[ -n "${LATEST_RELEASE}" ]] &&
  [[ "${BAZELMOD_VERSION}" == "${LATEST_RELEASE}" ]] &&
  [[ "$(git rev-parse HEAD)" != "$(git rev-list -n1 "${LATEST_RELEASE}")" ]]; then
  die "Development version (${BAZELMOD_VERSION}) still matches latest release tag (${LATEST_RELEASE}), but HEAD contains later work. Bump MODULE.bazel and CHANGELOG.md."
fi
