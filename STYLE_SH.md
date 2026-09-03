# Shell style

Follow the [Google Shell Style Guide](https://google.github.io/styleguide/shellguide.html)
unless this document or repository tooling says otherwise.

## Tooling

- Use Bash for repository scripts. Executable scripts start with
  `#!/usr/bin/env bash`, followed by the repository licence header.
- Use `set -euo pipefail`, quote expansions unless splitting is intentional,
  and make function variables `local`.
- Format with `shfmt -bn -ci -i=2 -w` and lint with `shellcheck`. Explain any
  necessary local suppression at the suppressed line.

## Functions and effects

- Return computed values on standard output and capture them; do not mutate a
  caller variable with `eval`, `printf -v`, or a global variable.
- Send diagnostics to standard error.
- A function whose purpose is an external effect may perform that named effect,
  but changes to directories, shell options, and traps stay local.

## Tests and temporary files

- Shell behavior requires a committed test just like C++ behavior.
- Prefer the existing C++ end-to-end harness when testing Carve itself. Adopt
  `mboworks_bashtest` only when the behavior is genuinely shell-specific.
- Put test files under the test-owned temporary directory. Do not add cleanup
  traps or broad recursive deletion for Bazel-managed scratch space.

## Portability

- Target the Bash available on supported Linux and macOS CI runners.
- Resolve Bazel runfiles through `TEST_SRCDIR` and `TEST_WORKSPACE`.
- Prefer `[[ ... ]]`, arithmetic `(( ... ))`, and arrays over legacy tests and
  stringly argument assembly.
- Use lower-case names for local variables and functions. Preserve environment
  and runfile variable names.
