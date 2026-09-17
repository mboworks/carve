# Infrastructure and publishing

Adapted from [proto PR 100](https://github.com/mboworks/proto/pull/100) and xff PRs 835–848,
excluding 841. Developer helpers require Python 3.13+; the published tool remains C++.

## Local lint

Build the generated and external headers, then generate the database with
`bazel run //:refresh_compile_commands`. Run `python3 tools/clang_tidy.py --clang-tidy PATH`
with the matching hermetic LLVM binary. The default is `max(1, min(2, CPUs - 1))` workers;
`--jobs N` overrides it. CI explicitly selects its runner CPU count. This is a worker bound,
not an OS memory quota, and separate invocations do not share a global limit.

Completion is reported per translation unit. Interruptions terminate active processes and prevent
queued tasks from launching. First-party selection, header filters, and findings remain enforcing.
Carve has no pre-commit clang-tidy wrapper that could multiply pools through filename batching.

## Caches and scheduling

The shared actions restore compiled outputs with OS, architecture, configuration, dependency,
run, and attempt isolation. Only main saves fresh generations; PRs and numeric tags restore.
Legacy main cache prefixes provide migration fallback. Extracted LLVM and repository downloads
are not uploaded. The existing Linux/macOS matrix and ASan/UBSan, TSan, and MSan jobs remain.

Stop Bazel and trim synchronously before saving: largest files first, oldest first at equal size.
Start at 600,000,000 uncompressed bytes and strictly below 700,000,000 compressed bytes per entry.
These are conservative starting limits, not measurements of Carve's optimal sanitizer capacities.
Review one-day cache-metric artifacts, final repository inventory, and Bazel disk-cache hits before
raising configuration-specific budgets. The report's 10 GB value is a planning budget.

Retire old main generations only after the exact usable replacement appears in the inventory.
Missing, empty, oversized, equal-age, or newer entries do not authorize retirement. Trusted main
maintenance handles closed-PR/tag caches, superseded generations, and oversized entries. Inventory
failures defer immediate retirement.

Coverage runs alongside lint, while every job remains required by the final gate. The sole coverage
invocation writes `coverage-preparation.json.gz`, including repository fetches, Starlark repository
functions, Starlark builtins, and fetch events. Main, PR, and release-tag Test runs retain the
`coverage-preparation-profile` artifact for seven days, even on failure. Later Bazel commands do
not overwrite it. Compare preparation with action time and cache hits before optimizing downloads.

## Coverage and releases

The trusted publisher fetches main's complete first-parent history and tags, then refreshes retained
metadata against paginated merged PRs. Main stays first; PRs and releases interleave by merge/tag
commit position, newest first, with releases before PRs at the same commit. Unpositioned reports
follow by workflow creation time. Report replacement freshness remains independent of display
ordering. Existing detailed LCOV and complete coverage JSON remain available.

Both complete-site publishers decorate only their staged deployment copies with shared favicons.
Retained release snapshots stay unchanged. The README uses the shared 64-pixel MBO Works logo.
Release archives fix entry timestamps to the source commit so retries are byte-identical even
across clock ticks. Keep the existing draft/upload/digest-verification/stable-publication sequence,
numeric immutable tags, and independently dispatched BCR publication. Development advances to 0.1.2
to satisfy the existing post-release version invariant; dependency and toolchain pins do not change.

## Rules and validation

`AGENTS.md` owns contributor obligations, `GIT_RULES.md` owns Git/PR operations, and `STYLE_CPP.md`
and `STYLE_SH.md` retain Carve's language and testing conventions. The style guide now describes
clang-tidy as the enforcing gate it already is. The design's old one-helper estimate is explicitly
updated to describe the existing developer infrastructure without adding runtime Python.

Run `bazel build //...`, `bazel test //...`, `python3 -m unittest discover -s tools -p '*_test.py'`,
and `pre-commit run --all-files`. CI validates the sanitizer matrix and generated site links.
