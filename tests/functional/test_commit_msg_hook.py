"""Install diffract as a real git ``commit-msg`` hook and make commits through it."""

import shlex
import subprocess  # nosec B404

import pytest

from tests.functional.conftest import DIFFRACT, INITIAL_PACKAGE, GitRepo

REMOVED = '__all__ = ["alpha"]\n\n\ndef alpha() -> int:\n    return 1\n'


@pytest.fixture()
def hooked(repo: GitRepo) -> GitRepo:
    """Install ``diffract --validate-msg-file`` as the commit-msg hook of the repository.

    This is the command that the ``diffract-validate`` hook in ``.pre-commit-hooks.yaml`` runs.
    """
    hook = repo.path / ".git" / "hooks" / "commit-msg"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(f'#!/bin/sh\nexec {shlex.quote(str(DIFFRACT))} --validate-msg-file "$1"\n', encoding="utf-8")
    hook.chmod(0o755)
    return repo


def _commit(repo: GitRepo, message: str) -> subprocess.CompletedProcess[str]:
    """Stage all changes and run ``git commit`` with the hooks."""
    repo.git("add", "--all")
    return subprocess.run(  # nosec B603 B607
        ["git", "commit", "-m", message], cwd=repo.path, env=repo.env, capture_output=True, text=True, check=False
    )


def _head_subject(repo: GitRepo) -> str:
    """Read the subject of the HEAD commit."""
    return repo.git("log", "-1", "--format=%s").stdout.strip()


def test_hook_rejects_a_fix_that_removes_a_name(hooked: GitRepo) -> None:
    """The hook reads the staged change (not HEAD~1..HEAD) and blocks a wrong commit type."""
    hooked.write("src/pkg/__init__.py", REMOVED)

    proc = _commit(hooked, "fix(parser): tidy up")

    assert proc.returncode != 0
    assert "Removed public names:\n  pkg:\n    - beta" in proc.stderr
    assert "diffract: commit type mismatch\n  written:  fix(parser)\n  possible: any type with a '!'" in proc.stderr
    assert _head_subject(hooked) == "feat: initial commit"


@pytest.mark.parametrize(
    "message", ["feat!: remove beta", "feat(api)!: remove beta", "docs!: remove beta", "Merge branch 'x'"]
)
def test_hook_accepts_a_possible_type_or_a_git_message(hooked: GitRepo, message: str) -> None:
    """A possible type passes. diffract does not check the messages that git writes."""
    hooked.write("src/pkg/__init__.py", REMOVED)

    proc = _commit(hooked, message)

    assert proc.returncode == 0, proc.stderr
    assert _head_subject(hooked) == message


@pytest.mark.parametrize(
    ("text", "good", "bad"),
    [
        pytest.param(REMOVED, "feat!: x", "feat: x", id="removed"),
        pytest.param(REMOVED, "chore!: x", "chore: x", id="removed-chore"),
        pytest.param(
            INITIAL_PACKAGE.replace('"beta"]', '"beta", "gamma"]') + "gamma = 3\n", "feat: x", "fix: x", id="added"
        ),
        pytest.param(
            INITIAL_PACKAGE.replace("def beta()", "def beta(scale: int)"), "feat!: x", "fix: x", id="new-parameter"
        ),
        pytest.param(
            INITIAL_PACKAGE.replace("def beta()", "def beta(scale: int = 1)"),
            "feat: x",
            "fix: x",
            id="new-optional-parameter",
        ),
    ],
)
def test_hook_checks_each_type(hooked: GitRepo, text: str, good: str, bad: str) -> None:
    """The hook refuses a type that tells less than the API change, then accepts a type that tells enough."""
    hooked.write("src/pkg/__init__.py", text)

    assert _commit(hooked, bad).returncode != 0
    assert _commit(hooked, good).returncode == 0
    assert _head_subject(hooked) == good


@pytest.mark.parametrize(
    "message",
    [
        "fix: x",
        "feat: x",
        "feat!: x",
        "refactor: x",
        "perf: x",
        "style: x",
        "docs: x",
        "test: x",
        "chore: x",
        "fix: x\n\nBREAKING CHANGE: y",
    ],
)
def test_hook_accepts_each_type_for_an_internal_change(hooked: GitRepo, message: str) -> None:
    """A change in the source directory with no name change accepts each known type."""
    hooked.write("src/pkg/__init__.py", INITIAL_PACKAGE + "\n\ndef _helper() -> None:\n    pass\n")

    proc = _commit(hooked, message)

    assert proc.returncode == 0, proc.stderr
    assert _head_subject(hooked) == message.splitlines()[0]


def test_hook_accepts_docs_for_a_docstring_change(hooked: GitRepo) -> None:
    """A change to a docstring in the source directory does not change the API. Thus ``docs`` passes."""
    with_docstring = INITIAL_PACKAGE.replace("def beta() -> int:\n", 'def beta() -> int:\n    """Give two."""\n')
    hooked.write("src/pkg/__init__.py", with_docstring)

    proc = _commit(hooked, "docs: describe beta")

    assert proc.returncode == 0, proc.stderr
    assert _head_subject(hooked) == "docs: describe beta"


@pytest.mark.parametrize(
    ("path", "message"),
    [
        pytest.param("tests/test_pkg.py", "fix: x", id="test"),
        pytest.param("README.md", "test: x", id="other"),
    ],
)
def test_hook_accepts_each_type_for_the_test_and_other_groups(hooked: GitRepo, path: str, message: str) -> None:
    """diffract cannot tell a test change or a docs change from a different type. Thus each type passes."""
    hooked.write(path, "def test_x() -> None:\n    pass\n")

    proc = _commit(hooked, message)

    assert proc.returncode == 0, proc.stderr
    assert _head_subject(hooked) == message


def test_hook_warns_about_feat_with_no_api_change(hooked: GitRepo) -> None:
    """``feat`` with no change to a public name passes, but the hook writes a warning."""
    hooked.write("README.md", "# pkg\n\nDocs.\n")

    proc = _commit(hooked, "feat: x")

    assert proc.returncode == 0, proc.stderr
    assert "diffract: warning: the type is feat, but no public name changed." in proc.stderr


def test_hook_rejects_a_message_with_no_type(hooked: GitRepo) -> None:
    """A message with no Conventional Commit type fails, and the output says so."""
    hooked.write("README.md", "# pkg\n\nDocs.\n")

    proc = _commit(hooked, "tidy up")

    assert proc.returncode != 0
    assert "written:  (no known type)\n  possible: any Conventional Commit type (" in proc.stderr


def test_hook_ignores_the_last_commit(hooked: GitRepo) -> None:
    """A breaking last commit does not make the next commit, which changes only docs, breaking."""
    hooked.write("src/pkg/__init__.py", REMOVED)
    hooked.commit("feat!: remove beta")
    hooked.write("README.md", "# pkg\n\nDocs.\n")

    proc = _commit(hooked, "docs: typo")

    assert proc.returncode == 0, proc.stderr


@pytest.mark.parametrize("args", [["-a"], ["--", "src/pkg/__init__.py"]], ids=["all", "paths"])
def test_hook_reads_the_temporary_index_of_the_commit(hooked: GitRepo, args: list[str]) -> None:
    """``git commit -a`` and ``git commit <paths>`` give the hook a temporary index, and the hook reads it.

    The change is not in the staging area. Thus ``.git/index`` still has the old content.
    """
    hooked.write("src/pkg/__init__.py", REMOVED)
    index = hooked.path / ".git" / "index"
    staged = index.read_bytes()

    proc = subprocess.run(  # nosec B603 B607
        ["git", "commit", "-m", "fix: x", *args],
        cwd=hooked.path,
        env=hooked.env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode != 0
    assert "Removed public names:\n  pkg:\n    - beta" in proc.stderr
    assert index.read_bytes() == staged


@pytest.mark.parametrize(
    ("template", "comment_char"),
    [
        pytest.param("# type(scope): subject\n#\n# BREAKING CHANGE: description\n", None, id="comment"),
        pytest.param("\n\n", None, id="blank"),
        pytest.param("; type(scope): subject\n", ";", id="comment-char"),
    ],
)
def test_hook_skips_the_comment_lines_of_a_template(hooked: GitRepo, template: str, comment_char: str | None) -> None:
    """git gives the hook the message file before it removes the comment lines and the blank lines at the start."""
    template_file = hooked.path.parent / "template.txt"
    template_file.write_text(template, encoding="utf-8")
    hooked.git("config", "commit.template", str(template_file))
    if comment_char is not None:
        hooked.git("config", "core.commentChar", comment_char)
    hooked.write("README.md", "# pkg\n\nDocs.\n")
    hooked.git("add", "--all")
    # The editor adds the header after the template text, as a person does.
    editor = 'sh -c \'printf "chore: x\\n" >> "$1"\' -'

    proc = subprocess.run(  # nosec B603 B607
        ["git", "commit"],
        cwd=hooked.path,
        env={**hooked.env, "GIT_EDITOR": editor},
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert _head_subject(hooked) == "chore: x"
