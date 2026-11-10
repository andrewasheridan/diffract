# 005. Compare HEAD with the git staging area in the commit-msg hook

Date: 2026-03-24
Status: Accepted

## Context

The `diffract-validate` hook runs at the `commit-msg` stage. git runs this stage
before it makes the new commit object. Thus `HEAD` is still the previous commit when
the hook runs.

The first version compared `HEAD~1` with `HEAD`, which is the change in the previous
commit. Thus the hook validated the API change of the *last commit*, not the *staged
change*. This gave incorrect results with no warning. For example, a developer removed
a public name, but the hook showed "feat (added)" from the previous commit. The
correct result was "feat! (removed)".

## Decision

If you use `--validate-msg-file` and give no BASE or HEAD refs, diffract compares
`HEAD` with the **git staging area**. `HEAD` is the last commit. The staging area is
the content of the new commit. This is the usual `commit-msg` hook context. These
functions do the comparison:

1. `git_utils.get_api_at_index()` writes the staged tree with `git write-tree`
   (through `repo.git`). This command keeps the tree object in the git object store.
   Then the function writes the tree to a directory with `git archive <tree-sha>` and
   calls `get_public_api()`.
2. `git_utils.has_python_changes_index()` uses `git diff --cached --name-only HEAD` to
   find staged changes to `.py` files.
3. `checker.check_staged()` is a new public function. It compares `HEAD` with the
   staging area.
4. `cli.main()` calls `check_staged()`, not `check()`, for `--validate-msg-file` with
   no refs.

The `DiffractResult` from `check_staged()` has the string `":staged"` as its
`head_ref`. This value shows that the result is not for a commit.

## Alternatives considered

**A `post-commit` hook:** This hook runs after git makes the commit, so `HEAD` is
correct. We rejected this method because a `post-commit` hook cannot stop a commit. It
only gives information.

**Use `git stash` to keep the staged changes:** This method gives a real commit SHA.
But `git stash` changes the repository, and it is not safe during a commit.

**Users give the refs:** `.pre-commit-hooks.yaml` then has
`entry: diffract HEAD :staged --validate-msg-file`. But `:staged` is not a valid git
ref. Also, git cannot archive the index with that syntax.

## Consequences

**Positive:**

- The hook now correctly finds the change in the commit that you make.
- `git write-tree` does not change the repository state. It writes a loose tree object
  to the git object store. It does not change refs, the working tree or `.git/index`.
- The `git` command obeys `GIT_INDEX_FILE`. Thus the hook reads the temporary index of
  `git commit -a` (see the correction in ADR 003).
- Other tools can call `check_staged()` as a public Python API, for example in
  pre-commit tools.

**Negative:**

- The `:staged` value in `DiffractResult.head_ref` is not a real git ref. If a tool
  gives this value to git, git fails. The code documents this behavior.
