# Contributing to [[ cookiecutter.project_slug ]]

Thank you for considering a contribution!

## Setup

```bash
task install
pre-commit install
```

## Workflow

1. Create a feature branch from `main`
2. Write your code and tests (coverage must remain ≥ 90%)
3. Run `task check` — all gates must pass
4. Commit using [Conventional Commits](https://www.conventionalcommits.org/) format
5. Open a pull request

## Running checks

```bash
task check        # all gates: lint, format, typecheck, test
task lint         # ruff check + autofix
task format       # ruff format
task typecheck    # mypy --strict
task test         # pytest with coverage
```

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
- Dev dependencies go under `[project.optional-dependencies] dev`

## Architecture Decision Records

Significant decisions are recorded as ADRs in `docs/decisions/`.
Use the `docs/decisions/` directory to document any non-obvious choices.

## CI pipeline

The full CI pipeline runs via Dagger:

```bash
task ci-init   # first time only
task ci        # run all gates in containers
```

Individual gates: `task lint:check`, `task format:check`, `task typecheck`, `task test`.
