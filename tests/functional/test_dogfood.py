"""Run the real diffract CLI on a clone of the diffract repository itself."""

import json
import subprocess  # nosec B404
from pathlib import Path

import pytest

from tests.functional.conftest import GitRepo, clean_env

ROOT = Path(__file__).resolve().parents[2]
INIT = "src/sheridan/diffract/__init__.py"


def _clone(tmp_path: Path) -> GitRepo:
    """Clone the HEAD commit of this repository. A shallow CI checkout works too."""
    home = tmp_path / "home"
    home.mkdir()
    env = clean_env(home)
    target = tmp_path / "diffract"
    subprocess.run(  # nosec B603 B607
        ["git", "clone", "--quiet", "--no-hardlinks", str(ROOT), str(target)],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    clone = GitRepo(path=target, env=env)
    clone.git("config", "commit.gpgsign", "false")
    return clone


@pytest.mark.skipif(not (ROOT / ".git").exists(), reason="needs the diffract git repository, not an sdist")
def test_diffract_on_itself(tmp_path: Path) -> None:
    """To remove ``load_config`` from ``__all__`` is a breaking change. To add it again is a feature."""
    clone = _clone(tmp_path)
    init = clone.path / INIT
    original = init.read_text(encoding="utf-8")
    assert '    "load_config",\n' in original

    proc = clone.diffract("HEAD", "HEAD", "--json")
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["commit_type"] == "fix"

    clone.write(INIT, original.replace('    "load_config",\n', ""))
    clone.commit("feat!: remove load_config")
    proc = clone.diffract("--json", "--exit-code")
    assert proc.returncode == 1, proc.stderr
    data = json.loads(proc.stdout)
    assert data["commit_type"] == "feat!"
    assert data["diff"] == {"added": [], "removed": [{"module": "sheridan.diffract", "name": "load_config"}]}

    clone.write(INIT, original)
    clone.commit("feat: restore load_config")
    proc = clone.diffract("--exit-code")
    assert proc.returncode == 2, proc.stderr
    assert "Added public names:\n  sheridan.diffract:\n    + load_config" in proc.stdout
    assert clone.diffract("HEAD~2", "HEAD", "--exit-code").returncode == 0
