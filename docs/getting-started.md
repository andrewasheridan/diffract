# Getting started

diffract finds how the public API of a Python package changed between two git refs.
It gives the Conventional Commit type for that change.

## Install diffract

diffract supports only Python 3.14 and later.

```bash
pip install sheridan-diffract
```

You can also use `uv`:

```bash
uv add --dev sheridan-diffract
```

## Do your first check

1. Go to the root of a git repository.
2. Make sure that the Python packages are in `src/`. If they are in a different directory, read [Configuration](configuration.md).
3. Run `diffract`.

```bash
diffract
```

diffract compares `HEAD~1` with `HEAD`. Then it writes the result:

```
Detected: other

The public API did not change.

This can be a docs, ci, chore or build commit.
```

To compare other refs, give the two refs:

```bash
diffract v1.2.0 HEAD
```

## How diffract gives the commit types

diffract uses [sheridan-iceberg](https://github.com/andrewasheridan/iceberg) to get the public API at each ref.
Then it compares the two APIs and finds the changed files. It gives the group
of possible types. The first rule that applies gives the result:

| Change | Group | Possible types |
|---|---|---|
| A public name was removed, or had a breaking change (for example, a parameter was removed) | `feat!` | `feat!` (breaking) |
| A public name was added, or had a change that adds to it (for example, a new optional parameter) | `feat` | `feat` |
| A `.py` or `.pyi` file in the source directory changed, and no public name changed | `code` | `fix`, `refactor`, `perf`, `style`, `docs` |
| A `.py` or `.pyi` file in the test directory changed | `test` | `test` |
| All other changes | `other` | `docs`, `ci`, `chore`, `build` |

diffract compares the public API and the file paths only. Thus it cannot tell a fix from
a refactor, or `docs` from `ci`. [API changes](api-changes.md) lists the changes to the
public API that diffract finds.

A file in the test directory is a test file, also when the test directory is in the
source directory. A commit that changes source files and test files is in the `code`
group.

## Next steps

- [CLI and exit codes](cli.md): all the options of the `diffract` command.
- [commit-msg hook](commit-msg-hook.md): check each commit message on your computer.
- [GitHub Actions](github-actions.md): check each pull request title in CI.
- [JSON output](json-output.md): read the result in a script.
- [API reference](api/api.md): use diffract from Python.
