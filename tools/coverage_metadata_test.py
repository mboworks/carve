#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) M. Boerger, the MBO Works authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for coverage report metadata."""

import unittest

from tools import coverage_metadata


class CoverageMetadataTest(unittest.TestCase):
    def test_metadata_carries_identity_and_overall_measurements(self):
        overall = {"lines": {"covered": 9, "total": 10, "percent": 90.0}}
        source = {
            "created_at": "2026-09-03T10:00:00Z",
            "started_at": "2026-09-03T10:01:00Z",
            "completed_at": "2026-09-03T10:02:00Z",
            "run_id": 42,
            "run_attempt": 2,
            "head_sha": "abc123",
        }
        self.assertEqual(
            coverage_metadata.report_metadata({"measurements": {"overall": overall}}, "pr/79", source),
            {"schema": 1, "target": "pr/79", "source": source, "coverage": overall},
        )


if __name__ == "__main__":
    unittest.main()
