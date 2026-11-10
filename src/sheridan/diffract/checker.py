"""Connect the git, extract, diff and classify steps of sheridan-diffract."""

__all__ = ["check", "check_staged"]

from pathlib import Path

from sheridan.diffract.classifier import classify
from sheridan.diffract.differ import diff_surfaces
from sheridan.diffract.enums import CommitType
from sheridan.diffract.exceptions import SurfaceError
from sheridan.diffract.git_utils import (
    get_api_at_index,
    get_api_at_ref,
    get_changed_paths,
    get_changed_paths_index,
    get_repo,
    has_python_changes,
)
from sheridan.diffract.models import ApiDiff, DiffractResult

type _Surface = dict[str, list[str]]


def _resolve_surfaces(
    base: _Surface | None,
    head: _Surface | None,
    src_path: str,
    base_ref: str,
    head_ref: str,
) -> tuple[_Surface, _Surface]:
    """Replace a missing source directory with an empty API.

    If ``src_path`` does not exist at one ref, the API at that ref is empty. diffract
    does not read the repository root in its place, because then the two refs can
    give different module names.

    Args:
        base: The API at the base, or ``None`` if ``src_path`` does not exist there.
        head: The API at the head, or ``None`` if ``src_path`` does not exist there.
        src_path: The source directory, for the error message.
        base_ref: The name of the base, for the error message.
        head_ref: The name of the head, for the error message.

    Returns:
        The base API and the head API.

    Raises:
        SurfaceError: If ``src_path`` does not exist at the two refs.
    """
    if base is None and head is None:
        raise SurfaceError(
            f"The source directory {src_path!r} does not exist at {base_ref} or at {head_ref}. "
            "Set the correct directory with --src or in the config file. "
            "To read the repository root, use --src ."
        )

    return base or {}, head or {}


def _classify_changes(
    diff: ApiDiff,
    changed_paths: list[str],
    src_path: str,
    tests_path: str,
) -> tuple[CommitType, str]:
    """Find the code and test changes in the changed paths, then classify the diff.

    A file in ``tests_path`` is a test file, also when ``tests_path`` is in ``src_path``.

    Args:
        diff: The API diff.
        changed_paths: The paths of the changed files, relative to the repository root.
        src_path: The source directory.
        tests_path: The test directory.

    Returns:
        The group of possible commit types and the summary.
    """
    return classify(
        diff,
        code_changed=has_python_changes(changed_paths, src_path, exclude=tests_path),
        tests_changed=has_python_changes(changed_paths, tests_path),
    )


def check(
    base_ref: str = "HEAD~1",
    head_ref: str = "HEAD",
    repo_path: Path | None = None,
    src_path: str = "src",
    tests_path: str = "tests",
) -> DiffractResult:
    """Find the public API changes between two git refs and give the possible commit types.

    Args:
        base_ref: The earlier git ref. The default is ``HEAD~1``.
        head_ref: The later git ref. The default is ``HEAD``.
        repo_path: The path of the git repository, or of a directory in it. The
            default is the current working directory.
        src_path: The directory in the repository that contains the Python packages.
        tests_path: The directory in the repository that contains the tests.

    Returns:
        A :class:`~sheridan.diffract.models.DiffractResult` with the group of possible
        commit types, a summary and the full API diff.

    Raises:
        GitError: If diffract cannot find the repository, or if a ref is not correct.
        SurfaceError: If diffract cannot extract the public API at a ref, or if
            ``src_path`` does not exist at the two refs.
    """
    resolved_path = repo_path if repo_path is not None else Path.cwd()
    repo = get_repo(resolved_path)

    base_surface, head_surface = _resolve_surfaces(
        get_api_at_ref(repo, base_ref, src_path=src_path),
        get_api_at_ref(repo, head_ref, src_path=src_path),
        src_path,
        base_ref,
        head_ref,
    )

    diff = diff_surfaces(base_surface, head_surface)
    changed_paths = get_changed_paths(repo, base_ref, head_ref)
    commit_type, summary = _classify_changes(diff, changed_paths, src_path, tests_path)

    return DiffractResult(
        commit_type=commit_type,
        summary=summary,
        diff=diff,
        base_ref=base_ref,
        head_ref=head_ref,
    )


def check_staged(
    repo_path: Path | None = None,
    src_path: str = "src",
    tests_path: str = "tests",
) -> DiffractResult:
    """Find the public API changes between HEAD and the staging area and give the possible types.

    Use this function in a ``commit-msg`` hook, before git makes the commit. The
    function compares the public API at ``HEAD`` with the public API of the files in
    the staging area (the index).

    Args:
        repo_path: The path of the git repository, or of a directory in it. The
            default is the current working directory.
        src_path: The directory in the repository that contains the Python packages.
        tests_path: The directory in the repository that contains the tests.

    Returns:
        A :class:`~sheridan.diffract.models.DiffractResult` with the group of possible
        commit types, a summary and the full API diff. ``base_ref`` is ``"HEAD"`` and ``head_ref``
        is ``":staged"``.

    Raises:
        GitError: If diffract cannot find the repository.
        SurfaceError: If diffract cannot extract the public API of the staging area,
            or if ``src_path`` does not exist at ``HEAD`` and in the staging area.
    """
    resolved_path = repo_path if repo_path is not None else Path.cwd()
    repo = get_repo(resolved_path)

    # Before the first commit, HEAD has no API.
    base = get_api_at_ref(repo, "HEAD", src_path=src_path) if repo.head.is_valid() else {}
    base_surface, head_surface = _resolve_surfaces(
        base,
        get_api_at_index(repo, src_path=src_path),
        src_path,
        "HEAD",
        "the staging area",
    )

    diff = diff_surfaces(base_surface, head_surface)
    changed_paths = get_changed_paths_index(repo)
    commit_type, summary = _classify_changes(diff, changed_paths, src_path, tests_path)

    return DiffractResult(
        commit_type=commit_type,
        summary=summary,
        diff=diff,
        base_ref="HEAD",
        head_ref=":staged",  # This is not a git ref. It is a label for the staging area.
    )
