# How to contribute to sheridan-diffract

Thank you for your contribution.

## Setup

```bash
task install
uv run prek install
```

## Workflow

1. Create a branch from `main`.
2. Write the code. Obey the [writing style](#writing-style), [comment](#comments) and
   [readability](#readability) rules.
3. Write tests. The minimum coverage is 90%.
   - Put unit tests that mock git and iceberg in `tests/unit/`.
   - Put end-to-end tests in `tests/functional/`. These tests run the real CLI in a
     temporary git repository.
4. Run `task check`. All the gates must pass.
5. Commit with a [Conventional Commits](https://www.conventionalcommits.org/) message.
6. Open a pull request.

## Checks

```bash
task check        # all gates: lint, format, typecheck, test, sdist, api
task lint         # ruff check, with autofix
task format       # ruff format
task typecheck    # pyrefly check (strict preset)
task test         # pytest with coverage
task api:update   # write the public API to api.txt
```

`api.txt` is the public API of `src/sheridan/`, as `iceberg` shows it. `task api:check`
fails if the public API is different from `api.txt`. If you change the public API
intentionally, do these steps:

1. Run `task api:update`.
2. Commit `api.txt` together with your change.

## Mutation testing

Line coverage shows which lines the tests run. It does not show if the tests check the
result of those lines. [mutmut](https://github.com/boxed/mutmut) finds this gap. It
changes the code in small ways, and each change is a "mutant". Then it runs the tests
that call the changed function. If all of these tests pass, the mutant "survived".

mutmut is for local runs only. CI does not run it. It is in the `mutation` dependency
group, thus `uv sync` does not install it. The `task mutate` commands install it.

```bash
task mutate                                       # test all the mutants that have no result
task mutate -- "sheridan.diffract._classifier.*"  # test only the selected mutants
task mutate:results                               # list the mutants that survived
task mutate:browse                                # examine the mutants in a terminal UI
task mutate:clean                                 # delete the results (mutants/)
```

mutmut keeps its results in `mutants/`. Thus, `task mutate` with no pattern tests only
the mutants that have no result, for example the mutants in a function that changed.
A pattern selects mutants by name, for example
`"sheridan.diffract._differ.x__diff_function*"`. mutmut always tests the selected
mutants again, also if they have a result.

A new or changed test does not reset a result. Thus, after you add tests for the
mutants that survived, give a pattern for each function to test them again.

### Read the results

`task mutate` shows a count for each status:

- 🎉 killed: a test failed. This is the correct result.
- 🙁 survived: all the tests passed. The tests do not check this change.
- 🧙 caught by type check: pyrefly found a type error in the mutant. mutmut does not
  run the tests for it.
- 🫥 no tests: no test calls the function.
- ⏰ timeout: the tests ran for too long.

To see the change in a mutant, run `uv run --group mutation mutmut show <name>`, or
use `task mutate:browse`. For each mutant that survived, decide which of these it is:

- A test gap: a change to the behavior that no test finds. Write a test that fails
  with the mutant.
- An equivalent mutant: the change does not change the behavior. An example is a
  `case _: return None` arm at the end of a function, because the function then
  returns `None` anyway.

Use `# pragma: no mutate` only for an equivalent mutant. Write the reason in the same
comment, after a comma:

```python
return path.name or "."  # pragma: no mutate, Path.name is empty only for "/"
```

Put the comma before the reason. If the reason starts with `block`, `start` or `end`
and has no comma, mutmut reads that word as a different pragma.

### Limits

- mutmut changes only code in functions. It does not change constants or tables at
  module level.
- mutmut must have `fork`, thus it does not run on Windows. Use WSL.
- The functional tests run the installed `diffract` command in a subprocess. This
  process imports the code from `src/`, not the mutated copy. Thus, only the unit
  tests can kill a mutant.
- If you change `only_mutate` or `do_not_mutate` in `[tool.mutmut]`, run
  `task mutate:clean` first. If you do not, mutmut can keep a plain copy of a file
  in `mutants/` and show errors for its mutants.
- If most of the mutants show 🫥 no tests, run `task mutate:clean`, then run
  `task mutate` again. mutmut mutates a file again only if the source file is newer
  than its copy in `mutants/`. Thus, a plain copy of a file can stay in `mutants/`
  after a run that stopped or failed. The tests then call no mutated function in
  that file.

## Commit format

This project uses [Commitizen](https://commitizen-tools.github.io/commitizen/) to make
sure that commits obey Conventional Commits:

```
feat: add new feature
fix: correct a bug
docs: update documentation
chore: maintenance tasks
refactor: code restructuring without behavior change
test: add or update tests
```

## Writing style

Write all prose in ASD-STE100 Simplified Technical English (STE). STE is a controlled
language: it uses common words, short sentences and the active voice. Text in STE has
only one possible meaning.

The rule applies to:

- `README.md`, `CONTRIBUTING.md` and the files in `docs/`
- docstrings and code comments
- CLI help text, error and log messages
- issue, commit and PR bodies

It does not apply to code identifiers, quoted output from other tools, the Conventional
Commits header syntax or `CHANGELOG.md`.

The `ste100` Claude Code skill (`.claude/skills/ste100/SKILL.md`) summarizes the rules.
The full rules and the dictionary of approved words are in the ASD-STE100 specification
at [asd-ste100.org](https://www.asd-ste100.org/).

## Comments

Write a comment only when it tells a thing that the code cannot tell: a reason, a
constraint or a consequence that is not clear. Do not use banner or section-divider
comments. A banner comment is a line made only of `#` and ten or more `-` or `=`,
usually around a section title. To group code, use a test class, a separate module or
a docstring.

`tests/unit/test_comment_style.py` applies this rule to the full repo. The
`no-banner-comments` prek hook finds banner comments before you commit.

## Readability

People read code much more frequently than they write it. When two ways work, use
the way that is easier to read. Ruff sets the layout of each line. But Ruff does not
decide where a blank line helps, or when a comprehension is too clever. You decide
these things.

The Zen of Python (`python -c "import this"`) is the guide. These lines are the most
important:

- Readability counts.
- Explicit is better than implicit.
- Simple is better than complex.
- Flat is better than nested.
- Sparse is better than dense.
- If the implementation is hard to explain, it's a bad idea.

Whitespace is your friend. Use blank lines for these purposes:

- To divide a function into its logical steps (setup, work, result).
- To put `if`, `for`, `with` and `try` blocks apart from the code around them.

To make deep nesting flat, use early returns or guard clauses. Replace a dense
one-liner with a plain loop or a named intermediate value.

Before:

```python
def load(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    text = path.read_text()
    pairs = {k.strip(): v.strip() for k, _, v in (l.partition("=") for l in text.splitlines() if l and not l.startswith("#"))}
    for key in pairs:
        if not key.isidentifier():
            raise ValueError(key)
    return pairs
```

After:

```python
def load(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    pairs: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if not line or line.startswith("#"):
            continue

        key, _, value = line.partition("=")
        pairs[key.strip()] = value.strip()

    for key in pairs:
        if not key.isidentifier():
            raise ValueError(key)

    return pairs
```

This is guidance, not a lint rule. Reviewers apply it.

## Dependencies

- Propose a new runtime dependency in a PR. Give a clear reason for it.
- Keep the list of runtime dependencies small.
- Put dev dependencies in `[dependency-groups]`. Put test tools in `test`. Put all
  other tools in `dev`, which includes `test`.
- This repo tracks `uv.lock`. After you change dependencies, run `uv lock` and commit
  `uv.lock`. `task lock:check` makes sure that `uv.lock` is current.

## CI pipeline

CI runs one "All gates" job in GitHub Actions (`.github/workflows/ci.yaml`). The job
syncs the environment with `uv sync --locked`. Then it runs each gate as a `task` step.
Each gate runs also if a gate before it failed. Thus one run shows all the failures.

To run the same gates locally, run these commands:

```bash
task lock:check
task lint:check
task format:check
task typecheck
task test
task security:check
task sdist:check
task api:check
task docs:build
```

`task check` runs lint, format, typecheck, test, the sdist check and the API check.
