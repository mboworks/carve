#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) M. Boerger, the MBO Works authors
# SPDX-License-Identifier: Apache-2.0

import unittest

from tools import coverage_data


class CoverageDataTest(unittest.TestCase):
    def test_preserves_complete_file_coverage(self):
        result = coverage_data.parse_lcov(
            """TN:
SF:carve/example.cc
FN:3,8,carve::Covered()
FN:10,carve::Missing()
FNDA:2,carve::Covered()
FNDA:0,carve::Missing()
DA:3,2,checksum
DA:4,0
BRDA:4,0,0,2
BRDA:4,0,1,-
end_of_record
"""
        )

        self.assertEqual(
            result,
            {
                "schema": 1,
                "totals": {
                    "lines": {"found": 2, "hit": 1},
                    "functions": {"found": 2, "hit": 1},
                    "branches": {"found": 2, "hit": 1},
                },
                "files": [
                    {
                        "path": "carve/example.cc",
                        "lines": [
                            {"line": 3, "execution_count": 2, "checksum": "checksum"},
                            {"line": 4, "execution_count": 0},
                        ],
                        "functions": [
                            {
                                "name": "carve::Covered()",
                                "start_line": 3,
                                "end_line": 8,
                                "execution_count": 2,
                            },
                            {"name": "carve::Missing()", "start_line": 10, "execution_count": 0},
                        ],
                        "branches": [
                            {"line": 4, "block": "0", "branch": "0", "taken": 2},
                            {"line": 4, "block": "0", "branch": "1", "taken": None},
                        ],
                    }
                ],
            },
        )

    def test_rejects_unterminated_record(self):
        with self.assertRaisesRegex(ValueError, "missing end_of_record"):
            coverage_data.parse_lcov("SF:carve/example.cc\nDA:1,1\n")


if __name__ == "__main__":
    unittest.main()
