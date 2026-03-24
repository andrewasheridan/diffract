# CLAUDE.md — sheridan-diffract

## Project overview

`sheridan-diffract` detects how a Python package's public API changed between two git commits and classifies that change as a conventional commit type. It has no AST logic of its own — it delegates API surface extraction entirely to `sheridan-iceberg`.

## Commands

```bash
task check          # full gate: lint, format, typecheck, tests (run before every commit)
task lint           # ruff check --fix
task lint:check     # ruff check (read-only, used in CI)
task format         # ruff format
task format:check   # ruff format --check (read-only, used in CI)
task typecheck      # mypy --strict src/
task test           # pytest --cov (coverage ≥ 90% required)
task install        # uv sync --all-extras --dev
```

## Architecture

```
src/sheridan/diffract/
├── __init__.py      # Public re-exports; __version__ from importlib.metadata
├── enums.py         # CommitType, ChangeKind (StrEnum)
├── exceptions.py    # DiffractError → GitError / SurfaceError
├── models.py        # NameChange, ApiDiff, DiffractResult (frozen dataclasses)
├── differ.py        # diff_surfaces() — set-diff two iceberg API surfaces
├── classifier.py    # classify() — maps ApiDiff → CommitType + summary
├── git_utils.py     # get_repo(), get_api_at_ref(), has_python_changes()
├── checker.py       # check() — orchestrates git → iceberg → diff → classify
└── cli.py           # argparse CLI: `diffract [BASE] [HEAD] [--json] [--exit-code]`
```

### Key dependency: sheridan-iceberg

```python
from sheridan.iceberg import get_public_api
# get_public_api(path: Path | str) -> dict[str, list[str]]
# Returns: {"module.qualified.name": ["PublicName1", "ClassFoo", ...], ...}
```

`diffract` calls `get_public_api` twice (once per ref), then diffs the two dicts.

### Classification rules (in priority order)

1. Any public name **removed** → `feat!` (breaking)
2. Any public name **added** (no removals) → `feat`
3. No name changes, but `.py` files changed → `refactor`
4. No changes detected → `fix`

## Code conventions

- **Python ≥ 3.14** — use modern syntax freely (`X | Y`, `match`, etc.)
- **`from __future__ import annotations`** at top of every file
- **`__all__`** declared in every module
- **Frozen dataclasses** for all result/model types
- **`StrEnum`** for enumerations
- **Google-style docstrings** on all public functions, classes, and methods
- **Line length**: 120 characters (ruff enforced)
- **Import order**: stdlib → third-party → local (isort via ruff)

## Testing conventions

- **pytest** only — never `unittest.TestCase`
- **pytest-mock** for patching: use the `mocker` fixture, not `unittest.mock.patch`
- **`monkeypatch`** for environment/`sys.argv` modification
- **No `MagicMock` as fixture arguments** — construct them inline with `MagicMock()`
- Shared fixtures live in `tests/conftest.py`
- One test file per source module: `test_<module>.py`
- Coverage threshold: **≥ 90%** (enforced by pytest-cov)

## Dependencies

- **Runtime**: `sheridan-iceberg`, `gitpython`
- **Dev**: `ruff`, `mypy`, `pytest`, `pytest-cov`, `pytest-mock`, `commitizen`, `pre-commit`, `bandit`, `zensical`, `mkdocstrings`

### Adding dependencies

Always run the dependency auditor before adding a new runtime dependency. Context matters: the automated auditor rejected `gitpython` on security grounds, but human review approved it (see ADR-002) because the CVEs are patched, inputs are controlled, and it handles git hook environment variables correctly.

## Commit format (Conventional Commits via commitizen)

```
feat:     add new public API
feat!:    remove or rename a public API (breaking)
fix:      correct a bug with no API change
refactor: internal restructuring, no API change
docs:     documentation only
test:     add or update tests
chore:    maintenance (deps, config, tooling)
```

## Architecture Decision Records

Significant decisions are documented in `docs/decisions/`. Use the `adr` skill to add new ones.

## What diffract does NOT do

- No AST logic — all API surface extraction is delegated to `sheridan-iceberg`
- No signature diffing — only name-level additions/removals are detected
- No automatic commit rewriting — diffract only reports and optionally fails CI
