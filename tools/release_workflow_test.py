#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) M. Boerger, the MBO Works authors
# SPDX-License-Identifier: Apache-2.0
"""Release and deferred BCR publication policy tests."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReleaseWorkflowTest(unittest.TestCase):
    def test_tag_release_is_provisional_and_does_not_publish_to_bcr(self):
        workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")

        self.assertIn("prerelease: true", workflow)
        self.assertNotIn("publish.yaml", workflow)
        self.assertNotIn("BCR_PUBLISH_TOKEN", workflow)

    def test_bcr_publication_is_manual_and_uses_the_selected_ref(self):
        workflow = (ROOT / ".github/workflows/publish.yaml").read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch: {}", workflow)
        self.assertIn("tag_name: ${{ inputs.tag_name || github.ref_name }}", workflow)

    def test_bcr_presubmit_uses_the_supported_consumer(self):
        presubmit = (ROOT / ".bcr/presubmit.yml").read_text(encoding="utf-8")

        self.assertIn("bcr_test_module:", presubmit)
        self.assertIn("module_path: examples/bcr", presubmit)
        self.assertIn("- 9.x", presubmit)
        self.assertNotIn("- 8.x", presubmit)
        self.assertNotIn("source-built LLVM", presubmit)

    def test_release_notes_do_not_claim_immediate_registry_availability(self):
        packager = (ROOT / ".github/workflows/release_prep.sh").read_text(encoding="utf-8")

        self.assertIn("BCR publication is an", packager)
        self.assertIn("independent later step", packager)
        self.assertIn("After \\`${BAZELMOD_NAME}@${TAG}\\` is available", packager)


if __name__ == "__main__":
    unittest.main()
