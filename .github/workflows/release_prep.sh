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

# Invoked by the release workflow. It builds the source archive that consumers
# fetch and prints the GitHub release notes (stdout). Nothing here publishes.

set -euo pipefail

PACKAGE_NAME="carve"
BAZELMOD_NAME="mboworks_carve"

# Tagged releases use GitHub's immutable ref name. CI archive-consumer tests use
# an explicit version because GitHub does not permit overriding GITHUB_* vars.
TAG="${CARVE_RELEASE_VERSION:-${GITHUB_REF_NAME}}"

function die() {
  echo "ERROR: ${*}" 1>&2
  exit 1
}

# Computed vars.
PREFIX="${PACKAGE_NAME}-${TAG}"
ARCHIVE="${CARVE_RELEASE_OUTPUT_DIR:-.}/${PACKAGE_NAME}-${TAG}.tar.gz"
BAZELMOD_VERSION="$(sed -rne 's,.*version = "([0-9]+([.][0-9]+)+.*)".*,\1,p' <MODULE.bazel | head -n1)"
# carve uses Keep a Changelog: the first "## [x.y.z]" heading (after "## [Unreleased]").
CHANGELOG_VERSION="$(sed -rne 's,^## \[([0-9]+([.][0-9]+)+)\].*,\1,p' <CHANGELOG.md | head -n1)"
BCR_TEST_VERSION="$(sed -rne 's|.*bazel_dep\(name = "mboworks_carve", version = "([0-9]+([.][0-9]+)+)"\).*|\1|p' <examples/bcr/MODULE.bazel | head -n1)"

if [ "${BAZELMOD_VERSION}" != "${TAG}" ]; then
  die "Tag = '${TAG}' does not match version = '${BAZELMOD_VERSION}' in MODULE.bazel."
fi
if [ "${CHANGELOG_VERSION}" != "${TAG}" ]; then
  die "Tag = '${TAG}' does not match the latest release version = '${CHANGELOG_VERSION}' in CHANGELOG.md."
fi
if [ "${BCR_TEST_VERSION}" != "${TAG}" ]; then
  die "Tag = '${TAG}' does not match the BCR consumer version = '${BCR_TEST_VERSION}'."
fi

# Prepare release-only files in a temporary directory. The checkout must remain
# unchanged so a retry produces the same tree and does not accumulate export
# rules.
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT
RELEASE_BUILD="${WORK}/BUILD.bazel"
RELEASE_MODULE="${WORK}/MODULE.bazel"
RELEASE_ATTRIBUTES="${WORK}/.gitattributes"
TMP_INDEX="${WORK}/index"

# Replace the root BUILD.bazel with an empty one for the released module:
# carve's root targets are for development, not dependents.
{
  cat tools/header.txt
  echo ""
  echo "\"\"\"Empty root BUILD for @${BAZELMOD_NAME}.\"\"\""
} >"${RELEASE_BUILD}"

# Comment the dev-only include so the released module does not reference the
# development modules (hedron, dwyu). The bazelmod package remains in the
# archive because MODULE.bazel uses its toolchains_llvm patch.
cp MODULE.bazel "${RELEASE_MODULE}"
perl -pi -e 's,^include\("//bazelmod:dev\.MODULE\.bazel"\),# include("//bazelmod:dev.MODULE.bazel"),' "${RELEASE_MODULE}"
grep -qE '^# include\("//bazelmod:dev\.MODULE\.bazel"\)' "${RELEASE_MODULE}" ||
  die "Failed to comment the dev include in MODULE.bazel (did the line change?)."

# Exclude development-only paths from the archive.
EXCLUDES=(
  ".bcr"
  ".github"
  ".pre-commit-config.yaml"
  "bazelmod/dev.MODULE.bazel"
  "tools"
)
if git cat-file -e HEAD:.gitattributes 2>/dev/null; then
  git show HEAD:.gitattributes >"${RELEASE_ATTRIBUTES}"
fi
{
  for exclude in "${EXCLUDES[@]}"; do
    echo "${exclude} export-ignore"
    if [[ -d ${exclude} ]]; then
      echo "${exclude}/** export-ignore"
    fi
  done
} >>"${RELEASE_ATTRIBUTES}"

# Build a release tree through a throwaway index. hash-object adds unreachable
# blobs to the local object store, but neither the worktree nor real index is
# changed.
GIT_INDEX_FILE="${TMP_INDEX}" git read-tree HEAD
for release_file in BUILD.bazel MODULE.bazel .gitattributes; do
  source_file="${WORK}/${release_file}"
  blob="$(git hash-object -w "${source_file}")"
  GIT_INDEX_FILE="${TMP_INDEX}" git update-index --add --cacheinfo "100644,${blob},${release_file}"
done
ARCHIVE_TREE="$(GIT_INDEX_FILE="${TMP_INDEX}" git write-tree)"
git archive --format=tar --prefix="${PREFIX}/" -o "${WORK}/archive.tar" \
  --add-virtual-file="${PREFIX}/VERSION:${TAG}" "${ARCHIVE_TREE}"
gzip -9 -n -c "${WORK}/archive.tar" >"${ARCHIVE}"

# Release notes (stdout).
echo "# Version ${TAG}"
echo "## [Changelog](https://github.com/mboworks/${PACKAGE_NAME}/blob/${TAG}/CHANGELOG.md)"
echo ""

# Print the body of the "## [${TAG}]" section from the Keep a Changelog file.
awk -v tag="${TAG}" '
  $0 ~ ("^## \\[" tag "\\]") { grab = 1; next }
  grab && /^## / { exit }
  grab { print }
' <CHANGELOG.md

cat <<EOF

## Bazel module

The attached archive is the complete source release. BCR publication is an
independent later step. After \`${BAZELMOD_NAME}@${TAG}\` is available from the
Bazel Central Registry, add:

\`\`\`bzl
bazel_dep(name = "${BAZELMOD_NAME}", version = "${TAG}")
\`\`\`

carve builds from source through your toolchain on first use; later builds hit
Bazel's cache. See the README for the \`carve_refresh\` / \`cc_carve_aspect\` rules.
EOF

printf '\n'
bash tools/release_notes.sh "${TAG}"
