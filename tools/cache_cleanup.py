#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) M. Boerger, the MBO Works authors
# SPDX-License-Identifier: Apache-2.0
"""Select oversized caches and superseded per-commit cache generations."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

MAX_CACHE_BYTES = 1_200_000_000


def expired_cache_ids(caches: Iterable[dict[str, Any]]) -> list[int]:
    caches = list(caches)
    families: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cache in caches:
        prefix, separator, suffix = cache["key"].rpartition("-")
        family = prefix if separator and len(suffix) == 40 else cache["key"]
        families[family].append(cache)
    expired = {
        cache["id"] for cache in caches if cache.get("sizeInBytes", 0) >= MAX_CACHE_BYTES
    }
    for family in sorted(families):
        entries = sorted(families[family], key=lambda item: item["createdAt"])
        expired.update(item["id"] for item in entries[:-1])
    return sorted(expired)


def main() -> int:
    caches = json.load(sys.stdin)
    if not isinstance(caches, list):
        raise ValueError("GitHub cache JSON must be an array")
    for cache_id in expired_cache_ids(caches):
        print(cache_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
