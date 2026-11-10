# CLAUDE.md

diffract (`sheridan-diffract` on PyPI) finds how the public API of a Python package
changed between two git refs. It gives the group of Conventional Commit types that are
possible for that change. It
does not read the AST itself: `sheridan-iceberg` extracts the public API.

## Check command

Run `task check` before you say that a change is done. It runs these gates:
`lint:check`, `format:check`, `typecheck` (pyrefly), `test`, `sdist:check` and
`api:check`. All gates must pass. CI also runs `lock:check`, `security:check` and `docs:build`.
`CONTRIBUTING.md` lists the other tasks.

## Architecture

The code is in `src/sheridan/diffract/`. `checker.py` connects the steps:

1. Git: `git_utils.py` uses `git archive` to write only the source directory of a ref (or
   of the staging area) to a temporary directory. It also gives the paths of the changed
   files. `has_python_changes` finds if `.py` or `.pyi` files in a directory changed.
2. Extract: `git_utils.py` calls `sheridan.iceberg.get_public_api` on each tree. It gives
   a dict from each dotted module name to the iceberg `Module`. The dotted name is the
   key because iceberg joins a chain of single-child packages at the top of the tree.
3. Diff: `differ.py` compares the two APIs and makes an `ApiDiff`. It finds the added
   and removed names (also class members) and the changes to the signatures, the bases
   and the kinds of the names at the two refs (`SignatureChange`). `docs/api-changes.md`
   lists the rules.
4. Classify: `classifier.py` gives the group of possible types (`CommitType`), in this
   order of priority:
   - a public name was removed, or had a breaking change: `feat!`
   - a public name was added, or had a change that adds to it: `feat`
   - `.py` or `.pyi` files in the source directory changed: `code` (`fix`, `refactor`,
     `perf`, `style`)
   - `.py` or `.pyi` files in the test directory changed: `test`
   - all other changes: `other` (`docs`, `ci`, `chore`, `build`)

   A file in the test directory is a test file, also when the test directory is in the
   source directory.

Other modules:

- `models.py`, `enums.py` and `exceptions.py`: the frozen dataclasses, the `StrEnum`s
  and the `DiffractError` exceptions.
- `config.py`: reads `src` and `tests` from `diffract.toml` or from `[tool.diffract]` in
  `pyproject.toml`. The `--src` and `--tests` flags have priority over both files.
- `cli.py`: the `diffract` command. With `--validate-msg-file` and no refs, it compares
  `HEAD` with the staging area. This is the `commit-msg` hook mode. The check fails
  if the written type is not possible for the result. `feat!` needs a `!` or a
  `BREAKING CHANGE:` footer. `feat` also accepts a breaking message. `code` accepts
  `fix`, `refactor`, `perf`, `style`, `feat` or a breaking message. `test` needs
  `test`, and `other` needs `docs`, `ci`, `chore` or `build`. A message with no
  known type fails. Messages that git writes (merge, revert, fixup, squash) and
  `revert:` messages always pass.

diffract does not compare type annotations, decorators or default values, and it does
not change commits.

## Dependencies

The dependency auditor rejected `gitpython`, but the maintainer kept it for these reasons:

- The current version of `gitpython` has a fix for each of its known CVEs.
- The CVEs are about remote URLs from untrusted sources. diffract sets all the git
  arguments, so no untrusted input goes into a git command.
- The `Repo` object reads the `GIT_DIR` and `GIT_WORK_TREE` environment variables that
  git sets for hooks. diffract reads the staging area through `repo.git`, which obeys
  `GIT_INDEX_FILE`. Do not use `repo.index`: it always reads `.git/index`.

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
