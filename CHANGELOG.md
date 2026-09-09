# Changelog

All notable changes to this project will be documented in this file. Format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning
follows [SemVer](https://semver.org/).

## [Unreleased]

## [0.1.1] - 2026-09-08

### Added

- Implement the `refresh`, `shard`, `aggregate`, and `prune` commands for
  producing and maintaining deterministic `compile_commands.json` databases.
- Provide Layer B's `carve_refresh` rule and Layer C's `cc_carve_aspect` and
  `carve_aspect_refresh` integration, including cacheable per-action shards.
- Extract compile actions from Bazel aquery protobufs, expand response files,
  remove Bazel-only flags, resolve Apple toolchain placeholders, and parse Make
  dependency files.
- Scan dependencies in-process through Clang, record source/header ownership,
  and incrementally rescan only stale or unresolved actions.
- Persist project-scoped action records and a deterministic header-to-owner
  index, with atomic writes, shard aggregation, and age-based pruning.
- Add source-release automation, a tested external-consumer module, BCR
  metadata for optional later publication, and retained versioned release and
  coverage websites with separately published website documentation.

### Changed

- Publish as the `mboworks_carve` Bazel module and use `mboworks_mbo` 0.14.0
  and `mboworks_proto` 1.2.2.
- Use `bazel-contrib/toolchains_llvm` 1.9.0 with LLVM 22.1.8 and matching
  prebuilt static Clang/LLVM archives instead of compiling LLVM in CI.
- Store compilation-database sources and cached headers execroot-relative to
  keep persisted data deterministic across hosts.
- Keep first-party warnings fatal while treating external headers and sources
  as code outside Carve's control.
- Create releases as mutable drafts, verify the attached source archive, and
  only then publish them directly as immutable stable releases.
- Build release archives without modifying the checkout and make repeated
  packaging byte-reproducible.
- Keep tag coverage CI while avoiding Trunk's unrelated whole-repository mode
  for commits that already passed the required merge gate.

### Quality

- Test all production modules with unit, integration, end-to-end, golden,
  archive-consumer, and differential checks on Linux x86-64 and Apple Silicon.
- Enforce clang-tidy, Trunk, pre-commit, ASan/LSan/UBSan, TSan, and Linux MSan
  in CI; LLVM-linked targets are excluded from sanitizer configurations.
- Enforce 95% line, function, and branch coverage overall and for every
  non-empty production category. At release preparation, reported coverage is
  98.54% lines, 98.90% functions, and 96.04% branches.
- Bound and separate Bazel action caches while leaving external repositories
  and the large LLVM distribution disposable.

### Known limitations

- The initial source release supports Linux x86-64 and Apple Silicon with the
  documented LLVM toolchain. Windows and macOS x86-64 are not supported.
- Compilation databases are tied to their Bazel execution root rather than
  being relocatable between workspace locations.
- NVCC and Emscripten command translation and broader external-project
  differential validation remain deferred.

## [0.1.0] - 2026-09-08

The signed tag was created, but its GitHub release was not published because
the original workflow uploaded assets after publishing an immutable release.
Version 0.1.1 supersedes this unpublished release.
