# TODO

The detailed dependency ordering and completed milestones live in
[docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md). This file is the
short list of remaining work.

## First release

- [x] Author and validate the consumer `.bazelrc` fragment and BCR test module
  required to build Carve with the matching prebuilt LLVM toolchain.
- [x] Allow repository administrators to create signed release tags without
  weakening the existing update, deletion, signature, or non-fast-forward
  protections.
- [x] Prepare `0.1.1`: finalize the changelog and verify the module, changelog,
  test module, tag, archive, and BCR metadata use the same version.
- [ ] Create the signed `0.1.1` tag and validate the generated draft and source
  archive before the workflow publishes the immutable stable release.
- [ ] Dispatch `pages.yml` for `0.1.1` after publication and verify the root site
  redirects to the stable release documentation.

## Deferred enhancements

- [ ] Add a valid `BCR_PUBLISH_TOKEN`, dispatch `publish.yaml`, merge the
  generated registry pull request, and verify `mboworks_carve@0.1.1`.

- [ ] Make the emitted compilation database relocatable by rewriting it to
  workspace-relative paths and handling Bazel's external-repository links.
- [ ] Add NVCC-to-Clang flag translation and Emscripten driver handling.
- [ ] Add Windows support, including junction and command-line-length handling.
- [ ] Run the differential harness over a representative external-project
  corpus.
- [ ] Revisit fully hermetic macOS C++ runtimes if a concrete need justifies
  extending or forking the LLVM toolchain module.
