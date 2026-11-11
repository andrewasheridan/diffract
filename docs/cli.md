# CLI and exit codes

## Usage

```
diffract [BASE_REF] [HEAD_REF] [--src SRC] [--tests TESTS] [--json] [--exit-code] [--validate-msg-file MSGFILE]
```

You can also run diffract as a module: `python -m sheridan.diffract`. The module accepts
the same arguments.

## Arguments

| Argument | Default | Description |
|---|---|---|
| `BASE_REF` | `HEAD~1` | The earlier git ref to compare. |
| `HEAD_REF` | `HEAD` | The later git ref to compare. If you give only `BASE_REF`, diffract uses `HEAD`. |
| `--src SRC` | `src` | The directory in the repository that contains the Python packages. Read [Configuration](configuration.md). |
| `--tests TESTS` | `tests` | The directory in the repository that contains the tests. Read [Configuration](configuration.md). |
| `--json` | off | Write JSON to stdout, not text. Read [JSON output](json-output.md). |
| `--exit-code` | off | Give an exit code for the type of API change. |
| `--validate-msg-file MSGFILE` | none | Check the commit type in a commit message file. Read [commit-msg hook](commit-msg-hook.md). |
| `--version` | | Show the version and exit. |

If you use `--validate-msg-file` and give no refs, diffract compares `HEAD` with the git
staging area.

## Examples

```bash
# Compare the last two commits
diffract

# Compare the specified refs
diffract HEAD~3 HEAD

# Use a different source directory
diffract --src lib/

# Use a different test directory
diffract --tests src/pkg/tests

# Write JSON for CI
diffract --json

# Exit with a code that is not zero if the public API changed
diffract --exit-code
```

## Text output

For a breaking change, diffract writes the removed names, grouped by module:

```
Detected: feat!  (breaking change)

Removed public names:
  sheridan.diffract:
    - OldHelper

Suggested commit prefix: feat!:
```

For added names, diffract writes the names with a `+`. For a breaking change to a name,
diffract writes the change with a `!`. For a change that adds to a name, it writes the
change with a `~`:

```
Detected: feat!  (breaking change)

Breaking changes:
  sheridan.diffract:
    ! check: parameter 'ref' was removed
Changes that add to public names:
  sheridan.diffract:
    ~ check: optional parameter 'strict' was added

Suggested commit prefix: feat!:
```

[API changes](api-changes.md) lists the changes that diffract finds. diffract shows a suggested prefix
only for `feat!` and `feat`. For the other groups, it shows the possible types. For
example, if no public name changed and no Python file changed, diffract writes this:

```
Detected: other

The public API did not change.

This can be a docs, ci, chore or build commit.
```

## Exit codes

| Code | Meaning |
|---|---|
| `0` | No public name changed, or the command has no `--exit-code` flag. |
| `1` | With `--exit-code`, a public name was removed or had a breaking change. With `--validate-msg-file`, the commit type in the message tells less than the API change. |
| `2` | With `--exit-code`, a public name was added or had a change that adds to it, and no breaking change occurred. |
| `3` | An error. This can be a usage error, a git, file or configuration error, or an unexpected error. |

The default exit code of `argparse` for a usage error is 2. diffract uses 3 for a usage
error. Thus a CI job can tell a usage error from an added name.

For an unexpected error, diffract does not show a traceback. It writes a short message
with a link to the issue tracker.
