# CLAUDE.md

diffract (`sheridan-diffract` on PyPI) finds how the public API of a Python package
changed between two git refs. It gives the Conventional Commit type for that change. It
does not read the AST itself: `sheridan-iceberg` extracts the public API.

## Check command

Run `task check` before you say that a change is done. It runs these gates:
`lint:check`, `format:check`, `typecheck` (pyrefly), `test`, `sdist:check` and
`api:check`. All gates must pass. CI also runs `lock:check`, `security:check` and `docs:build`.
`CONTRIBUTING.md` lists the other tasks.

## Architecture

The code is in `src/sheridan/diffract/`. `checker.py` connects the steps:

1. Git: `git_utils.py` uses `git archive` to write only the source directory of a ref (or
   of the staging area) to a temporary directory. It also finds if `.py` or `.pyi` files in the source directory changed.
2. Extract: `git_utils.py` calls `sheridan.iceberg.get_public_api` on each tree to get
   the public names.
3. Diff: `differ.py` compares the two sets of names and makes an `ApiDiff`.
4. Classify: `classifier.py` gives the commit type, in this order of priority:
   - a public name was removed: `feat!`
   - a public name was added: `feat`
   - no name changed, but `.py` or `.pyi` files in the source directory changed: `refactor`
   - no change: `fix`

Other modules:

- `models.py`, `enums.py` and `exceptions.py`: the frozen dataclasses, the `StrEnum`s
  and the `DiffractError` exceptions.
- `config.py`: reads `src` from `diffract.toml` or from `[tool.diffract]` in
  `pyproject.toml`. The `--src` flag has priority over both files.
- `cli.py`: the `diffract` command. With `--validate-msg-file` and no refs, it compares
  `HEAD` with the staging area. This is the `commit-msg` hook mode. The check fails
  only if the message tells less than the API change: removed names need a `!` or a
  `BREAKING CHANGE:` footer, and added names need `feat` or a `!`.

diffract compares names only. It does not compare signatures, and it does not change
commits. `docs/decisions/` has the architecture decision records (ADRs).

## Code conventions

- Write all prose (docs, READMEs, docstrings, comments, CLI messages, issue, commit and
  PR bodies) in ASD-STE100 Simplified Technical English. Load the `ste100` skill before
  you write or edit prose.
- No banner or section-divider comments: no lines made only of `#` and a run of `-` or
  `=`, and no title comments wrapped in them. To group code, use a test class, a
  separate module or a docstring. `tests/unit/test_comment_style.py` and the
  `no-banner-comments` prek hook enforce this.
- Write a comment only when it says something the code can't: a reason, a constraint
  or a non-obvious consequence. Don't label sections or restate what the code does.
- Readability matters: code is read far more often than it is written. When two ways
  work, pick the one that is easier to read. Follow the Zen of Python
  (`python -c "import this"`), above all: readability counts; explicit is better than
  implicit; simple is better than complex; flat is better than nested.
- Whitespace is your friend. Use blank lines to split a function into its logical steps
  (setup, work, result). Flatten nesting with early returns, and prefer a plain loop or
  a named intermediate value to a clever one-liner.

The `python-dev` skill has the tools and the Python rules. The `git-workflow` skill has
the branch, commit, PR and release rules.

## Claude Code files

Commit new skills, agents and settings in `.claude/`. A file stays local only if
`.gitignore` lists it, for example the issue loop (`.claude/skills/next-issue/`).
`.claude/settings.local.json` is for your own settings and is not tracked.

`.claude/settings.json` stops pushes to `main` and force-pushes. In an interactive
session, the `.claude/hooks/ask-before-merge.sh` hook asks you before each merge
command. Headless sessions (`claude -p`) skip this question, so that the issue loop can
enable auto-merge.
