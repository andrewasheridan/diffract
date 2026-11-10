# sheridan-diffract

**diffract finds how the public API of a Python package changed between two git commits. It gives the Conventional Commit types that are possible for that change.**

Most semver tools accept the commit type that the developer writes. `diffract` compares that type with the real change to the API. For example, it finds a commit with the type `fix:` that removed a public function.

diffract supports only Python 3.14 and later.

## How it works

1. diffract uses [sheridan-iceberg](https://github.com/andrewasheridan/iceberg) to get the public API at two points in the git history.
2. It compares the two APIs to find the names that were added or removed.
3. It gives the group of Conventional Commit types that are possible for the change. The first rule that applies gives the result:

| Change | Group | Possible types |
|---|---|---|
| A public name was removed | `feat!` | `feat!` (breaking) |
| A public name was added | `feat` | `feat` |
| A `.py` or `.pyi` file in the source directory changed, and no public name changed | `code` | `fix`, `refactor`, `perf`, `style` |
| A `.py` or `.pyi` file in the test directory changed | `test` | `test` |
| All other changes | `other` | `docs`, `ci`, `chore`, `build` |

diffract compares only names and file paths. Thus it cannot tell a fix from a refactor,
or `docs` from `ci`. It tells you only which types are possible.

The source directory is `src` and the test directory is `tests` by default. A file in the
test directory is a test file, also when the test directory is in the source directory
(for example `src/pkg/tests`). A commit that changes source files and test files is in
the `code` group.

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

# Use a different test directory (default: tests/)
diffract --tests src/pkg/tests

# Write JSON for CI
diffract --json

# Exit with a code that is not zero if the change is breaking (for CI gates)
diffract --exit-code
```

You can also run diffract as a module: `python -m sheridan.diffract`. The module accepts the same arguments.

**Exit codes:**

- `0`: no change to the public API, or `--exit-code` is not set.
- `1`: with `--exit-code`, a breaking change (a public name was removed). With `--validate-msg-file`, a commit message with a type that is not possible for the change.
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
Detected: other

The public API did not change.

This can be a docs, ci, chore or build commit.
```

diffract shows a suggested prefix only for `feat!` and `feat`. For the other groups, it
shows the possible types.

### Python API

```python
from sheridan.diffract import check

result = check(base_ref="v1.2.0", head_ref="HEAD")
print(result.commit_type)   # the group, for example "feat!" or "code"
print(result.commit_type.possible_types)  # for example ("fix", "refactor", "perf", "style")
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
print(result.commit_type)  # the group of the staged change, not of the last commit
```

### Validate commit messages with pre-commit or prek

`diffract` has a `commit-msg` hook. The hook rejects a commit message if the commit type is not possible for the change:

| Change that diffract finds | Types that pass |
|---|---|
| A public name was removed (`feat!`) | Any type with a `!` or a `BREAKING CHANGE:` footer |
| A public name was added (`feat`) | `feat`, or any type with a `!` or a `BREAKING CHANGE:` footer |
| Python files in the source directory changed (`code`) | `fix`, `refactor`, `perf`, `style` or `feat`, or any type with a `!` or a `BREAKING CHANGE:` footer |
| Only Python files in the test directory changed (`test`) | `test` |
| All other changes (`other`) | `docs`, `ci`, `chore` or `build` |

The hook also obeys these rules:

- A message with no type, or with a type that is not a Conventional Commit type, fails.
- A `revert:` message always passes, because a revert can undo any change.
- The hook does not check the messages that git writes: `Merge …`, `Revert "…"`, `fixup! …` and `squash! …`.

A change in behavior does not always change a public name. Thus the hook accepts `feat` and a breaking message for a `code` change.

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

If the hook rejects the message, it shows the written type and the possible types. The written type keeps the scope. For example, `fix(parser): …` for a change that adds a public name gives:

```
diffract: commit type mismatch
  written:  fix(parser)
  possible: feat, or any type with a '!' or a 'BREAKING CHANGE:' footer
```

The suggested prefix also keeps the scope:

```
Suggested commit prefix: feat(parser):
```

### Configuration

diffract has two settings:

- `src`: the source directory. The default is `src`.
- `tests`: the test directory. The default is `tests`.

If your code is in other directories, write the settings one time in a configuration file. Then you do not have to give `--src` and `--tests` in each command.

**`diffract.toml`** (has priority over `pyproject.toml`):

```toml
src = "python/src"
tests = "python/tests"
```

**`pyproject.toml`**:

```toml
[tool.diffract]
src = "python/src"
tests = "python/tests"
```

The order of priority for each setting is:

1. The flag (`--src` or `--tests`).
2. `diffract.toml`.
3. `pyproject.toml`.
4. The default (`src/` or `tests/`).

diffract reads only the source directory. It does not read the repository root as a replacement:

- If the source directory does not exist at one ref, the API at that ref is empty. For example, if the base ref is before you added `src/`, all the names at the head ref are added names.
- If the source directory does not exist at the two refs, diffract shows an error and exits with code 3. Thus an incorrect `--src` value or configuration value does not give an incorrect result.
- If your packages are at the repository root (a flat layout), use `--src .` or `src = "."`.

### As a GitHub Actions check

This workflow compares the **PR title** with the API change. It does in CI what the `commit-msg` hook does locally. It compares the `HEAD` of the PR branch with the `HEAD` of the target branch:

```yaml
# .github/workflows/diffract.yaml
name: diffract

on:
  pull_request:
    types: [opened, synchronize, reopened, edited]  # 'edited' runs the check when only the title changes

jobs:
  api-change-check:
    name: Validate PR title against API changes
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1
        with:
          fetch-depth: 0  # necessary to get the two commit SHAs

      - uses: astral-sh/setup-uv@68559e99cc807c1eb7e9238fd43a15bba460eec2  # v10.3.3

      - name: Check that the PR title tells the API change
        env:
          PR_TITLE: ${{ github.event.pull_request.title }}
        run: |
          printf '%s' "$PR_TITLE" > /tmp/pr-title.txt
          uvx --from sheridan-diffract diffract \
            ${{ github.event.pull_request.base.sha }} \
            ${{ github.event.pull_request.head.sha }} \
            --validate-msg-file /tmp/pr-title.txt
```

- `base.sha` is the `HEAD` of the target branch (for example `main`) at the time of the PR event.
- `head.sha` is the `HEAD` of the PR branch.
- The check uses the same rules as the `commit-msg` hook. The title type must be possible for all the changes in the PR. For example, if the PR changes code and tests, `test:` fails.
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
