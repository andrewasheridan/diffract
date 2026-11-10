# Configuration

diffract has two settings:

| Setting | Flag | Default | Description |
|---|---|---|---|
| `src` | `--src` | `src` | The directory in the repository that contains the Python packages. |
| `tests` | `--tests` | `tests` | The directory in the repository that contains the tests. |

The two paths are relative to the repository root. The test directory can be next to the
source directory (`tests`) or in it (for example `src/pkg/tests`). A Python file in the
test directory is a test file, not a source file.

## Write the settings in a file

Write the settings one time in a configuration file. Then you do not have to give
`--src` and `--tests` in each command.

**`diffract.toml`**:

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

diffract reads the files in the root of the git repository. Thus it finds them also
when you start diffract in a subdirectory.

## Order of priority

diffract uses this order of priority for each setting:

1. The flag (`--src` or `--tests`).
2. `diffract.toml`.
3. `pyproject.toml`.
4. The default (`src` or `tests`).

## When the source directory does not exist

diffract reads only the source directory. It does not read the repository root as a
replacement.

- If the source directory does not exist at one ref, the API at that ref is empty. For example, if the base ref is before you added `src/`, all the names at the head ref are added names.
- If the source directory does not exist at the two refs, diffract shows an error and exits with code 3. Thus an incorrect `--src` value or configuration value does not give an incorrect result.
- If your packages are at the repository root (a flat layout), use `--src .` or `src = "."`.

## Errors

If a configuration file is not correct TOML, or if `src` or `tests` is not a string,
diffract shows an error and exits with code 3.
