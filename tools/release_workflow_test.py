#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) M. Boerger, the MBO Works authors
# SPDX-License-Identifier: Apache-2.0
"""Release and deferred BCR publication policy tests."""

import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReleaseWorkflowTest(unittest.TestCase):
    def test_tag_release_validates_a_draft_before_stable_publication(self):
        workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")

        draft = workflow.index('gh release create "${TAG}" --draft')
        upload = workflow.index('gh release upload "${TAG}"')
        verify = workflow.index("Verify uploaded archive")
        publish = workflow.index('gh release edit "${TAG}" --draft=false')

        self.assertLess(draft, upload)
        self.assertLess(upload, verify)
        self.assertLess(verify, publish)
        self.assertIn('tools/release_archive_test.sh "carve-${TAG}.tar.gz"', workflow)
        self.assertIn("sha256sum", workflow)
        self.assertNotIn("release_ruleset.yaml", workflow)
        self.assertNotIn("prerelease: true", workflow)
        self.assertNotIn("publish.yaml", workflow)
        self.assertNotIn("BCR_PUBLISH_TOKEN", workflow)

    def test_release_tags_do_not_run_whole_repository_trunk(self):
        workflow = (ROOT / ".github/workflows/main.yml").read_text(encoding="utf-8")

        self.assertIn("if: github.ref_type != 'tag'", workflow)
        self.assertIn("Accept policy-checked release tag", workflow)
        self.assertIn("if: github.ref_type == 'tag'", workflow)

    def test_packaging_is_reproducible_and_does_not_modify_checkout(self):
        before = subprocess.check_output(
            ["git", "status", "--porcelain=v1"], cwd=ROOT, text=True
        )
        archives = []
        with tempfile.TemporaryDirectory() as output:
            for directory in ("first", "second"):
                destination = Path(output) / directory
                destination.mkdir()
                environment = os.environ.copy()
                environment["CARVE_RELEASE_OUTPUT_DIR"] = str(destination)
                environment["CARVE_RELEASE_VERSION"] = "0.1.1"
                subprocess.run(
                    [str(ROOT / ".github/workflows/release_prep.sh")],
                    cwd=ROOT,
                    env=environment,
                    stdout=subprocess.DEVNULL,
                    check=True,
                )
                archives.append((destination / "carve-0.1.1.tar.gz").read_bytes())

            self.assertEqual(archives[0], archives[1])
            with tarfile.open(Path(output) / "first/carve-0.1.1.tar.gz") as archive:
                names = set(archive.getnames())
                self.assertIn("carve-0.1.1/VERSION", names)
                self.assertIn("carve-0.1.1/examples/bcr/MODULE.bazel", names)
                self.assertNotIn("carve-0.1.1/.github", names)
                module = archive.extractfile("carve-0.1.1/MODULE.bazel")
                self.assertIsNotNone(module)
                self.assertIn(
                    b'# include("//bazelmod:dev.MODULE.bazel")', module.read()
                )

        after = subprocess.check_output(
            ["git", "status", "--porcelain=v1"], cwd=ROOT, text=True
        )
        self.assertEqual(before, after)

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
