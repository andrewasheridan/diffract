# GitHub Actions

This workflow compares the pull request title with the API change. It does in CI what
the [commit-msg hook](commit-msg-hook.md) does on your computer. It compares the change
that the squash merge will put on the target branch.

```yaml
# .github/workflows/diffract.yaml
name: diffract

on:
  pull_request:
    types: [opened, synchronize, reopened, edited]  # 'edited' runs the check when only the title changes

jobs:
  api-change-check:
    name: Validate PR title against API changes
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1
        with:
          fetch-depth: 2  # necessary to get the merge commit and its first parent

      - uses: astral-sh/setup-uv@68559e99cc807c1eb7e9238fd43a15bba460eec2  # v10.3.3

      - name: Check that the PR title tells the API change
        env:
          PR_TITLE: ${{ github.event.pull_request.title }}
        run: |
          printf '%s' "$PR_TITLE" > /tmp/pr-title.txt
          uvx --from sheridan-diffract diffract HEAD^1 HEAD \
            --validate-msg-file /tmp/pr-title.txt
```

- For a `pull_request` event, `actions/checkout` gets the test merge commit of the pull request. `HEAD^1`, its first parent, is the `HEAD` of the target branch. The diff between the two is the change of the pull request only.
- Do not compare `pull_request.base.sha` with `pull_request.head.sha`. diffract compares the two trees. If the target branch moved after the branch point, the diff also contains the newer changes on the target branch, in reverse. For example, a name that a different pull request added shows as a removed name.
- The check uses the same rules as the [commit-msg hook](commit-msg-hook.md). The title type must be possible for all the changes in the pull request. For example, if the pull request changes code and tests, `test:` fails.
- The check keeps the scope. If the title is `fix(parser): …` and diffract finds an added name, the message shows `feat(parser):`.

Do not put `${{ github.event.pull_request.title }}` directly in the `run` script. A
title can contain shell commands. The `PR_TITLE` environment variable prevents this.

## Use the exit code as a gate

To stop a job when the public API changes, use `--exit-code`:

```yaml
      - name: Stop if the public API changed
        run: |
          uvx --from sheridan-diffract diffract HEAD^1 HEAD --exit-code
```

The step fails with code 1 for a breaking change and with code 2 for an added name. Read
[CLI and exit codes](cli.md#exit-codes).
