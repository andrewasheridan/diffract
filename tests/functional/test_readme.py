"""Run the examples in README.md against a temporary repository with the real CLI and iceberg.

Each expected output is also checked against the README text, so the README and the tool stay in step.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from sheridan.diffract import check, check_staged
from tests.functional.conftest import GitRepo

README = (Path(__file__).resolve().parents[2] / "README.md").read_text(encoding="utf-8")

PACKAGE = "src/sheridan/diffract/__init__.py"
BEFORE = '__all__ = ["NewHelper", "OldHelper"]\n\n\nclass NewHelper:\n    pass\n\n\nclass OldHelper:\n    pass\n'
AFTER = '__all__ = ["NewHelper"]\n\n\nclass NewHelper:\n    pass\n'

BREAKING_OUTPUT = """\
Detected: feat!  (breaking change)

Removed public names:
  sheridan.diffract:
    - OldHelper

Suggested commit prefix: feat!:
"""

FIX_OUTPUT = """\
Detected: fix

No public API changes detected.

Suggested commit prefix: fix:
"""


@pytest.fixture()
def readme_repo(repo: GitRepo) -> GitRepo:
    """Return a repository with the ``sheridan.diffract`` package from the README examples.

    The history is: ``v1.2.0`` (both helpers), then a commit that removes ``OldHelper``.
    """
    repo.write(PACKAGE, BEFORE)
    repo.commit("feat: add the helpers")
    repo.git("tag", "v1.2.0")
    repo.write(PACKAGE, AFTER)
    repo.commit("feat!: remove OldHelper")
    return repo


def test_the_readme_outputs_are_in_the_readme() -> None:
    """The outputs that these tests expect are the ones that the README shows."""
    assert f"```\n{BREAKING_OUTPUT}```" in README
    assert f"```\n{FIX_OUTPUT}```" in README
    assert "Suggested commit prefix: feat(parser):" in README
    assert "diffract: commit type mismatch\n  written:  fix(parser):\n  detected: feat(parser):" in README


def test_default_and_explicit_refs(readme_repo: GitRepo) -> None:
    """``diffract`` and ``diffract HEAD~3 HEAD`` print the README outputs."""
    assert "diffract\n" in README
    assert "diffract HEAD~3 HEAD\n" in README

    proc = readme_repo.diffract()
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == BREAKING_OUTPUT

    readme_repo.write("README.md", "# pkg\n\nDocs.\n")
    readme_repo.commit("docs: more")
    readme_repo.write("README.md", "# pkg\n\nMore docs.\n")
    readme_repo.commit("docs: even more")
    assert readme_repo.diffract().stdout == FIX_OUTPUT
    assert readme_repo.diffract("HEAD~3", "HEAD").stdout == BREAKING_OUTPUT


def test_src_json_and_exit_code(readme_repo: GitRepo) -> None:
    """``diffract --src lib/``, ``diffract --json`` and ``diffract --exit-code`` work as the README says."""
    for example in ("diffract --src lib/\n", "diffract --json\n", "diffract --exit-code\n"):
        assert example in README

    readme_repo.git("mv", "src", "lib")
    readme_repo.commit("refactor: move to lib")
    readme_repo.write("lib/sheridan/diffract/__init__.py", BEFORE)
    readme_repo.commit("feat: restore OldHelper")
    proc = readme_repo.diffract("--src", "lib/", "--exit-code")
    assert proc.returncode == 2
    assert "Added public names:\n  sheridan.diffract:\n    + OldHelper" in proc.stdout

    data = json.loads(readme_repo.diffract("--src", "lib/", "--json").stdout)
    assert data["commit_type"] == "feat"
    assert "- `2` — non-breaking API change (public name added)" in README


def test_scope_in_the_suggestion_and_the_mismatch(readme_repo: GitRepo, tmp_path: Path) -> None:
    """A scope in the message appears in the suggestion and in the mismatch message, as in the README."""
    message = tmp_path / "msg.txt"
    readme_repo.write("src/sheridan/diffract/__init__.py", BEFORE.replace('"OldHelper"]', '"OldHelper", "Third"]'))
    readme_repo.git("add", "--all")
    message.write_text("fix(parser): add Third\n", encoding="utf-8")

    proc = readme_repo.diffract("--validate-msg-file", str(message))

    assert proc.returncode == 1
    assert "Suggested commit prefix: feat(parser):" in proc.stderr
    assert "diffract: commit type mismatch\n  written:  fix(parser):\n  detected: feat(parser):" in proc.stderr


def test_github_actions_example(readme_repo: GitRepo, tmp_path: Path) -> None:
    """``diffract BASE_SHA HEAD_SHA --validate-msg-file`` checks a PR title against the two commits."""
    assert "--validate-msg-file /tmp/pr-title.txt" in README
    base = readme_repo.git("rev-parse", "v1.2.0").stdout.strip()
    head = readme_repo.git("rev-parse", "HEAD").stdout.strip()
    title = tmp_path / "pr-title.txt"

    title.write_text("feat!: remove OldHelper", encoding="utf-8")
    assert readme_repo.diffract(base, head, "--validate-msg-file", str(title)).returncode == 0
    title.write_text("fix: remove OldHelper", encoding="utf-8")
    assert readme_repo.diffract(base, head, "--validate-msg-file", str(title)).returncode == 1
    title.write_text("chore: remove OldHelper", encoding="utf-8")
    assert readme_repo.diffract(base, head, "--validate-msg-file", str(title)).returncode == 0


@pytest.mark.parametrize(
    ("filename", "text"),
    [("diffract.toml", 'src = "python/src"\n'), ("pyproject.toml", '[tool.diffract]\nsrc = "python/src"\n')],
)
def test_configuration_files(readme_repo: GitRepo, filename: str, text: str) -> None:
    """The README configuration examples set the source directory."""
    assert f"```toml\n{text}```" in README
    (readme_repo.path / "python").mkdir()
    readme_repo.git("mv", "src", "python/src")
    readme_repo.write(filename, text)
    readme_repo.commit("refactor: move to python/src")
    readme_repo.write("python/src/sheridan/diffract/__init__.py", BEFORE)
    readme_repo.commit("feat: restore OldHelper")

    data = json.loads(readme_repo.diffract("--json").stdout)

    assert data["diff"] == {"added": [{"module": "sheridan.diffract", "name": "OldHelper"}], "removed": []}


def test_python_api(readme_repo: GitRepo, monkeypatch: pytest.MonkeyPatch) -> None:
    """The ``check`` and ``check_staged`` examples run in the repository directory."""
    assert 'check(base_ref="v1.2.0", head_ref="HEAD")' in README
    assert "result = check_staged()" in README
    monkeypatch.chdir(readme_repo.path)
    for key in [key for key in os.environ if key.startswith("GIT_")]:
        monkeypatch.delenv(key)

    result = check(base_ref="v1.2.0", head_ref="HEAD")
    assert str(result.commit_type) == "feat!"
    assert result.summary
    assert [(c.module, c.name) for c in result.diff.removed] == [("sheridan.diffract", "OldHelper")]
    assert result.diff.added == ()
    assert json.loads(json.dumps(result.to_dict()))["commit_type"] == "feat!"

    assert str(check_staged().commit_type) == "fix"
    readme_repo.write(PACKAGE, BEFORE)
    readme_repo.git("add", "--all")
    assert str(check_staged().commit_type) == "feat"
