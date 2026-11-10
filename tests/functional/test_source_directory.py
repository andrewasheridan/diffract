"""Run the real CLI when the source directory is missing at one ref or at the two refs."""

import json

from tests.functional.conftest import INITIAL_PACKAGE, GitRepo


def test_src_added_later_gives_only_additions(repo: GitRepo) -> None:
    """A base before ``src/`` existed has an empty API, so diffract does not read the root there."""
    repo.write("setup_helper.py", '__all__ = ["helper"]\n\n\ndef helper() -> None: ...\n')
    repo.git("rm", "--quiet", "-r", "src")
    repo.commit("flat layout")
    repo.write("src/pkg/__init__.py", INITIAL_PACKAGE)
    repo.commit("move to src")

    proc = repo.diffract("--json")

    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["commit_type"] == "feat"
    assert data["diff"]["removed"] == []


def test_src_missing_at_both_refs_exits_3(repo: GitRepo) -> None:
    """A typo in ``--src`` is an error, not a scan of the repository root."""
    repo.write("README.md", "# pkg\n\nMore words.\n")
    repo.commit("docs")

    proc = repo.diffract("--src", "scr")

    assert proc.returncode == 3
    assert "'scr' does not exist at HEAD~1 or at HEAD" in proc.stderr
    assert proc.stdout == ""


def test_src_dot_reads_the_repository_root(repo: GitRepo) -> None:
    """``--src .`` reads the repository root, for a flat layout."""
    repo.write("flat.py", '__all__ = ["one"]\n\n\ndef one() -> int:\n    return 1\n')
    repo.commit("add flat module")

    proc = repo.diffract("--json", "--src", ".")

    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["diff"]["added"] == [{"module": "flat", "name": "one"}]
