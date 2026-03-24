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

**Exit codes with `--exit-code`:**
- `0` — no API surface changes
- `1` — breaking change (public name removed)
- `2` — non-breaking API change (public name added)
- `3` — error (git or surface extraction failure)

**Example output:**

```
Detected: feat!  (breaking change)

Removed public names:
  sheridan.diffract.enums:
    - OldHelper

Suggested commit prefix: feat!:
```

```
Detected: fix

No public API changes detected.

Suggested commit prefix: fix:
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

### Validate commit messages with pre-commit

`diffract` ships a `commit-msg` hook that rejects commits whose conventional commit type doesn't match the detected API change — catching `fix:` when you actually removed a public name.

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/sheridan/diffract
    rev: v<VERSION>
    hooks:
      - id: diffract-validate
```

Non-conventional commit types (`docs:`, `chore:`, `test:`, etc.) are never blocked.

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

```yaml
- name: Check API classification
  run: diffract --exit-code --json
```

Fails the build if a breaking change is not flagged as `feat!` in the commit message.

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
