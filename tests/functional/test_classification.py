"""Run the real CLI and iceberg on temporary repositories: commit types, ``--json`` and ``--exit-code``."""

import json

import pytest

from tests.functional.conftest import INITIAL_PACKAGE, GitRepo

ADDED = INITIAL_PACKAGE.replace('"beta"]', '"beta", "gamma"]') + "\n\ndef gamma() -> int:\n    return 3\n"
REMOVED = '__all__ = ["alpha"]\n\n\ndef alpha() -> int:\n    return 1\n'
TEST = "def test_alpha() -> None:\n    assert True\n"
INTERNAL = INITIAL_PACKAGE.replace("return 2", "return 2 + _offset()") + "\n\ndef _offset() -> int:\n    return 0\n"


def _json(repo: GitRepo, *args: str) -> dict[str, object]:
    """Run ``diffract --json`` and parse the output."""
    proc = repo.diffract("--json", *args)
    assert proc.returncode == 0, proc.stderr
    data: dict[str, object] = json.loads(proc.stdout)
    return data


@pytest.mark.parametrize(
    ("files", "group", "added", "removed"),
    [
        pytest.param({"src/pkg/__init__.py": ADDED}, "feat", [{"module": "pkg", "name": "gamma"}], [], id="addition"),
        pytest.param({"src/pkg/__init__.py": REMOVED}, "feat!", [], [{"module": "pkg", "name": "beta"}], id="removal"),
        pytest.param({"src/pkg/__init__.py": INTERNAL}, "code", [], [], id="internal-change"),
        pytest.param({"src/pkg/__init__.py": INTERNAL, "tests/test_pkg.py": TEST}, "code", [], [], id="code-and-test"),
        pytest.param({"tests/test_pkg.py": TEST}, "test", [], [], id="test-change"),
        pytest.param({"README.md": "# pkg\n\nMore words.\n"}, "other", [], [], id="no-python-change"),
    ],
)
def test_json_reports_the_classification(
    repo: GitRepo,
    files: dict[str, str],
    group: str,
    added: list[dict[str, str]],
    removed: list[dict[str, str]],
) -> None:
    """The default refs (HEAD~1 and HEAD) give the group of possible types and the changed names."""
    for relative, text in files.items():
        repo.write(relative, text)
    repo.commit("change")

    data = _json(repo)

    assert data["group"] == group
    assert data["base_ref"] == "HEAD~1"
    assert data["head_ref"] == "HEAD"
    assert data["diff"] == {"added": added, "removed": removed}


def test_addition_and_removal_together_is_breaking(repo: GitRepo) -> None:
    """A rename is a removal and an addition, so it is breaking."""
    repo.write("src/pkg/__init__.py", INITIAL_PACKAGE.replace("beta", "delta"))
    repo.commit("rename")

    data = _json(repo)

    assert data["group"] == "feat!"
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

    assert _json(repo)["group"] == "other"
    assert _json(repo, "HEAD~2", "HEAD")["group"] == "feat"


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
    assert "Error: The ref does not exist: no-such-ref" in proc.stderr


def test_src_flag_and_config_files(repo: GitRepo) -> None:
    """``--src`` has priority over ``diffract.toml``, then ``pyproject.toml``, then ``src/``."""
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


def test_human_output_gives_the_possible_types(repo: GitRepo) -> None:
    """For a group with more than one type, the text gives the types and no prefix."""
    repo.write("src/pkg/__init__.py", INTERNAL)
    repo.commit("change")

    proc = repo.diffract()

    assert proc.returncode == 0, proc.stderr
    assert "This can be a fix, refactor, perf or style commit." in proc.stdout
    assert "Suggested commit prefix" not in proc.stdout
    assert _json(repo)["possible_types"] == ["fix", "refactor", "perf", "style"]


def test_tests_flag_and_config_files(repo: GitRepo) -> None:
    """A test directory in the source directory is set with ``--tests`` or the ``tests`` setting."""
    repo.write("src/pkg/tests/test_pkg.py", TEST)
    repo.commit("add tests in the package")

    assert _json(repo)["group"] == "code"
    assert _json(repo, "--tests", "src/pkg/tests")["group"] == "test"

    repo.write("pyproject.toml", '[tool.diffract]\ntests = "src/pkg/tests"\n')
    assert _json(repo)["group"] == "test"
    repo.write("diffract.toml", 'tests = "tests"\n')
    assert _json(repo)["group"] == "code"
