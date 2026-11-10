"""Run the real CLI and iceberg on temporary repositories: classification, ``--json`` and ``--exit-code``."""

from __future__ import annotations

import json

import pytest

from tests.functional.conftest import INITIAL_PACKAGE, GitRepo

ADDED = INITIAL_PACKAGE.replace('"beta"]', '"beta", "gamma"]') + "\n\ndef gamma() -> int:\n    return 3\n"
REMOVED = '__all__ = ["alpha"]\n\n\ndef alpha() -> int:\n    return 1\n'
INTERNAL = INITIAL_PACKAGE.replace("return 2", "return 2 + _offset()") + "\n\ndef _offset() -> int:\n    return 0\n"


def _json(repo: GitRepo, *args: str) -> dict[str, object]:
    """Run ``diffract --json`` and return the parsed output."""
    proc = repo.diffract("--json", *args)
    assert proc.returncode == 0, proc.stderr
    data: dict[str, object] = json.loads(proc.stdout)
    return data


@pytest.mark.parametrize(
    ("files", "commit_type", "added", "removed"),
    [
        pytest.param({"src/pkg/__init__.py": ADDED}, "feat", [{"module": "pkg", "name": "gamma"}], [], id="addition"),
        pytest.param({"src/pkg/__init__.py": REMOVED}, "feat!", [], [{"module": "pkg", "name": "beta"}], id="removal"),
        pytest.param({"src/pkg/__init__.py": INTERNAL}, "refactor", [], [], id="internal-change"),
        pytest.param({"README.md": "# pkg\n\nMore words.\n"}, "fix", [], [], id="no-python-change"),
    ],
)
def test_json_reports_the_classification(
    repo: GitRepo,
    files: dict[str, str],
    commit_type: str,
    added: list[dict[str, str]],
    removed: list[dict[str, str]],
) -> None:
    """The default refs (HEAD~1 and HEAD) give the commit type and the changed names."""
    for relative, text in files.items():
        repo.write(relative, text)
    repo.commit("change")

    data = _json(repo)

    assert data["commit_type"] == commit_type
    assert data["base_ref"] == "HEAD~1"
    assert data["head_ref"] == "HEAD"
    assert data["diff"] == {"added": added, "removed": removed}


def test_addition_and_removal_together_is_breaking(repo: GitRepo) -> None:
    """A rename is a removal and an addition, so it is breaking."""
    repo.write("src/pkg/__init__.py", INITIAL_PACKAGE.replace("beta", "delta"))
    repo.commit("rename")

    data = _json(repo)

    assert data["commit_type"] == "feat!"
    assert data["diff"] == {
        "added": [{"module": "pkg", "name": "delta"}],
        "removed": [{"module": "pkg", "name": "beta"}],
    }


def test_explicit_refs_span_several_commits(repo: GitRepo) -> None:
    """``diffract BASE HEAD`` compares the two refs, not only the last commit."""
    repo.write("src/pkg/__init__.py", ADDED)
    repo.commit("add gamma")
    repo.write("README.md", "# pkg\n\nDocs.\n")
    repo.commit("docs")

    assert _json(repo)["commit_type"] == "fix"
    assert _json(repo, "HEAD~2", "HEAD")["commit_type"] == "feat"


@pytest.mark.parametrize(
    ("text", "exit_code"),
    [
        pytest.param(REMOVED, 1, id="breaking"),
        pytest.param(ADDED, 2, id="addition"),
        pytest.param(INTERNAL, 0, id="internal-change"),
    ],
)
def test_exit_code(repo: GitRepo, text: str, exit_code: int) -> None:
    """``--exit-code`` exits 1 for a breaking change, 2 for an addition and 0 for no API change."""
    repo.write("src/pkg/__init__.py", text)
    repo.commit("change")

    assert repo.diffract().returncode == 0
    assert repo.diffract("--exit-code").returncode == exit_code
    assert repo.diffract("--exit-code", "--json").returncode == exit_code


def test_unknown_ref_exits_3(repo: GitRepo) -> None:
    """A git error exits 3 and prints the error, also with ``--exit-code``."""
    proc = repo.diffract("no-such-ref", "HEAD", "--exit-code")

    assert proc.returncode == 3
    assert "Error: Unknown ref: no-such-ref" in proc.stderr


def test_src_flag_and_config_files(repo: GitRepo) -> None:
    """``--src`` beats ``diffract.toml``, which beats ``pyproject.toml``, which beats ``src/``."""
    repo.write("lib/other/__init__.py", '__all__ = ["one"]\n\n\ndef one() -> int:\n    return 1\n')
    repo.write("python/src/third/__init__.py", '__all__ = ["x"]\n\n\ndef x() -> int:\n    return 1\n')
    repo.commit("add the other layouts")
    repo.git("rm", "--quiet", "lib/other/__init__.py", "python/src/third/__init__.py", "src/pkg/__init__.py")
    repo.write("pyproject.toml", '[tool.diffract]\nsrc = "python/src"\n')
    repo.commit("remove everything")

    def removed(*args: str) -> object:
        diff = _json(repo, *args)["diff"]
        assert isinstance(diff, dict)
        result: object = diff["removed"]
        return result

    assert removed() == [{"module": "third", "name": "x"}]
    repo.write("diffract.toml", 'src = "lib"\n')
    assert removed() == [{"module": "other", "name": "one"}]
    assert removed("--src", "src") == [{"module": "pkg", "name": "alpha"}, {"module": "pkg", "name": "beta"}]
