# cookiecutter-sheridan

A [Cookiecutter](https://github.com/cookiecutter/cookiecutter) template for `sheridan.*` Python projects.

## What you get

- `sheridan.<package_name>` namespace package with `src/` layout
- CLI entrypoint via `argparse`
- Build system: [Hatchling](https://hatch.pypa.io/) + [uv](https://docs.astral.sh/uv/)
- Task runner: [Taskfile](https://taskfile.dev/)
- Code quality: ruff + mypy strict + bandit
- Testing: pytest with 90% coverage minimum
- Version management: commitizen (conventional commits)
- CI: [Dagger](https://dagger.io/) via GitHub Actions (all gates in parallel)
- Docs: [Zensical](https://github.com/sheridan/zensical) (mkdocs-based)
- Publishing: OIDC trusted publishing to PyPI on version tag

## Conventions

| Thing | Pattern | Example |
|---|---|---|
| PyPI name | `sheridan-<package>` | `sheridan-iceberg` |
| Import path | `sheridan.<package>` | `sheridan.iceberg` |
| GitHub repo | `<package-with-dashes>` | `iceberg` |

## Prerequisites

```bash
uv tool install cookiecutter
brew install go-task
brew install dagger/tap/dagger
```

## Usage

```bash
cookiecutter path/to/cookiecutter-sheridan
```

## Template variables

| Variable | Description |
|---|---|
| `project_name` | Human-readable name (README title only) |
| `package_name` | Python identifier — sets PyPI name, repo, import path |
| `description` | One-line description |
| `cli_command` | CLI tool name (defaults to `package_name`) |
| `python_version` | Minimum Python version, e.g. `3.14` |
| `initial_version` | Starting semver, e.g. `0.1.0` |
| `dagger_version` | Dagger engine version, e.g. `0.20.3` |

## Getting started after generation

```bash
cd sheridan-<package_name>
git init
task install
pre-commit install
git add .
git commit -m "feat: initial project structure"
```

Register for PyPI trusted publishing before your first release:

> pypi.org → Account Settings → Publishing → Add a new pending publisher
> - Owner: `andrewasheridan`
> - Repository: `<package-name>`
> - Workflow: `publish.yaml`
> - Environment: `pypi`

```bash
task ci-init   # generate ci/sdk/ (run once)
task ci        # run all gates locally
```
