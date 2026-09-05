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

readonly tool="$(dirname "$0")/ci_with_heartbeat.sh"

output="$(CARVE_CI_HEARTBEAT_SECONDS=0.01 "${tool}" sh -c 'echo warning; sleep 0.04; echo error >&2' 2>&1)"
grep -q '^warning$' <<<"${output}"
grep -q '^error$' <<<"${output}"
grep -q '^Still running after .*s: sh$' <<<"${output}"

status=0
CARVE_CI_HEARTBEAT_SECONDS=0.01 "${tool}" sh -c 'exit 7' || status="$?"
[[ "${status}" == 7 ]]
