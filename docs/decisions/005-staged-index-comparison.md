# 005. Compare HEAD against git staging area in pre-commit hook

Date: 2026-03-24
Status: Accepted

## Context

The `diffract-validate` pre-commit hook runs at the `commit-msg` stage, which fires before the new commit object is created. Because of this, `HEAD` still points to the previous commit when the hook runs. The original implementation compared `HEAD~1 → HEAD` (the previous commit's changes), which meant the hook was validating the *last commit's* API change instead of the *current staged change*. This caused silent false results: a developer removing a public name would see the hook report "feat (added)" (from the previous commit) rather than "feat! (removed)".

## Decision

When `--validate-msg-file` is invoked without explicit BASE/HEAD refs (i.e., in the standard commit-msg hook context), diffract now compares `HEAD` (the last committed state) against the **git staging area** (what will become the new commit). This is implemented by:

1. `git_utils.get_api_at_index()` — materialises the staged tree via `repo.index.write_tree()` (which calls `git write-tree` and stores the result as a tree object in the git object store), then archives it with `git archive <tree-sha>` and calls `get_public_api()`
2. `git_utils.has_python_changes_index()` — uses `repo.head.commit.diff(index=True)` to detect staged `.py` changes
3. `checker.check_staged()` — new public function that orchestrates HEAD vs index comparison
4. `cli.main()` — routes `--validate-msg-file` (no explicit refs) to `check_staged()` instead of `check()`

The `DiffractResult` returned by `check_staged()` uses the sentinel string `":staged"` as `head_ref` to distinguish it from commit-based results.

## Alternatives Considered

**Post-commit hook:** Runs after the commit is created, so HEAD is correct. Rejected because `post-commit` hooks cannot fail a commit (they are informational only).

**Use `git stash` to snapshot staged changes:** Would provide a real commit SHA, but stashing has side effects and is unsafe in the middle of an active commit flow.

**Require users to pass explicit refs:** Would require `entry: diffract HEAD :staged --validate-msg-file` in `.pre-commit-hooks.yaml`, but `:staged` is not a valid git ref and git itself does not support archiving the index directly by that syntax.

## Consequences

**Positive:**
- The hook now correctly detects what is actually being committed
- `write_tree()` is read-safe: it writes a loose tree object to the git object store (no ref changes, no working-tree changes)
- `check_staged()` is also useful as a public Python API for programmatic pre-commit tooling

**Negative:**
- `write_tree()` has a subtle side effect: it flushes the in-memory index to `.git/index`. This is benign in normal commit-msg hook usage but could be surprising during a rebase or merge in progress
- The `:staged` sentinel in `DiffractResult.head_ref` is not a real git ref; downstream tools that try to pass it back to git will fail — this is documented in the code
