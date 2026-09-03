#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) M. Boerger, the MBO Works authors
# SPDX-License-Identifier: Apache-2.0
"""Select all but the newest GitHub Actions cache in each key family."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from collections.abc import Iterable
from typing import Any


def expired_cache_ids(caches: Iterable[dict[str, Any]]) -> list[int]:
    families: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cache in caches:
        prefix, separator, suffix = cache["key"].rpartition("-")
        family = prefix if separator and len(suffix) == 40 else cache["key"]
        families[family].append(cache)
    expired = []
    for family in sorted(families):
        entries = sorted(families[family], key=lambda item: item["createdAt"])
        expired.extend(item["id"] for item in entries[:-1])
    return expired


def main() -> int:
    caches = json.load(sys.stdin)
    if not isinstance(caches, list):
        raise ValueError("GitHub cache JSON must be an array")
    for cache_id in expired_cache_ids(caches):
        print(cache_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
