# 004. Use pytest-mock (the mocker fixture), not unittest.mock.patch

Date: 2026-03-23
Status: Accepted

## Context

The test suite mocks many parts of gitpython, iceberg and standard library modules.
There were two possible methods:

1. `unittest.mock.patch` as a context manager or a decorator
2. the `mocker` fixture of pytest-mock

Many projects use each method. The choice has an effect on the clarity of tests, on
the life of fixtures and on the agreement with pytest conventions.

## Decision

Use the `mocker` fixture of pytest-mock for all patches. Use `monkeypatch` to change
environment variables and `sys.argv`. You can use `unittest.mock.MagicMock` directly
to make mock objects. Only `patch()` is not permitted.

## Alternatives considered

**`unittest.mock.patch` as a context manager or a decorator:** This method uses the
standard library and needs no dependency. But it needs a context manager (nested
blocks) or a decorator for each patch. If the cleanup does not occur, a patch can
stay active in other tests. This method also agrees less with pytest conventions.

## Consequences

**Positive:**

- The method agrees with pytest conventions. pytest removes the patches after each
  test, without nested context managers.
- The patches follow the life of pytest fixtures. Thus a patch cannot stay active in
  other tests.
- `monkeypatch` is a pytest fixture. It needs no dependency to change environment
  variables or `sys.argv`.
- The test code is clearer because it has no nested context managers.

**Negative:**

- diffract has `pytest-mock` as a dev dependency. This package is small and many
  projects use it. It has no known security problems.
- `mocker` has no standard type for the annotation of a fixture parameter. Thus the
  tests use `pytest.fixture` as the annotation, with a `# type: ignore` comment.

**Mitigation:** Use `# type: ignore` on the fixture annotations until pytest-mock
gives a type.
