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

set -uo pipefail

if (( $# == 0 )); then
  echo "Usage: $0 COMMAND [ARG...]" >&2
  exit 2
fi

readonly interval="${CARVE_CI_HEARTBEAT_SECONDS:-10}"
readonly started_at="${SECONDS}"

"$@" &
readonly command_pid="$!"

function heartbeat() {
  local sleep_pid=""
  trap 'kill "${sleep_pid}" 2>/dev/null || true; wait "${sleep_pid}" 2>/dev/null || true; exit 0' TERM
  while true; do
    sleep "${interval}" &
    sleep_pid="$!"
    wait "${sleep_pid}" || return
    kill -0 "${command_pid}" 2>/dev/null || return
    echo "Still running after $((SECONDS - started_at))s: $1"
  done
}

heartbeat "$1" &
readonly heartbeat_pid="$!"

status=0
wait "${command_pid}" || status="$?"
kill "${heartbeat_pid}" 2>/dev/null || true
wait "${heartbeat_pid}" 2>/dev/null || true
exit "${status}"
