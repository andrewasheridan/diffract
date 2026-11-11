"""Run the real iceberg on two commits of a temporary repository, without the CLI."""

from git import Repo

from sheridan.diffract._differ import diff_surfaces
from sheridan.diffract._enums import ChangeKind
from sheridan.diffract._git_utils import get_api_at_ref
from sheridan.diffract._models import ApiDiff, NameChange
from tests.functional.conftest import GitRepo


def test_real_iceberg_gives_the_api_diff(repo: GitRepo) -> None:
    """A removed name, an added name and a new public submodule give the correct ``ApiDiff``."""
    repo.write("src/pkg/__init__.py", "alpha = 1\ndelta = 4\n")
    repo.write("src/pkg/sub/mod.py", "def epsilon() -> None: ...\n")
    repo.write("src/pkg/_impl.py", "def hidden() -> None: ...\n")
    repo.commit("feat!: change the api")
    git_repo = Repo(repo.path)

    base = get_api_at_ref(git_repo, "HEAD~1")
    head = get_api_at_ref(git_repo, "HEAD")
    assert base is not None
    assert head is not None

    diff = diff_surfaces(base, head)

    assert diff == ApiDiff(
        added=(
            NameChange(module="pkg", name="delta", kind=ChangeKind.added),
            NameChange(module="pkg.sub.mod", name="epsilon", kind=ChangeKind.added),
        ),
        removed=(NameChange(module="pkg", name="beta", kind=ChangeKind.removed),),
    )
