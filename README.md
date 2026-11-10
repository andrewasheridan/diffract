# sheridan-diffract

**diffract finds how the public API of a Python package changed between two git commits. It gives the Conventional Commit type for that change.**

Most semver tools accept the commit type that the developer writes. `diffract` compares that type with the real change to the API. For example, it finds a commit with the type `fix:` that removed a public function.

diffract supports only Python 3.14 and later.

## How it works

1. diffract uses [sheridan-iceberg](https://github.com/andrewasheridan/iceberg) to get the public API at two points in the git history.
2. It compares the two APIs to find the names that were added or removed.
3. It gives a Conventional Commit type for the change:

| Change | Commit type |
|---|---|
| A public name was removed | `feat!` (breaking) |
| A public name was added | `feat` |
| Only internal or private changes in the source directory | `refactor` |
| No change | `fix` |

diffract counts a code change only in the `.py` and `.pyi` files in the source directory
(`src` by default). A change only to a `.py` or `.pyi` file in `tests/`, `scripts/` or
`docs/` gives `fix`, not `refactor`.

## Installation

```bash
pip install sheridan-diffract
```

## Usage

### CLI

```bash
# Compare the last two commits (default)
diffract

# Compare specified refs
diffract HEAD~3 HEAD

# Use a different source directory (default: src/)
diffract --src lib/

# Write JSON for CI
diffract --json

# Exit with a code that is not zero if the change is breaking (for CI gates)
diffract --exit-code
```

You can also run diffract as a module: `python -m sheridan.diffract`. The module accepts the same arguments.

**Exit codes:**

- `0`: no change to the public API, or `--exit-code` is not set.
- `1`: with `--exit-code`, a breaking change (a public name was removed). With `--validate-msg-file`, a commit message that tells less than the API change.
- `2`: with `--exit-code`, a change that is not breaking (a public name was added).
- `3`: an error. This can be a usage error, a git, file or configuration error, or an unexpected error. For an unexpected error, diffract writes a short message with a link to the issue tracker.

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

### Python API

```python
from sheridan.diffract import check

result = check(base_ref="v1.2.0", head_ref="HEAD")
print(result.commit_type)   # for example "feat!"
print(result.summary)       # a description for people
print(result.diff.removed)  # a tuple of NameChange objects
print(result.diff.added)

# A dict that you can write as JSON, for CI output
import json
print(json.dumps(result.to_dict(), indent=2))
```

`check_staged` compares `HEAD` with the **staging area**, which is the content of the next commit. The `commit-msg` hook does the same comparison:

```python
from sheridan.diffract import check_staged

result = check_staged()
print(result.commit_type)  # the type of the staged change, not of the last commit
```

### Validate commit messages with pre-commit or prek

`diffract` has a `commit-msg` hook. The hook rejects a commit message only if the message tells less than the change to the public API:

- If the commit removes a public name, the message must have a `!` (for example `feat!:` or `fix!:`) or a `BREAKING CHANGE:` footer.
- If the commit adds a public name, the type must be `feat`, or the message must have a `!`.

The detected type is only an estimate from the public names. Thus the hook accepts a message that tells more than the detected type. For example, it accepts `fix:` for a change to a function body. It also accepts `feat!:` for a breaking change in behavior.

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/andrewasheridan/diffract
    rev: v<VERSION>
    hooks:
      - id: diffract-validate
```

The hook works with [pre-commit](https://pre-commit.com) and with [prek](https://github.com/j178/prek). First, install the `commit-msg` hook. Run `pre-commit install --hook-type commit-msg` or `prek install --hook-type commit-msg`.

The hook compares `HEAD` with the **git staging area**, not `HEAD~1` with `HEAD`. Thus it finds the change in the commit that you make now, not the change in the last commit. To compare other refs, give `BASE` and `HEAD` refs (see the GitHub Actions example below).

All output keeps the scope. If you write `fix(parser): …`, the error message shows `fix(parser):` as you wrote it. It also shows `feat(parser):` as the type that diffract found:

```
diffract: commit type mismatch
  written:  fix(parser):
  detected: feat(parser):
```

The suggested prefix also keeps the scope:

```
Suggested commit prefix: feat(parser):
```

The hook checks only the `feat`, `fix` and `refactor` types. It never blocks other types (`docs:`, `chore:`, `test:` and other types).

### Configuration

If your source code is not in `src/`, write the source directory one time in a configuration file. Then you do not have to give `--src` in each command.

**`diffract.toml`** (has priority over `pyproject.toml`):

```toml
src = "python/src"
```

**`pyproject.toml`**:

```toml
[tool.diffract]
src = "python/src"
```

The order of priority is:

1. The `--src` flag.
2. `diffract.toml`.
3. `pyproject.toml`.
4. The default (`src/`).

diffract reads only the source directory. It does not read the repository root as a replacement:

- If the source directory does not exist at one ref, the API at that ref is empty. For example, if the base ref is before you added `src/`, all the names at the head ref are added names.
- If the source directory does not exist at the two refs, diffract shows an error and exits with code 3. Thus an incorrect `--src` value or configuration value does not give an incorrect result.
- If your packages are at the repository root (a flat layout), use `--src .` or `src = "."`.

### As a GitHub Actions check

This workflow compares the **PR title** with the API change. It does in CI what the `commit-msg` hook does locally. It compares the `HEAD` of the PR branch with the `HEAD` of the target branch:

```yaml
# .github/workflows/diffract.yml
name: diffract

on:
  pull_request:
    types: [opened, synchronize, reopened, edited]  # 'edited' runs the check when only the title changes

jobs:
  api-change-check:
    name: Validate PR title against API changes
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # necessary to get the two commit SHAs

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

- `base.sha` is the `HEAD` of the target branch (for example `main`) at the time of the PR event.
- `head.sha` is the `HEAD` of the PR branch.
- The check never blocks other title types (`docs:`, `chore:`, `test:` and other types).
- The check keeps the scope. If the title is `fix(parser): …` and diffract finds an added name, the message shows `feat(parser):`.

## What it does not do

- `diffract` has **no AST logic of its own**. `sheridan-iceberg` gets the public API.
- It compares only public names (added names and removed names). It does not find **signature changes**, for example a new argument name or a new return type. iceberg gives lists of names, not signatures.
- It does not change commits or the git history. It only tells you the result.

## Development

```bash
task install        # install all dependencies
task check          # lint, format, typecheck and tests (all must pass)
task test           # pytest with coverage (90% or more is necessary)
```

[CONTRIBUTING.md](CONTRIBUTING.md) has the full workflow.
