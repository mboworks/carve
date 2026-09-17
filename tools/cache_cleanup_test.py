#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) M. Boerger, the MBO Works authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for cache_cleanup.py."""

from __future__ import annotations

import unittest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import cache_cleanup


class CacheCleanupTest(unittest.TestCase):

  def test_selects_entries_at_or_above_limit(self):
    self.assertEqual(
        cache_cleanup.oversized_cache_ids(
            [
                {"id": 1, "sizeInBytes": cache_cleanup.MAX_CACHE_BYTES - 1},
                {"id": 2, "sizeInBytes": cache_cleanup.MAX_CACHE_BYTES},
                {"id": 3, "sizeInBytes": cache_cleanup.MAX_CACHE_BYTES + 1},
            ]
        ),
        [2, 3],
    )

  def test_empty_inventory_needs_no_cleanup(self):
    self.assertEqual(cache_cleanup.oversized_cache_ids([]), [])

  def test_closed_prs_and_tags_are_removed_before_other_cleanup(self):
    caches = [
        {"id": 1, "ref": "refs/heads/main", "sizeInBytes": 1, "key": "trunk"},
        {"id": 2, "ref": "refs/pull/839/merge", "sizeInBytes": 1, "key": "trunk"},
        {"id": 3, "ref": "refs/pull/840/merge", "sizeInBytes": 1, "key": "trunk"},
        {"id": 4, "ref": "refs/tags/v0.5.0", "sizeInBytes": 1, "key": "release"},
        {"id": 5, "ref": "refs/heads/refs/tags/v0.4.0", "sizeInBytes": 1, "key": "release"},
        {"id": 6, "ref": "refs/heads/main", "sizeInBytes": cache_cleanup.MAX_CACHE_BYTES, "key": "old"},
    ]
    self.assertEqual(cache_cleanup.obsolete_cache_ids(caches, {839}), [2, 4, 5, 6])

  def test_retains_newest_usable_generation_per_configuration_and_ref(self):
    def entry(number, namespace="Linux-X64-default", ref="refs/heads/main", size=10):
      return {"id": number, "ref": ref, "sizeInBytes": size,
              "createdAt": f"2026-09-{number:02d}T00:00:00Z",
              "key": f"bazel-actions-v2-{namespace}-{'a' * 64}-{number}-1"}
    caches = [entry(1), entry(2), entry(3, size=cache_cleanup.MAX_CACHE_BYTES),
              entry(4, "macOS-ARM64-default"), entry(5, "Linux-X64-asan"),
              entry(6, ref="refs/pull/840/merge")]
    # A newer rejected upload must not cause the last usable main generation to be deleted.
    self.assertEqual(cache_cleanup.obsolete_cache_ids(caches, set()), [1, 3])

  def test_empty_generation_does_not_displace_previous_usable_cache(self):
    old = {"id": 1, "ref": "refs/heads/main", "sizeInBytes": 10,
           "createdAt": "2026-09-01T00:00:00Z",
           "key": f"bazel-actions-v2-Linux-X64-coverage-{'a' * 64}-1-1"}
    empty = dict(old, id=2, sizeInBytes=0, createdAt="2026-09-02T00:00:00Z",
                 key=f"bazel-actions-v2-Linux-X64-coverage-{'a' * 64}-2-1")
    self.assertEqual(cache_cleanup.obsolete_cache_ids([old, empty], set()), [])

  def test_immediate_retirement_is_scoped_and_preserves_newer_uploads(self):
    def entry(number, namespace="Linux-X64-asan", ref="refs/heads/main", size=10):
      return {"id": number, "ref": ref, "sizeInBytes": size,
              "createdAt": f"2026-09-{number:02d}T00:00:00Z",
              "key": f"bazel-actions-v2-{namespace}-{'a' * 64}-{number}-1"}
    caches = [entry(1), entry(2), entry(3), entry(4, "Linux-X64-tsan"),
              entry(5, "macOS-ARM64-asan"), entry(6, ref="refs/pull/843/merge")]
    self.assertEqual(cache_cleanup.replaced_cache_ids(caches, caches[1]["key"]), [1])
    self.assertEqual(cache_cleanup.replaced_cache_ids(caches, "missing"), [])
    self.assertEqual(cache_cleanup.replaced_cache_ids(caches, caches[5]["key"]), [])
    for size in (0, 1_000_000_001):
      with self.subTest(size=size):
        caches[1]["sizeInBytes"] = size
        self.assertEqual(cache_cleanup.replaced_cache_ids(caches, caches[1]["key"]), [])

  def test_retirement_waits_for_inventory_and_preserves_equal_timestamps(self):
    old = {"id": 1, "ref": "refs/heads/main", "sizeInBytes": 100,
           "createdAt": "2026-09-01T00:00:00Z",
           "key": f"bazel-actions-v2-Linux-X64-coverage-{'a' * 64}-1-1"}
    new = dict(old, id=2, sizeInBytes=600_000_000, createdAt="2026-09-02T00:00:00Z",
               key=f"bazel-actions-v2-Linux-X64-coverage-{'b' * 64}-2-1")
    self.assertEqual(cache_cleanup.replaced_cache_ids([old], new["key"]), [])
    self.assertEqual(cache_cleanup.replaced_cache_ids([old, new], new["key"]), [1])
    old["createdAt"] = new["createdAt"]
    self.assertEqual(cache_cleanup.replaced_cache_ids([old, new], new["key"]), [])

  def test_cache_budget_is_unchanged_and_upload_bound_is_lower(self):
    import bazel_cache
    self.assertEqual(cache_cleanup.MAX_CACHE_BYTES, 700_000_000)
    self.assertLess(bazel_cache.MAX_BYTES, cache_cleanup.MAX_CACHE_BYTES)


class WorkflowCachePolicyTest(unittest.TestCase):
    def test_matrix_isolated_caches_and_coverage_gate(self):
        root = Path(__file__).parents[1]
        workflow = (root / ".github/workflows/main.yml").read_text()
        for config in ("clang-tidy", "test", "asan", "tsan", "msan", "coverage"):
            self.assertIn(f"namespace: {config}", workflow)
        self.assertIn("os: [ubuntu-latest, macos-latest]", workflow)
        self.assertIn("--config=asan --config=ubsan", workflow)
        coverage = workflow.split("  coverage:\n")[1].split("  done:\n")[0]
        self.assertNotIn("    needs:", coverage)
        self.assertIn("--profile=", coverage)
        self.assertIn("retention-days: 7", coverage)
        self.assertIn("if: always()", coverage)
        self.assertIn("needs: [release-site-tests, trunk, pre-commit, clang-tidy, test, asan, tsan, msan, coverage]", workflow)
        for setting in ("bazelisk-cache: false", "disk-cache: false", "external-cache: false", "repository-cache: false"):
            self.assertEqual(workflow.count(setting), 6)
        self.assertNotIn("--experimental_disk_cache_gc_max_size", workflow)
        self.assertNotIn("--experimental_disk_cache_gc_max_size", (root / ".bazelrc").read_text())
        self.assertIn("cancel-in-progress: ${{ github.event_name == 'pull_request' }}", workflow)


if __name__ == "__main__":
    unittest.main()
