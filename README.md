# carve

[Release website](https://mboworks.github.io/carve/)

Carve `compile_commands.json` out of Bazel build graphs for clangd-style
tooling, licensed under [Apache-2.0](LICENSE). Carve is a clean-slate C++23
replacement for the
[maintained `helly25` fork of Hedron's bazel-compile-commands-extractor](https://github.com/helly25/bazel-compile-commands-extractor).
(Note that the original Hedron repository is no longer maintained.)

[![Test](https://github.com/mboworks/carve/actions/workflows/main.yml/badge.svg)](https://github.com/mboworks/carve/actions/workflows/main.yml)
[Coverage report](https://mboworks.github.io/carve/coverage/)

## Status

Working, pre-release. All three layers are implemented and tested - Layer A
(`carve refresh`), Layer B (`bazel run //:refresh`), and Layer C (the
`cc_carve_aspect` aspect emitting per-action shards) - along with the `refresh`,
`aggregate`, `shard`, and `prune` subcommands. Not yet published to the Bazel
Central Registry; the release tooling is in place. See
[CARVE_DESIGN.md](CARVE_DESIGN.md) for the architecture and
[docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for milestone status.

## What it does

1. Walks Bazel's action graph via `bazel aquery`.
2. Filters to C/C++/Objective-C/CUDA compile actions.
3. Resolves each action's header set in-process via clang's
   `DependencyScanningTool`.
4. De-Bazels each compile command so clangd can introspect it without
   Bazel-specific environment.
5. Writes an atomic `compile_commands.json` plus a persistent sidecar cache
   that skips re-scanning unchanged actions on re-refresh.

A working CDB does not require a full build; clangd resolves most headers
itself. Generated headers, however, must exist on disk for the scan to resolve
them - codegen-heavy targets may need a build first. Sub-second incremental
refresh on large monorepos is a Layer C (aspect) property: Layers A/B re-run
`bazel aquery` each time and so pay the graph-query cost regardless of edit
size. See [CARVE_DESIGN.md](CARVE_DESIGN.md) section 3.1.

## Usage

```bash
# Refresh the whole repo's compilation database (writes compile_commands.json to
# the workspace root). This is the carve_refresh rule (Layer B).
bazel run //:refresh

# Or drive the binary directly (Layer A), choosing targets/output on the CLI.
bazel run //:carve -- refresh --targets=//foo/... --output=compile_commands.json
```

In a consumer workspace, depend on carve in `MODULE.bazel` (once it is published
to the Bazel Central Registry):

```python
bazel_dep(name = "mboworks_carve", version = "0.1.0")

# The official LLVM static archives contain LLVM bitcode, so select the
# matching compiler as well as its C++ standard library.
bazel_dep(name = "toolchains_llvm", version = "1.9.0")
llvm = use_extension("@toolchains_llvm//toolchain/extensions:llvm.bzl", "llvm")
llvm.toolchain(
    name = "llvm_toolchain",
    llvm_version = "22.1.8",
    stdlib = {
        "": "builtin-libc++",
        "linux-aarch64": "stdc++",
        "linux-x86_64": "stdc++",
    },
)
use_repo(llvm, "llvm_toolchain")
register_toolchains("@llvm_toolchain//:all")
```

Carve links LLVM's prebuilt dependency-scanning libraries. Copy
[`carve.bazelrc`](carve.bazelrc) into the consumer workspace and import it from
the workspace `.bazelrc` so Carve is compiled as C++23 with its required LLVM
link settings and warning policy:

```text
try-import %workspace%/carve.bazelrc
```

The fragment is part of every source archive. The consumer registers the
matching toolchain because `toolchains_llvm` 1.9.0 only permits its toolchain
extension in the root module. Bazel's `include()` likewise cannot load a
fragment from an external repository, so this stanza cannot live inside Carve.
The checked-in [`examples/bcr`](examples/bcr) module is the authoritative
consumer example used by both source-archive CI and the optional BCR
presubmit.

Then add the rule from a `BUILD` file:

```python
load("@mboworks_carve//rules:carve.bzl", "carve_refresh")

carve_refresh(name = "refresh", targets = ["//..."])
```

`carve_refresh` is a **`bazel run`** target, not a build artifact: carve invokes
`bazel aquery`, and spawning bazel inside a build action is the nested-bazel
trap. For huge repos there is also Layer C - `cc_carve_aspect` +
`carve_aspect_refresh` (`rules/cc_carve_aspect.bzl`, `rules/carve.bzl`) schedule
one individually-cacheable shard per compile action and aggregate them.

## Build requirements

- Bazel 9.1+
- Clang 22.x (LLVM 22.1.8); root development uses
  [toolchains_llvm](https://github.com/bazel-contrib/toolchains_llvm) 1.9.0,
  while `scan_deps` downloads and links the matching static Clang/LLVM archives
- A consumer toolchain using LLVM 22.1.8 with libstdc++ on Linux or libc++ on
  macOS, matching the official LLVM distributions
- Apple Silicon / x86\_64 Linux supported; Windows planned

## License

Apache-2.0. See [LICENSE](LICENSE).

## Release website

Release notes use `.github/release-notes.md.template`, rendered by
`tools/release_notes.sh TAG`, to link to that tag's versioned website and related
release resources. The existing changelog and installation notes remain included.

The [website](https://mboworks.github.io/carve/) forwards to the latest published
stable release at `site/tag/<tag>/`, preserving the exact Git tag name.
Each release keeps its converted HTML, images, and configured files. Retrying
publication leaves an existing snapshot unchanged; a different commit cannot
replace it. Older versions remain directly accessible.

[`release-site.json`](release-site.json) defines the layout. Source names are
relative to the repository root; destinations are relative to that release's
site directory. For example:

```json
{
  "pages": {
    "README.md": "index.html",
    "docs/guide.md": "guide/index.html"
  },
  "files": {
    "schema/example.json": "schema/v1.json"
  },
  "links": [
    {
      "label": "Release",
      "href": "https://github.com/{owner}/{repo}/releases/tag/{tag}"
    }
  ]
}
```

Use existing source files in the actual configuration. `pages` converts Markdown;
optional `files` copies other files unchanged. `README.md` must map to `index.html`.
The generated `documents.html`, `release.json`, `release-site.json`, and `assets/`
paths are reserved. Destination paths cannot have hidden components (names starting
with a dot), because the Pages artifact uploader excludes them. Hidden source
paths remain valid; for example, `.github/workflows/README.md` maps to
`workflows/index.html`.
Navigation links support `{owner}`, `{repo}`, `{tag}`, `{version}`, and `{commit}`.
`{version}` omits a leading `v` for compatibility with coverage report paths.
By default, the configuration and content come from the release tag. Every linked
local Markdown page (including directory README links) must have a `pages` mapping.
Publication fails for an omitted mapping, a missing generated file, or a broken
anchor within the snapshot. Links to configured pages follow their destination
mappings; other local source links use the exact release commit. Embedded images are copied, including remote badges. Markdown
conversion uses the [GitHub Markdown API](https://docs.github.com/en/rest/markdown/markdown)
at publication time; browsing the result requires no Markdown renderer or CDN.

After the Release workflow succeeds, `Publish release site` retains the snapshot
on `coverage-pages` and deploys the complete Pages tree. Coverage and site
publication share a concurrency group to preserve both trees. GitHub's latest
stable release selects the root redirect; backfilling an older release does not
make it latest. The workflow can also be dispatched with a published tag to retry
publication. Enable GitHub Pages with
**GitHub Actions** as its source, and set the repository's About website to
`https://mboworks.github.io/carve/`.

### Backfill a historical release

No new release or tag change is needed. Manually dispatch `Publish release site`
with `tag` set to the historical release and `config_path` set to a tracked JSON
file on `main`. Leave `config_path` empty to use a configuration already in the tag.
For example, after selecting a compatible configuration and an existing tag:

```sh
gh workflow run pages.yml --repo mboworks/carve --ref main \
  -f tag="$RELEASE_TAG" -f config_path=release-site.json
```

The override controls only publication layout; all Markdown and copied files come
from the selected tag. Each new snapshot retains the exact configuration as
`release-site.json`, with its SHA-256, origin, and source commit in `release.json`.
A configuration can serve several historical tags when its sources exist in each.
For another layout, commit another configuration and select its path. Missing
sources or links fail publication instead of using newer content. Retrying a
published tag preserves its original HTML and configuration.

Local regression tests: `python3 -m unittest discover -s tools -p release_site_test.py`.
CI also converts the configured documentation and checks the generated links in
a disposable runner directory. It never commits, retains, or deploys that preview.

Release coverage links select `https://mboworks.github.io/carve/coverage/tag/<version>/`,
matching the coverage publisher rather than the moving main-branch report.
