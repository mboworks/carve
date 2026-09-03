# Git and pull-request rules

These rules apply to humans and automation changing branches, pull requests,
CI, or releases in this repository. Repository protections are constraints,
not obstacles to bypass.

## Synchronization

Before starting or resuming pull-request work:

1. Fetch `main` and the remote pull-request head.
2. Inspect GitHub's current head, base, mergeability, and required checks.
3. Bring the branch current with `main` before final validation.
4. Push the synchronization immediately, then validate the pushed head.

Local validation is final evidence only when it covers the current pushed head
and current base. A later rebase, merge, conflict resolution, or edit invalidates
the affected result.

## Readiness and merging

A pull request is ready when it is approved, mergeable, current, and every
required check has succeeded. When instructed to merge a ready pull request,
merge that head without rebasing, retargeting, or otherwise invalidating its
successful checks.

Never substitute checks from another pull request or commit, even if their Git
trees happen to match. Treat GitHub as the source of truth for pull-request
state and refresh it after every push, merge, retarget, or completed CI run.

## Stacked changes

- State hard dependencies explicitly in the child pull request.
- Merge a ready base before its sole child; after GitHub retargets the child,
  require the new checks against `main`.
- Independent changes should use sibling branches from `main`, so their CI can
  run in parallel and their reviews remain separable.
- When several changes overlap or alter shared CI/build policy, re-evaluate
  their ordering after each merge and resynchronize only branches whose heads
  actually need to change.

## Conflicts and failures

Resolve conflicts on the pull request that is not ready, preserve compatible
changes from both sides, push the resolution, and rerun validation. Do not alter
a ready pull request merely to make another branch easier to merge.

For a failed check, inspect the failing log and reproduce the narrow failure
where practical. Fix the cause in a fresh signed-off commit; do not amend a
pushed commit or bypass the required check.

## Releases

Release tags are immutable, signed, numeric SemVer tags. Create them only from
a clean, current `main` with the repository release helper. Never move or reuse
a published tag.
