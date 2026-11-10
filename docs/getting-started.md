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
Detected: fix

The public API did not change.

Suggested commit prefix: fix:
```

To compare other refs, give the two refs:

```bash
diffract v1.2.0 HEAD
```

## How diffract gives the commit type

diffract uses [sheridan-iceberg](https://github.com/andrewasheridan/iceberg) to get the public names at each ref.
Then it compares the two sets of names. It gives the type in this order of priority:

| Change | Commit type |
|---|---|
| A public name was removed | `feat!` (breaking) |
| A public name was added | `feat` |
| Only internal or private changes in the source directory | `refactor` |
| No change | `fix` |

diffract counts a code change only in the `.py` and `.pyi` files in the source directory.
diffract compares names only. It does not find signature changes.

## Next steps

- [CLI and exit codes](cli.md): all the options of the `diffract` command.
- [commit-msg hook](commit-msg-hook.md): check each commit message on your computer.
- [GitHub Actions](github-actions.md): check each pull request title in CI.
- [JSON output](json-output.md): read the result in a script.
- [API reference](api/api.md): use diffract from Python.
