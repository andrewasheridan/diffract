# Contributing to sheridan-diffract

Thank you for considering a contribution!

## Setup

```bash
task install
uv run prek install
```

## Workflow

1. Create a feature branch from `main`
2. Write your code and tests (coverage must remain ≥ 90%): unit tests that mock git and iceberg go in
   `tests/unit/`, and end-to-end tests that run the real CLI in a temporary git repository go in
   `tests/functional/`
3. Run `task check` — all gates must pass
4. Commit using [Conventional Commits](https://www.conventionalcommits.org/) format
5. Open a pull request

## Running checks

```bash
task check        # all gates: lint, format, typecheck, test, sdist, api
task lint         # ruff check + autofix
task format       # ruff format
task typecheck    # pyrefly check (strict preset)
task test         # pytest with coverage
task api:update   # write the public API to api.txt
```

`api.txt` is the public API of `src/sheridan/`, as `iceberg` shows it. `task api:check`
fails when the public API is different from `api.txt`. When you change the public API on
purpose, run `task api:update` and commit `api.txt` with your change.

## Commit format

This project uses [Commitizen](https://commitizen-tools.github.io/commitizen/) with Conventional Commits:

```
feat: add new feature
fix: correct a bug
docs: update documentation
chore: maintenance tasks
refactor: code restructuring without behavior change
test: add or update tests
```

## Adding dependencies

- Propose new runtime dependencies in a PR with a clear justification
- Keep the runtime dependency list minimal
- Dev dependencies go under `[dependency-groups]`: test tools in `test`, everything else in `dev` (which includes `test`)
- `uv.lock` is tracked: run `uv lock` after changing dependencies and commit it (`task lock:check` verifies it)

## Architecture Decision Records

Significant decisions are recorded as ADRs in `docs/decisions/`.
Use the `docs/decisions/` directory to document any non-obvious choices.

## CI pipeline

CI runs one "All gates" job in GitHub Actions (`.github/workflows/ci.yaml`). It syncs the
environment with `uv sync --locked`, then runs each gate as a `task` step. Every gate runs even
when an earlier one fails, so one run shows all the failures.

Run the same gates locally:

```bash
task lock:check
task lint:check
task format:check
task typecheck
task test
task security:check
task sdist:check
task api:check
task docs:build
```

`task check` runs lint, format, typecheck, test, the sdist check and the API check.
