"""Run the real iceberg on two commits of a temporary repository, without the CLI."""

from git import Repo

from sheridan.diffract.differ import diff_surfaces
from sheridan.diffract.enums import ChangeKind
from sheridan.diffract.git_utils import get_api_at_ref
from sheridan.diffract.models import ApiDiff, NameChange
from tests.functional.conftest import GitRepo


def test_real_iceberg_gives_the_api_diff(repo: GitRepo) -> None:
    """A removed name, an added name and a new public submodule give the correct ``ApiDiff``."""
    repo.write("src/pkg/__init__.py", "alpha = 1\ndelta = 4\n")
    repo.write("src/pkg/sub/mod.py", "def epsilon() -> None: ...\n")
    repo.write("src/pkg/_impl.py", "def hidden() -> None: ...\n")
    repo.commit("feat!: change the api")
    git_repo = Repo(repo.path)

    diff = diff_surfaces(get_api_at_ref(git_repo, "HEAD~1"), get_api_at_ref(git_repo, "HEAD"))

    assert diff == ApiDiff(
        added=(
            NameChange(module="pkg", name="delta", kind=ChangeKind.added),
            NameChange(module="pkg.sub.mod", name="epsilon", kind=ChangeKind.added),
        ),
        removed=(NameChange(module="pkg", name="beta", kind=ChangeKind.removed),),
    )
