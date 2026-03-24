# 004. Use pytest-mock (mocker fixture) instead of unittest.mock.patch

Date: 2026-03-23
Status: Accepted

## Context

The test suite requires extensive mocking of gitpython, iceberg, and stdlib modules. Two approaches were available:
1. `unittest.mock.patch` as context manager or decorator
2. pytest-mock's `mocker` fixture

Both are widely used; the choice affects test clarity, fixture lifecycle, and consistency with pytest idioms.

## Decision

Use pytest-mock's `mocker` fixture for all patching. Use `monkeypatch` for environment and `sys.argv` modifications. `unittest.mock.MagicMock` may still be used directly to construct mock objects; only `patch()` is replaced.

## Alternatives Considered

**unittest.mock.patch as context manager or decorator:** Allows direct use of the stdlib mock library without an additional dependency. However, it requires explicit context management (nesting or decorators) and risks patch leakage across tests if cleanup is missed. The approach is less idiomatic in pytest-based projects.

## Consequences

**Positive:**
- Consistent with pytest idioms; patches are automatically undone after each test without context manager nesting
- Patches integrate with pytest's fixture lifecycle — no risk of patch leakage across tests
- `monkeypatch` is a built-in pytest fixture requiring no extra dependency for env/argv manipulation
- Cleaner test code without context manager nesting

**Negative:**
- Adds `pytest-mock` as a dev dependency (lightweight, widely used, no security concerns)
- `mocker` is not type-annotated as a standard fixture type — tests use `pytest.fixture` as type annotation with a `# type: ignore` comment until upstream improves this

**Mitigation:** Use `# type: ignore` on fixture type annotations as a workaround for missing upstream type support.
