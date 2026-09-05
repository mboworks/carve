#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) M. Boerger, the MBO Works authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for GitHub Actions cache retention selection."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cache_cleanup


class ExpiredCacheIdsTest(unittest.TestCase):
    def test_keeps_newest_cache_per_key_family(self):
        prefix = "bazel-ubuntu-module"
        caches = [
            {"id": 3, "key": f"{prefix}-{'c' * 40}", "createdAt": "2026-09-03T12:00:00Z"},
            {"id": 1, "key": f"{prefix}-{'a' * 40}", "createdAt": "2026-09-01T12:00:00Z"},
            {"id": 2, "key": f"{prefix}-{'b' * 40}", "createdAt": "2026-09-02T12:00:00Z"},
        ]
        self.assertEqual(cache_cleanup.expired_cache_ids(caches), [1, 2])

    def test_different_families_are_retained_independently(self):
        caches = [
            {"id": 1, "key": f"linux-{'a' * 40}", "createdAt": "2026-09-01T12:00:00Z"},
            {"id": 2, "key": f"macos-{'b' * 40}", "createdAt": "2026-09-01T12:00:00Z"},
        ]
        self.assertEqual(cache_cleanup.expired_cache_ids(caches), [])

    def test_non_sha_suffix_is_not_grouped(self):
        caches = [
            {"id": 1, "key": "manual-cache-one", "createdAt": "2026-09-01T12:00:00Z"},
            {"id": 2, "key": "manual-cache-two", "createdAt": "2026-09-02T12:00:00Z"},
        ]
        self.assertEqual(cache_cleanup.expired_cache_ids(caches), [])

    def test_oversized_cache_is_deleted_even_when_it_is_newest(self):
        caches = [
            {
                "id": 7,
                "key": "bazel-ubuntu-current",
                "createdAt": "2026-09-04T12:00:00Z",
                "sizeInBytes": 1_200_000_000,
            }
        ]
        self.assertEqual(cache_cleanup.expired_cache_ids(caches), [7])


if __name__ == "__main__":
    unittest.main()
