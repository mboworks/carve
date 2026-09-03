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

readonly COMPARISON='\b(ASSERT|EXPECT)_(EQ|NE|LT|LE|GT|GE|STREQ|STRNE|STRCASEEQ|STRCASENE|FLOAT_EQ|DOUBLE_EQ|NEAR)[[:space:]]*\('
readonly QUALIFIED='(::mbo::)?testing::[A-Z][A-Za-z0-9_]*\('
readonly QUALIFIED_UTILITY='testing::(ExplainMatchResult|MakeMatcher|MakePolymorphicMatcher|PrintToString|Return|RunfilesDirOrDie|TempDir|Test|TestWithParam|Values)\('

status=0
for file in "$@"; do
  source="$(sed 's|//.*||' "${file}")"
  comparisons="$(grep -nE "${COMPARISON}" <<<"${source}" || true)"
  qualified="$(grep -nE "${QUALIFIED}" <<<"${source}" | grep -vE "${QUALIFIED_UTILITY}" || true)"
  if [[ -n ${comparisons} ]]; then
    echo "${file}: use EXPECT_THAT / ASSERT_THAT and a matcher:" >&2
    echo "${comparisons}" >&2
    status=1
  fi
  if [[ -n ${qualified} ]]; then
    echo "${file}: import matchers with a using declaration instead of qualifying them inline:" >&2
    echo "${qualified}" >&2
    status=1
  fi
done
exit "${status}"
