# commit-msg hook

diffract has a `commit-msg` hook for [pre-commit](https://pre-commit.com) and
[prek](https://github.com/j178/prek). The hook rejects a commit message if the commit
type is not possible for the change.

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

| Change that diffract finds | Types that pass |
|---|---|
| A public name was removed or had a breaking change (`feat!`) | Any type with a `!` or a `BREAKING CHANGE:` footer |
| A public name was added or had a change that adds to it (`feat`) | `feat`, or any type with a `!` or a `BREAKING CHANGE:` footer |
| Python files in the source directory changed (`code`) | `fix`, `refactor`, `perf`, `style` or `feat`, or any type with a `!` or a `BREAKING CHANGE:` footer |
| Only Python files in the test directory changed (`test`) | `test` |
| All other changes (`other`) | `docs`, `ci`, `chore` or `build` |

The hook also obeys these rules:

- A message with no type, or with a type that is not a Conventional Commit type, fails.
- A `revert:` message always passes, because a revert can undo any change.
- The hook does not check the messages that git writes: `Merge …`, `Revert "…"`, `fixup! …` and `squash! …`.
- The hook ignores comment lines and the blank lines at the start of the message, as git does. A comment line starts with `#`, or with the value of `core.commentChar`.

A change in behavior does not always change a public name. Thus the hook accepts `feat` and a breaking message for a `code` change.

## What the hook compares

The hook compares `HEAD` with the git staging area, not `HEAD~1` with `HEAD`. Thus it
finds the change in the commit that you make now, not the change in the last commit.
git runs the `commit-msg` hook before it makes the new commit. Thus `HEAD` is still the
last commit, and the staging area has the content of the new commit.

## Output

If the commit type is not possible for the change, the hook writes the change, the
written type and the possible types to stderr. Then it exits with code 1. The written
type keeps the scope of your message. For example, `fix(parser): …` for a change that
adds a public name gives:

```
diffract: commit type mismatch
  written:  fix(parser)
  possible: feat, or any type with a '!' or a 'BREAKING CHANGE:' footer
```

## Run the check without the hook

The hook runs this command. You can run it yourself:

```bash
diffract --validate-msg-file .git/COMMIT_EDITMSG
```
