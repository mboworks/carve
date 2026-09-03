#!/usr/bin/env python3
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
"""Reject ASSERT_THAT(StatusOr, IsOk()) followed by dereferencing that value."""

import re
import sys
from pathlib import Path

_ASSERT = re.compile(r"\bASSERT_THAT\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*IsOk\(\)\s*\)")
_WINDOW = 8


def check(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    problems = []
    for index, line in enumerate(lines):
        match = _ASSERT.search(line)
        if not match:
            continue
        name = re.escape(match.group(1))
        following = "\n".join(lines[index + 1 : index + 1 + _WINDOW])
        if re.search(rf"\*{name}\b|\b{name}->", following):
            problems.append(
                f"{path}:{index + 1}: bind the StatusOr value with MBO_ASSERT_OK_AND_ASSIGN "
                "or match it with IsOkAndHolds"
            )
    return problems


def main(paths: list[str]) -> int:
    problems = [problem for raw in paths if raw.endswith("_test.cc") for problem in check(Path(raw))]
    for problem in problems:
        print(problem, file=sys.stderr)
    return int(bool(problems))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
