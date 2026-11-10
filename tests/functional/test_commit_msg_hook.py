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
    assert "diffract: commit type mismatch\n  written:  fix(parser):\n  detected: feat(parser)!:" in proc.stderr
    assert _head_subject(hooked) == "feat: initial commit"


@pytest.mark.parametrize("message", ["feat!: remove beta", "feat(api)!: remove beta", "docs: not checked"])
def test_hook_accepts_a_matching_or_unchecked_type(hooked: GitRepo, message: str) -> None:
    """A matching type passes, and a type that diffract does not check is never blocked."""
    hooked.write("src/pkg/__init__.py", REMOVED)

    proc = _commit(hooked, message)

    assert proc.returncode == 0, proc.stderr
    assert _head_subject(hooked) == message


@pytest.mark.parametrize(
    ("text", "good", "bad"),
    [
        pytest.param(
            INITIAL_PACKAGE + "\n\ndef _helper() -> None:\n    pass\n", "refactor: x", "feat: x", id="internal"
        ),
        pytest.param(
            INITIAL_PACKAGE.replace('"beta"]', '"beta", "gamma"]') + "gamma = 3\n", "feat: x", "fix: x", id="added"
        ),
    ],
)
def test_hook_checks_each_type(hooked: GitRepo, text: str, good: str, bad: str) -> None:
    """The hook rejects the wrong type and then accepts the right one for the same staged change."""
    hooked.write("src/pkg/__init__.py", text)

    assert _commit(hooked, bad).returncode != 0
    assert _commit(hooked, good).returncode == 0
    assert _head_subject(hooked) == good


def test_hook_ignores_the_last_commit(hooked: GitRepo) -> None:
    """A breaking last commit does not make the next commit, which changes only docs, breaking."""
    hooked.write("src/pkg/__init__.py", REMOVED)
    hooked.commit("feat!: remove beta")
    hooked.write("README.md", "# pkg\n\nDocs.\n")

    proc = _commit(hooked, "fix: typo")

    assert proc.returncode == 0, proc.stderr
