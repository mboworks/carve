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

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "${TEST_ROOT}"' EXIT

REMOTE="${TEST_ROOT}/origin.git"
WORK="${TEST_ROOT}/work"
BIN="${TEST_ROOT}/bin"
mkdir -p "${BIN}"
git init --bare --quiet "${REMOTE}"
git init --quiet "${WORK}"
git -C "${WORK}" config user.name "Carve release test"
git -C "${WORK}" config user.email "carve-release-test@example.invalid"
git -C "${WORK}" config commit.gpgsign false

mkdir -p "${WORK}/.pre-commit" "${WORK}/tools"
cp "${ROOT}/.pre-commit/check_version.sh" "${WORK}/.pre-commit/"
cp "${ROOT}/tools/trigger_release.sh" "${WORK}/tools/"
cat >"${WORK}/MODULE.bazel" <<'EOF'
module(name = "mboworks_carve", version = "0.1.0")
EOF
cat >"${WORK}/CHANGELOG.md" <<'EOF'
# Changelog

## [Unreleased]

## [0.1.0] - 2026-08-31

- First release.
EOF
git -C "${WORK}" add .
git -C "${WORK}" commit --quiet -m "Prepare release fixture"
git -C "${WORK}" branch -M main
git -C "${WORK}" remote add origin "${REMOTE}"
git -C "${WORK}" push --quiet -u origin main

# The helper only queries `gh release view` during a dry run. Exit nonzero to
# model a release that does not exist yet without requiring network access.
cat >"${BIN}/gh" <<'EOF'
#!/usr/bin/env bash
exit 1
EOF
chmod +x "${BIN}/gh"

(
  cd "${WORK}"
  output="$(PATH="${BIN}:${PATH}" tools/trigger_release.sh --dry-run 0.1.0)"
  grep -q "Would create and push signed tag '0.1.0'" <<<"${output}"
)

touch "${WORK}/dirty"
if (cd "${WORK}" && PATH="${BIN}:${PATH}" tools/trigger_release.sh --dry-run 0.1.0 >/dev/null 2>&1); then
  echo "trigger_release.sh accepted a dirty worktree" 1>&2
  exit 1
fi
rm "${WORK}/dirty"

git -C "${WORK}" tag 0.1.0
(cd "${WORK}" && .pre-commit/check_version.sh)
echo later >"${WORK}/later"
git -C "${WORK}" add later
git -C "${WORK}" commit --quiet -m "Add post-release work"
if (cd "${WORK}" && .pre-commit/check_version.sh >/dev/null 2>&1); then
  echo "check_version.sh accepted post-release work at the released version" 1>&2
  exit 1
fi

sed -i.bak 's/version = "0.1.0"/version = "0.2.0"/' "${WORK}/MODULE.bazel"
sed -i.bak 's/## \[0.1.0\]/## [0.2.0]/' "${WORK}/CHANGELOG.md"
rm "${WORK}/MODULE.bazel.bak" "${WORK}/CHANGELOG.md.bak"
(cd "${WORK}" && .pre-commit/check_version.sh)
