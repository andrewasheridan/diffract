# sheridan-diffract

**Detects how a Python package's public API changed between two git commits and classifies that change as a conventional commit type.**

Most semver tools trust the developer to classify their own changes correctly. `diffract` verifies that classification against the actual diff — catching the common case where someone writes `fix:` but actually removed a public function.

## How it works

1. Uses [sheridan-iceberg](https://github.com/andrewasheridan/iceberg) to extract the public API surface at two points in git history
2. Diffs those two surfaces to find what was added or removed
3. Maps the diff to a conventional commit classification:

| Change | Commit type |
|---|---|
| Public name removed | `feat!` (breaking) |
| Public name added | `feat` |
| Only internal/private changes | `refactor` |
| No changes detected | `fix` |

## Installation

```bash
pip install sheridan-diffract
```

## Usage

### CLI

```bash
# Compare the last two commits (default)
diffract

# Compare specific refs
diffract HEAD~3 HEAD

# Custom source directory (default: src/)
diffract --src lib/

# Emit JSON for CI consumption
diffract --json

# Exit non-zero if a breaking change is detected (for CI gates)
diffract --exit-code
```

**Exit codes:**
- `0` — no API surface changes, or `--exit-code` is not set
- `1` — breaking change (public name removed) with `--exit-code`, or a commit message that tells less than the API change with `--validate-msg-file`
- `2` — non-breaking API change (public name added) with `--exit-code`
- `3` — error: a usage error, a git, file or config error, or an unexpected error. For an unexpected error, diffract writes a short message with a link to the issue tracker.

**Example output:**

```
Detected: feat!  (breaking change)

Removed public names:
  sheridan.diffract:
    - OldHelper

Suggested commit prefix: feat!:
```

```
Detected: fix

No public API changes detected.

Suggested commit prefix: fix:
```

Scopes are passed through to the suggestion — if your commit message includes `(parser)`, the suggested prefix will too:

```
Suggested commit prefix: feat(parser):
```

### Python API

```python
from sheridan.diffract import check

result = check(base_ref="v1.2.0", head_ref="HEAD")
print(result.commit_type)   # e.g. "feat!"
print(result.summary)       # human-readable description
print(result.diff.removed)  # tuple of NameChange objects
print(result.diff.added)

# JSON-serialisable dict for CI output
import json
print(json.dumps(result.to_dict(), indent=2))
```

To compare `HEAD` against the **staging area** (what the next commit will contain) — the same comparison the pre-commit hook uses:

```python
from sheridan.diffract import check_staged

result = check_staged()
print(result.commit_type)  # reflects what is staged, not the last commit
```

### Validate commit messages with pre-commit or prek

`diffract` ships a `commit-msg` hook. The hook rejects a commit message only if the message tells less than the change to the public API:

- If the commit removes a public name, the message must have a `!` (for example `feat!:` or `fix!:`) or a `BREAKING CHANGE:` footer.
- If the commit adds a public name, the type must be `feat`, or the message must have a `!`.

The detected type is only an estimate from the public names. Thus the hook accepts a message that tells more than the detected type. For example, it accepts `fix:` for a change to a function body, and `feat!:` for a breaking change in behavior.

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/sheridan/diffract
    rev: v<VERSION>
    hooks:
      - id: diffract-validate
```
- the hook works with both [pre-commit](https://pre-commit.com) and [prek](https://github.com/j178/prek); install the `commit-msg` hook first with `pre-commit install --hook-type commit-msg` or `prek install --hook-type commit-msg`

The hook compares `HEAD` against the **git staging area** (not `HEAD~1 → HEAD`), so it correctly detects what is about to be committed rather than what was committed last. Explicit `BASE`/`HEAD` refs can be added to override this (see the GitHub Actions example below).

Scopes are preserved in all output — if you write `fix(parser): …`, the mismatch message will show `fix(parser):` as written and `feat(parser):` as the suggested replacement:

```
diffract: commit type mismatch
  written:  fix(parser):
  detected: feat(parser):
```

The hook checks only the `feat`, `fix` and `refactor` types. It never blocks other types (`docs:`, `chore:`, `test:` and so on).

### Configuration

If your source code isn't in `src/`, tell diffract once in a config file rather than repeating it on every command:

**`diffract.toml`** (takes precedence):
```toml
src = "python/src"
```

**`pyproject.toml`**:
```toml
[tool.diffract]
src = "python/src"
```

Priority: explicit `--src` flag → `diffract.toml` → `pyproject.toml` → default (`src/`).

### As a GitHub Actions check

Validate the **PR title** against detected API changes — the CI equivalent of the pre-commit hook.
The refs to diff are the PR branch HEAD versus the target branch HEAD:

```yaml
# .github/workflows/diffract.yml
name: diffract

on:
  pull_request:
    types: [opened, synchronize, reopened, edited]  # 'edited' catches title-only changes

jobs:
  api-change-check:
    name: Validate PR title against API changes
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # required to access both commit SHAs

      - name: Install diffract
        run: pip install sheridan-diffract

      - name: Validate PR title type matches API change
        env:
          PR_TITLE: ${{ github.event.pull_request.title }}
        run: |
          printf '%s' "$PR_TITLE" > /tmp/pr-title.txt
          diffract \
            ${{ github.event.pull_request.base.sha }} \
            ${{ github.event.pull_request.head.sha }} \
            --validate-msg-file /tmp/pr-title.txt
```

- `base.sha` — HEAD of the target branch (e.g. `main`) at the time of the PR event
- `head.sha` — HEAD of the PR branch
- Non-conventional title prefixes (`docs:`, `chore:`, `test:`, etc.) are never blocked
- Scopes are passed through: a title of `feat(parser): …` will suggest `feat(parser):` on mismatch

## What it does not do

- `diffract` has **no AST logic of its own**. It delegates all API surface extraction to `sheridan-iceberg`.
- It compares public names only (additions and removals). **Signature changes** (argument renames, return type changes) are not currently detected — iceberg returns name lists, not signatures.
- It does not modify commits or rewrite history. It only reports.

## Development

```bash
task install        # install all dependencies
task check          # lint + format + typecheck + tests (must all pass)
task test           # pytest with coverage (≥90% required)
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow.
