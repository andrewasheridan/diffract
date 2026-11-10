# commit-msg hook

diffract has a `commit-msg` hook for [pre-commit](https://pre-commit.com) and
[prek](https://github.com/j178/prek). The hook rejects a commit message only if the
message tells less than the change to the public API.

## Install the hook

1. Add the hook to `.pre-commit-config.yaml`:

    ```yaml
    repos:
      - repo: https://github.com/andrewasheridan/diffract
        rev: v<VERSION>
        hooks:
          - id: diffract-validate
    ```

2. Install the `commit-msg` hook type. Run one of these commands:

    ```bash
    pre-commit install --hook-type commit-msg
    prek install --hook-type commit-msg
    ```

Write the source directory in `diffract.toml` or in `pyproject.toml`, not in the hook
arguments. Read [Configuration](configuration.md).

## The rules

- If the commit removes a public name, the message must have a `!` (for example `feat!:` or `fix!:`) or a `BREAKING CHANGE:` footer.
- If the commit adds a public name, the type must be `feat`, or the message must have a `!`.
- The hook checks only the `feat`, `fix` and `refactor` types. It never blocks other types, for example `docs:`, `chore:` or `test:`.

The detected type is only an estimate from the public names. Thus the hook accepts a
message that tells more than the detected type. For example, it accepts `fix:` for a
change to a function body. It also accepts `feat!:` for a breaking change in behavior.

## What the hook compares

The hook compares `HEAD` with the git staging area, not `HEAD~1` with `HEAD`. Thus it
finds the change in the commit that you make now, not the change in the last commit.
git runs the `commit-msg` hook before it makes the new commit. Thus `HEAD` is still the
last commit, and the staging area has the content of the new commit.

## Output

If the message tells less than the API change, the hook writes the API change and the
two types to stderr. Then it exits with code 1. The output keeps the scope of your
message:

```
diffract: commit type mismatch
  written:  fix(parser):
  detected: feat(parser):
```

## Run the check without the hook

The hook runs this command. You can run it yourself:

```bash
diffract --validate-msg-file .git/COMMIT_EDITMSG
```
