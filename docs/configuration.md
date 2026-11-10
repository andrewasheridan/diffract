# Configuration

diffract has one setting: `src`. It is the directory in the repository that contains the
Python packages. The default is `src`.

## Write the setting in a file

Write the source directory one time in a configuration file. Then you do not have to
give `--src` in each command.

**`diffract.toml`**:

```toml
src = "python/src"
```

**`pyproject.toml`**:

```toml
[tool.diffract]
src = "python/src"
```

diffract reads the files in the root of the git repository. Thus it finds them also
when you start diffract in a subdirectory.

## Order of priority

1. The `--src` flag.
2. `diffract.toml`.
3. `pyproject.toml`.
4. The default (`src`).

## When the source directory does not exist

diffract reads only the source directory. It does not read the repository root as a
replacement.

- If the source directory does not exist at one ref, the API at that ref is empty. For example, if the base ref is before you added `src/`, all the names at the head ref are added names.
- If the source directory does not exist at the two refs, diffract shows an error and exits with code 3. Thus an incorrect `--src` value or configuration value does not give an incorrect result.
- If your packages are at the repository root (a flat layout), use `--src .` or `src = "."`.

## Errors

If a configuration file is not correct TOML, or if `src` is not a string, diffract shows
an error and exits with code 3.
