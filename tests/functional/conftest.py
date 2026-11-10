"""Fixtures for the functional tests: temporary git repositories and the real diffract CLI."""

import os
import subprocess  # nosec B404
import sysconfig
from dataclasses import dataclass
from pathlib import Path

import pytest

__all__ = ["DIFFRACT", "GitRepo", "clean_env"]

DIFFRACT: Path = Path(sysconfig.get_path("scripts")) / "diffract"
"""The ``diffract`` console script installed in the test environment."""

INITIAL_PACKAGE = (
    '__all__ = ["alpha", "beta"]\n\n\ndef alpha() -> int:\n    return 1\n\n\ndef beta() -> int:\n    return 2\n'
)
"""The first version of ``src/pkg/__init__.py`` in the ``repo`` fixture."""


def clean_env(home: Path) -> dict[str, str]:
    """Make an environment that isolates git from the user's configuration and git hooks.

    The function removes the ``GIT_*`` variables. Thus a test run that a git hook starts
    (for example the pre-push pytest hook) does not change this repository.

    Args:
        home: A directory to use as ``HOME``.

    Returns:
        A copy of ``os.environ`` that is safe for git subprocesses.
    """
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(
        HOME=str(home),
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_AUTHOR_NAME="Test",
        GIT_AUTHOR_EMAIL="test@example.com",
        GIT_COMMITTER_NAME="Test",
        GIT_COMMITTER_EMAIL="test@example.com",
    )
    return env


@dataclass(frozen=True)
class GitRepo:
    """A temporary git repository that the tests change and run diffract in.

    Attributes:
        path: The root of the working tree.
        env: The environment for git and diffract subprocesses.
    """

    path: Path
    env: dict[str, str]

    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        """Run a git command in the repository and fail the test if it fails.

        Args:
            *args: The git arguments.

        Returns:
            The completed process.
        """
        return subprocess.run(  # nosec B603 B607
            ["git", *args], cwd=self.path, env=self.env, capture_output=True, text=True, check=True
        )

    def write(self, relative: str, text: str) -> None:
        """Write a file in the working tree, and create its parent directories.

        Args:
            relative: The path relative to the repository root.
            text: The file contents.
        """
        target = self.path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def commit(self, message: str) -> None:
        """Stage all the changes and commit them. Do not run the hooks.

        Args:
            message: The commit message.
        """
        self.git("add", "--all")
        self.git("commit", "--quiet", "--no-verify", "--allow-empty", "-m", message)

    def diffract(self, *args: str) -> subprocess.CompletedProcess[str]:
        """Run the real ``diffract`` CLI in the repository.

        Args:
            *args: The CLI arguments.

        Returns:
            The completed process. The function does not check its return code.
        """
        return subprocess.run(  # nosec B603
            [str(DIFFRACT), *args], cwd=self.path, env=self.env, capture_output=True, text=True, check=False
        )


def init_repo(path: Path, home: Path) -> GitRepo:
    """Create an empty git repository with a ``main`` branch.

    Args:
        path: The directory for the repository.
        home: A directory to use as ``HOME``.

    Returns:
        The new repository.
    """
    path.mkdir(parents=True, exist_ok=True)
    repo = GitRepo(path=path, env=clean_env(home))
    repo.git("init", "--quiet", "--initial-branch=main")
    repo.git("config", "commit.gpgsign", "false")
    return repo


@pytest.fixture()
def repo(tmp_path: Path) -> GitRepo:
    """Create a git repository with one commit: package ``pkg`` with public ``alpha`` and ``beta``."""
    home = tmp_path / "home"
    home.mkdir()
    git_repo = init_repo(tmp_path / "repo", home)
    git_repo.write("src/pkg/__init__.py", INITIAL_PACKAGE)
    git_repo.write("README.md", "# pkg\n")
    git_repo.commit("feat: initial commit")
    return git_repo
