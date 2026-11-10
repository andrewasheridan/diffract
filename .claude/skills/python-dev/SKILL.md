---
name: python-dev
description: Python conventions for diffract - uv for environments and dependencies, Taskfile tasks, ruff for lint and format, pyrefly for type checks, pytest for tests, prek hooks. Use when you write, change, test, or add dependencies to Python code in this repo.
---

# Python development

## Tools

| Job | Tool | Command |
|---|---|---|
| Environment, dependencies, running | uv | `uv sync`, `uv run` |
| Format | ruff | `task format` (`task format:check` to only check) |
| Lint | ruff | `task lint` (`task lint:check` to only check) |
| Type check | pyrefly | `task typecheck` |
| Test | pytest | `task test` (give pytest arguments after `--`) |
| Security lint | bandit | `task security:check` |
| Lock file | uv | `task lock:check` |
| Docs | Zensical | `task docs:build` |
| All gates | Taskfile | `task check` |

`Taskfile.yaml` defines the tasks. The configuration for ruff, pyrefly, pytest,
coverage and commitizen is in `pyproject.toml`. Do not add separate configuration files
(`ruff.toml`, `pytest.ini`, `pyrefly.toml`, `setup.cfg`).

The project uses pyrefly, not mypy. Do not run mypy.

## Rules

- Always use `uv`. Do not use `pip` or `python -m venv`, and do not activate a venv.
  Run code with `uv run ...`.
- Propose a new dependency in an issue first. Add it only after the maintainer approves
  it. Then run `uv lock` and commit `uv.lock`.
- Before you propose a new runtime dependency, run the dependency auditor. A human
  review can overrule the auditor: `docs/decisions/003-gitpython.md` tells why
  `gitpython` is a dependency.
- The package code is in `src/sheridan/diffract/`. The tests are in `tests/unit/` and
  `tests/functional/`. The name of a unit test file is `test_<module>.py`, for example
  `test_differ.py`. Unit tests mock git and iceberg. Functional tests make temporary
  git repositories and run the real `diffract` command. Shared fixtures are in the
  `conftest.py` of each directory.
- Target Python 3.14. Use modern syntax: `X | None`, built-in generics (`list[int]`),
  `type` aliases, and `match` when it is easier to read.
- The maximum line length is 120 characters. Ruff enforces it.
- Add type annotations to all function signatures, in tests too. Do not use `Any` or
  `# type: ignore` if you can use a different solution. If you must use them, add a
  comment that tells why.
- Write a test for each change in behavior. When you fix a bug, write a test that fails
  before you write the fix.
- The minimum test coverage is 90%.
- Use pytest only, not `unittest.TestCase`. Use the `mocker` fixture from pytest-mock to
  patch, not `unittest.mock.patch`. Use `monkeypatch` for environment variables and
  `sys.argv`.
- Use frozen dataclasses for result and model types, and `StrEnum` for enumerations.
  Declare `__all__` in each module. Do not use `from __future__ import annotations`.
- diffract does not read the AST. `sheridan-iceberg` extracts the public API. diffract
  compares names only, not signatures.
- If you change the output that users see, update `README.md`, `docs/` and the
  functional tests for the README examples.

## Docstrings

- Use the Google convention. Ruff enforces it (the `D` rules).
- Each public module, class, function and method in `src/` must have a docstring.
- Write the text in STE (see the `ste100` skill).
- The summary line is one imperative sentence that ends with a period.
- Do not start a docstring with "Return" or "Returns". Use a verb that tells how the
  function makes the value, such as *build*, *find*, *parse* or *resolve*.
  `tests/unit/test_docstring_style.py` enforces this rule.
- Do not write the types in the docstring. The type annotations give the types.

```python
def parse(text: str, *, strict: bool = False) -> list[Record]:
    """Parse the records in a CSV text.

    Args:
        text: The CSV text. The first line must be the header.
        strict: If true, stop at the first record that is not valid.

    Returns:
        The records, in the same order as in the text.

    Raises:
        ParseError: If `strict` is true and a record is not valid.
    """
```

## Before you say that the work is done

Run `task check` and make sure that it passes.

The prek hooks run ruff, pyrefly and the `no-banner-comments` check on each commit.
They run pytest on each push. To install the hooks, run `uv run prek install` once for
each clone.

If a check fails, fix the cause. Do not disable a rule, skip a test or suppress a type
error to make a check pass, unless the user agrees.
