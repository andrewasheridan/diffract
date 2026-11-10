# 003. Use gitpython for git operations

Date: 2026-03-23
Status: Accepted

## Context

diffract must do three git operations:

1. Open and examine git repositories.
2. Get the files at a commit ref with `git archive`.
3. Find whether `.py` files changed between two refs.

There were two possible methods:

- the gitpython library
- subprocess calls to the git CLI

The automated dependency auditor rejected gitpython for these reasons:

- gitpython had 4 CVEs from 2022 to 2024.
- gitpython has no Python 3.14 classifier.
- gitpython is in maintenance mode.

A person examined each reason and overrode the rejection.

## Decision

Use gitpython (3.1 or later) for git operations.

The decision is based on these facts:

- gitpython 3.1.46 (the current version) has a fix for each of the CVEs.
- The CVEs are about remote URLs from untrusted sources. diffract sets all the git
  arguments. No untrusted input goes into a subprocess call.
- We tested gitpython 3.1.46 on Python 3.14.3 in the project environment. It imports
  and runs correctly, although it has no classifier for Python 3.14.
- The Snyk health score of gitpython is 94/100.
- gitpython was already installed in the project environment.
- The `Repo` object of gitpython reads the `GIT_DIR` and `GIT_WORK_TREE` environment
  variables. git sets these variables for hooks.
- With the subprocess method, diffract must read these environment variables itself
  to be equally correct in hooks.

## Alternatives considered

**Subprocess calls to the git CLI:** This method needs no dependency. But in a git hook,
diffract must then read the git environment variables (`GIT_DIR`, `GIT_INDEX_FILE` and
`GIT_WORK_TREE`) itself. The `Repo` object of gitpython does this automatically. Thus
gitpython is the more correct choice for hooks.

## Correction: `GIT_INDEX_FILE`

Date: 2026-11-10

The first version of this ADR said that gitpython reads `GIT_INDEX_FILE`. That is not
correct for `IndexFile` (`repo.index`). `IndexFile` always reads `.git/index`, and
`IndexFile.write_tree()` also writes `.git/index`.

For `git commit -a` and `git commit <paths>`, git gives the hooks a temporary index in
`GIT_INDEX_FILE`. Thus `repo.index` showed the old staged content to the `commit-msg`
hook, not the content of the commit (issue #27).

diffract does not use `repo.index`. It reads the staging area with the `git` command
through `repo.git`, which obeys `GIT_INDEX_FILE`:

- `git write-tree` gets the tree of the staging area.
- `git diff --cached` finds the changed files.

## Consequences

**Positive:**

- gitpython has a clear API for git operations.
- diffract reads `GIT_DIR` and `GIT_WORK_TREE` correctly in git hooks.
- gitpython has a Snyk health score of 94/100, and all the known CVEs have a fix.
- diffract does not have to manage subprocess calls itself.

**Negative:**

- diffract depends on a package in maintenance mode. Examine each new version of
  gitpython for security problems before you use it.
- The classifiers of gitpython show new Python versions later than gitpython
  supports them.

**Mitigation:** All the git arguments are in the code or come from trusted CLI input.
diffract never puts untrusted text into a git argument. Thus the cited CVEs cannot
attack diffract.
