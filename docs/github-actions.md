# GitHub Actions

This workflow compares the pull request title with the API change. It does in CI what
the [commit-msg hook](commit-msg-hook.md) does on your computer. It compares the `HEAD`
of the pull request branch with the `HEAD` of the target branch.

```yaml
# .github/workflows/diffract.yml
name: diffract

on:
  pull_request:
    types: [opened, synchronize, reopened, edited]  # 'edited' runs the check when only the title changes

jobs:
  api-change-check:
    name: Validate PR title against API changes
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # necessary to get the two commit SHAs

      - name: Install diffract
        run: pip install sheridan-diffract

      - name: Validate PR title type matches API change
        env:
          PR_TITLE: ${{ github.event.pull_request.title }}
        run: |
          printf '%s' "$PR_TITLE" > /tmp/pr-title.txt
          diffract \
            ${{ github.event.pull_request.base.sha }} \
            ${{ github.event.pull_request.head.sha }} \
            --validate-msg-file /tmp/pr-title.txt
```

- `base.sha` is the `HEAD` of the target branch (for example `main`) at the time of the pull request event.
- `head.sha` is the `HEAD` of the pull request branch.
- The check never blocks other title types (`docs:`, `chore:`, `test:` and other types).
- The check keeps the scope. If the title is `fix(parser): …` and diffract finds an added name, the message shows `feat(parser):`.

Do not put `${{ github.event.pull_request.title }}` directly in the `run` script. A
title can contain shell commands. The `PR_TITLE` environment variable prevents this.

## Use the exit code as a gate

To stop a job when the public API changes, use `--exit-code`:

```yaml
      - name: Stop if the public API changed
        run: |
          diffract \
            ${{ github.event.pull_request.base.sha }} \
            ${{ github.event.pull_request.head.sha }} \
            --exit-code
```

The step fails with code 1 for a removed name and with code 2 for an added name. Read
[CLI and exit codes](cli.md#exit-codes).
