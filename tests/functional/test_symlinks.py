"""Run the real CLI in a repository that has symbolic links that tar extraction refuses."""

import json
import os
from pathlib import Path

import pytest

from tests.functional.conftest import GitRepo

ADDED = (
    '__all__ = ["alpha", "beta", "gamma"]\n\n\n'
    "def alpha() -> int: ...\n\n\n"
    "def beta() -> int: ...\n\n\n"
    "def gamma() -> int: ...\n"
)


def _link(repo: GitRepo, relative: str, target: str) -> None:
    """Make a symbolic link in the working tree.

    Args:
        repo: The repository.
        relative: The path of the link, relative to the repository root.
        target: The path that the link points to.
    """
    link = repo.path / relative
    link.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(target, link)


@pytest.mark.parametrize("target", ["/etc/hosts", "../../../outside"])
def test_unsafe_link_outside_src_does_not_stop_diffract(repo: GitRepo, target: str) -> None:
    """diffract reads only ``src/``, thus a link in ``docs/`` has no effect."""
    _link(repo, "docs/assets/link", target)
    repo.commit("docs: add a link")
    repo.write("src/pkg/__init__.py", ADDED)
    repo.commit("feat: add gamma")

    proc = repo.diffract("--json")

    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["commit_type"] == "feat"
    assert data["diff"]["added"] == [{"module": "pkg", "name": "gamma"}]


def test_unsafe_link_outside_src_does_not_stop_the_staging_area_check(repo: GitRepo, tmp_path: Path) -> None:
    """The ``commit-msg`` mode reads only ``src/`` in the staging area."""
    _link(repo, "docs/link", "/etc/hosts")
    repo.write("src/pkg/__init__.py", ADDED)
    repo.git("add", "--all")
    message = tmp_path / "COMMIT_EDITMSG"
    message.write_text("feat: add gamma\n", encoding="utf-8")

    proc = repo.diffract("--validate-msg-file", str(message))

    assert proc.returncode == 0, proc.stderr


def test_unsafe_link_in_src_exits_3(repo: GitRepo) -> None:
    """A link in ``src/`` that tar extraction refuses is an error, not a traceback."""
    _link(repo, "src/pkg/link", "/etc/hosts")
    repo.commit("add a link")

    proc = repo.diffract("--json")

    assert proc.returncode == 3
    assert "Traceback" not in proc.stderr
    assert "Cannot extract" in proc.stderr
