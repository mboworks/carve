# TODO

The detailed dependency ordering and completed milestones live in
[docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md). This file is the
short list of remaining work.

## First release

- [x] Author and validate the consumer `.bazelrc` fragment required to build
  carve and its source-built LLVM dependencies outside this repository.
- [ ] Add a valid `BCR_PUBLISH_TOKEN` with access to
  `mboworks/bazel-central-registry`.
- [x] Allow repository administrators to create signed release tags without
  weakening the existing update, deletion, signature, or non-fast-forward
  protections.
- [ ] Prepare `0.1.0`: finalize the changelog and verify the module, changelog,
  tag, archive, and BCR metadata all use the same version.
- [ ] Create the signed `0.1.0` tag and keep the GitHub release marked as a
  prerelease while the secondary BCR publication process is pending.
- [ ] Merge the generated BCR pull request, verify `mboworks_carve@0.1.0`, and
  then mark the GitHub release as final.

## Deferred enhancements

- [ ] Make the emitted compilation database relocatable by rewriting it to
  workspace-relative paths and handling Bazel's external-repository links.
- [ ] Add NVCC-to-Clang flag translation and Emscripten driver handling.
- [ ] Add Windows support, including junction and command-line-length handling.
- [ ] Run the differential harness over a representative external-project
  corpus.
- [ ] Revisit fully hermetic macOS C++ runtimes if a concrete need justifies
  extending or forking the LLVM toolchain module.
