# RULES.md

Code-style and structural rules for `mboworks/carve`. These mirror the MBO Works
house style (see sibling repos [mbo](https://github.com/mboworks/mbo) and
[bzl](https://github.com/mboworks/bzl)).

[STYLE_CPP.md](STYLE_CPP.md) is the detailed C++ style companion - the shared
MBO Works C++ conventions with rationale and examples (idioms, error handling,
output/`AbslStringify`, concurrency, protobuf, GoogleTest). This file is the
concise carve-specific rule set and structural conventions; STYLE_CPP.md expands
the C++ parts. Where they overlap they agree; STYLE_CPP.md has the detail.

[AGENTS.md](AGENTS.md) remains canonical for *process and agent* conventions
(commits, PRs, testing discipline, library priority) and references this file
for *code style*. [CARVE_DESIGN.md](CARVE_DESIGN.md) is canonical for
architecture. Where this file and the design disagree, the design wins and this
file is corrected.

## Licensing and headers

- Apache-2.0. Every Bazel, Starlark, C++, proto, and shell file starts with the
  SPDX header block (see [AGENTS.md](AGENTS.md#file-headers)). Markdown, JSON,
  and other comment-less formats are exempt.
- Unix text files: UTF-8, LF line endings, final newline, no trailing
  whitespace.

## C++

- C++23, clang 20.1+ (pinned at LLVM 22.1.8 via `toolchains_llvm` 1.9.0).
- Style: Google C++ with the deviations in [.clang-format](.clang-format);
  formatting is enforced, not negotiated.
- Compiler warnings for first-party C and C++ sources are enabled with `-Wall`,
  `-Wextra`, and `-Wpedantic` and treated as errors in target and host/tool
  configurations. Diagnostics from external headers and sources are suppressed;
  the shared MBO Works carve-outs cover external macros whose diagnostics are
  attributed to their first-party expansion site and deliberate partial
  designated initialization.
- Lints: [.clang-tidy](.clang-tidy) with `WarningsAsErrors: true`.
- No exceptions (`-fno-exceptions`); errors flow through `absl::Status`,
  `absl::StatusOr`, or `std::expected`.

### Layout and naming

- **One module per directory:** `carve/<module>/`, self-contained.
- **Namespaces:** `carve::<module>`. Internal-only code lives in
  `carve::<module>::<module>_internal` - never a bare `internal` namespace.
  Implementation detail may use a nested `detail` namespace.
- **Header guards:** `CARVE_<PATH>_<FILE>_` (path + filename, upper-snake,
  non-alphanumerics to `_`, trailing `_`). Example:
  `CARVE_COMMAND_DEBAZEL_H_`.
- **Macros:** prefix `CARVE_`. **Flags:** `--carve_<module>_*`.
- **Includes:** project headers (quoted, full repo-relative path) before
  external; keep IWYU pragmas in headers (`// IWYU pragma: keep`).
- **Files:** `<unit>.h` / `<unit>.cc`, test colocated as `<unit>_test.cc`.

### Bazel targets

- `cc_library` targets are suffixed `_cc` (e.g. `command_cc`).
- `cc_test` targets are suffixed `_test` and every direct test rule declares
  its scheduling `size` explicitly.
- Every `cc_library` has a direct dependency from a test in the same package;
  narrowly justified structural fixtures are recorded in the policy check's
  allowlist.
- Split `implementation_deps` (private, not propagated) from `deps` (public API
  surface).
- Package `default_visibility = ["//visibility:private"]`; widen explicitly per
  target only where a public boundary is intended.

## Protobuf

- Edition 2024 (`edition = "2024";`). `features.field_presence = EXPLICIT` only
  where set-vs-empty matters. See [CARVE_DESIGN.md](CARVE_DESIGN.md) section 4.4.

## Shell and Starlark

- Shell: follow [STYLE_SH.md](STYLE_SH.md), based on Google shell style;
  format with `shfmt` and lint with `shellcheck`.
- Starlark/Bazel: formatted and linted with `buildifier` (`--warnings=all`).

## Markdown

- Tables are vertically aligned: every column padded to a consistent width,
  pipes lined up, the `---` separator row matched, `:---`/`---:` markers kept.
  Enforced by `tools/align_md_tables.py` via the `align-md-tables` pre-commit
  hook; run `pre-commit run align-md-tables -a` (or the script directly) to fix.

## Tests

- GTest, colocated with the unit. Every change is covered by a committed test at
  the appropriate level - see the testing-discipline section in
  [AGENTS.md](AGENTS.md#testing-discipline). No exemption category.
- **Assert with matchers.** Use `EXPECT_THAT(actual, matcher)`, not GoogleTest
  comparison macros. Use the expressive matcher, not a hand-rolled
  predicate:
  - substring: `EXPECT_THAT(text, HasSubstr("x"))` - never
    `EXPECT_NE(text.find("x"), npos)`.
  - equality: `Eq(...)` / `StrEq(...)`; containers: `ElementsAre`, `IsEmpty`,
    `SizeIs`; structs: `Field(&T::member, matcher)` with `AllOf` for several.
  - status: the `mbo::testing` matchers (`mbo/testing/status.h`,
    `@mboworks_mbo//mbo/testing:status_cc`) `IsOk()`, `StatusIs(code)`,
    `IsOkAndHolds(value_matcher)`; `::absl_testing::` is disallowed (see STYLE_CPP.md
    "Status matchers"). Use `IsOkAndHolds(m)` rather than asserting `IsOk()` and then
    dereferencing (`*x`) to compare the value; bind reusable values with
    `MBO_ASSERT_OK_AND_ASSIGN`.
- Range-for loops use a named collection rather than an inline braced list.
- Use comparison `CHECK` macros (`CHECK_EQ`, `CHECK_NE`, and variants) so
  failures report both operands.
