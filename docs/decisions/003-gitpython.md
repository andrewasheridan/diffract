# 003. Use gitpython for git operations

Date: 2026-03-23
Status: Accepted

## Context

diffract needs to perform three key git operations:
1. Open and inspect git repositories
2. Extract files at a given commit ref via `git archive`
3. Check whether any `.py` files changed between two refs

Two approaches were available: (a) the gitpython library, or (b) subprocess calls to the git CLI directly.

The automated dependency auditor rejected gitpython, citing: CVE history (4 CVEs 2022–2024), lack of Python 3.14 classifier, and maintenance-mode status. However, human review overrode this rejection after investigating each concern.

## Decision

Use gitpython (≥3.1) for git operations.

This decision was made after verifying that:
- All cited CVEs are patched in gitpython 3.1.46 (current version)
- The CVEs involved untrusted remote URL injection; diffract controls all git arguments — no untrusted input enters subprocess calls
- gitpython 3.1.46 imports and runs cleanly on Python 3.14.3 (tested in the project venv) despite missing classifiers
- Snyk health score: 94/100
- gitpython is already installed in the project venv
- gitpython's `Repo` object correctly normalises `GIT_DIR`, `GIT_INDEX_FILE`, and `GIT_WORK_TREE` environment variables set by git hooks — an important correctness property since diffract runs as a pre-push hook
- The subprocess approach would require manual environment-variable handling to be equally correct in hook contexts

## Alternatives Considered

**Subprocess + git CLI directly:** This avoids the dependency but requires careful handling of git environment variables (`GIT_DIR`, `GIT_INDEX_FILE`, `GIT_WORK_TREE`) when running as a git hook. gitpython's `Repo` object handles this normalization automatically, making it the more correct choice for this context.

## Consequences

**Positive:**
- Clean, idiomatic API for git operations
- Correct handling of git hook environment variables
- 94/100 Snyk health score; all known CVEs patched
- Avoids manual subprocess complexity

**Negative:**
- Adds a dependency with maintenance-mode upstream; security vigilance required on upgrades
- Upstream classifiers lag behind Python version support

**Mitigation:** All git arguments are hardcoded or come from trusted CLI inputs; never interpolated from untrusted sources. This eliminates the attack surface of the cited CVEs.
