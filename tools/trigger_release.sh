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

DRY_RUN=false
VERSION=""
for arg in "${@}"; do
  case "${arg}" in
    --dry | --dry-run) DRY_RUN=true ;;
    -*) die "Unknown option '${arg}'. Usage: ${0} [--dry-run] <version>" ;;
    *)
      [[ -z "${VERSION}" ]] || die "Usage: ${0} [--dry-run] <version>"
      VERSION="${arg}"
      ;;
  esac
done
[[ -n "${VERSION}" ]] || die "Usage: ${0} [--dry-run] <version>"
[[ "${VERSION}" =~ ^(0|[1-9][0-9]*)[.](0|[1-9][0-9]*)[.](0|[1-9][0-9]*)$ ]] ||
  die "Version '${VERSION}' must use numeric X.Y.Z format."

for tool in gh git gpg; do
  command -v "${tool}" >/dev/null 2>&1 || die "Required tool '${tool}' is not installed."
done

git fetch origin main --tags
[[ "$(git branch --show-current)" == "main" ]] || die "Must be run from main."
[[ -z "$(git status --porcelain)" ]] || die "Working tree must be clean."
[[ "$(git rev-parse HEAD)" == "$(git rev-parse origin/main)" ]] ||
  die "Local main must equal origin/main."

BAZELMOD_VERSION="$(sed -rne 's,.*version = "([0-9]+([.][0-9]+)+.*)".*,\1,p' MODULE.bazel | head -n1)"
CHANGELOG_VERSION="$(sed -rne 's,^## \[([0-9]+([.][0-9]+)+)\].*,\1,p' CHANGELOG.md | head -n1)"
[[ "${BAZELMOD_VERSION}" == "${CHANGELOG_VERSION}" ]] ||
  die "MODULE.bazel (${BAZELMOD_VERSION}) != CHANGELOG.md (${CHANGELOG_VERSION})."
[[ "${VERSION}" == "${BAZELMOD_VERSION}" ]] ||
  die "Requested version (${VERSION}) != repository version (${BAZELMOD_VERSION})."
[[ -z "$(git tag --list "${VERSION}")" ]] || die "Tag '${VERSION}' already exists."
gh release view "${VERSION}" >/dev/null 2>&1 && die "Release '${VERSION}' already exists."

if [[ "${DRY_RUN}" == true ]]; then
  echo "[dry-run] Would create and push signed tag '${VERSION}' at $(git rev-parse HEAD)."
  echo "[dry-run] GitHub Actions would create a prerelease, then open the BCR publication PR."
  exit 0
fi

git tag -s -a "${VERSION}" \
  -m "New release tag version: '${VERSION}'." \
  -m "$(awk -v tag="${VERSION}" '
    $0 ~ ("^## \\[" tag "\\]") { grab = 1; next }
    grab && /^## / { exit }
    grab { print }
  ' CHANGELOG.md)"
git push origin "refs/tags/${VERSION}"
echo "Pushed signed release tag '${VERSION}'. GitHub Actions will create the prerelease and BCR PR."
