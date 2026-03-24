"""Git interaction utilities for sheridan-diffract."""

from __future__ import annotations

__all__ = [
    "get_api_at_index",
    "get_api_at_ref",
    "get_repo",
    "has_python_changes",
    "has_python_changes_index",
]

import tarfile
import tempfile
from pathlib import Path

from git import BadName, InvalidGitRepositoryError, Repo

from sheridan.diffract.exceptions import GitError, SurfaceError
from sheridan.iceberg import get_public_api


def get_repo(path: Path) -> Repo:
    """Find and return the git Repo at or above path.

    Args:
        path: A path inside (or equal to) the git repository root.

    Returns:
        The ``git.Repo`` instance for the repository.

    Raises:
        GitError: If no git repository is found at or above ``path``.
    """
    try:
        return Repo(str(path), search_parent_directories=True)
    except InvalidGitRepositoryError as exc:
        raise GitError(f"No git repository found at or above: {path}") from exc


def get_api_at_ref(repo: Repo, ref: str, src_path: str = "src") -> dict[str, list[str]]:
    """Extract the public API surface at a given git ref.

    Uses ``git archive`` to extract the repository tree into a temporary
    directory, then invokes ``sheridan.iceberg.get_public_api()`` on the
    ``src_path`` subdirectory (or the temp root if that subdirectory does
    not exist).

    Args:
        repo: The git repository to archive.
        ref: The git ref (branch, tag, or commit SHA) to check out.
        src_path: Relative path within the repo that contains Python packages.

    Returns:
        A mapping of fully-qualified module name to list of public names,
        as returned by ``sheridan.iceberg.get_public_api``.

    Raises:
        GitError: If ``ref`` is not a valid ref in the repository.
        SurfaceError: If ``get_public_api`` raises any exception.
    """
    # Validate the ref early so we can give a clear error message.
    try:
        repo.commit(ref)
    except BadName as exc:
        raise GitError(f"Unknown ref: {ref}") from exc

    with tempfile.TemporaryDirectory() as tmp:
        proc = repo.git.archive(ref, format="tar", as_process=True)
        with tarfile.open(fileobj=proc.stdout, mode="r|") as tar:
            tar.extractall(tmp, filter="data")
        proc.wait()

        api_root = Path(tmp) / src_path
        if not api_root.exists():
            api_root = Path(tmp)

        try:
            return get_public_api(api_root)
        except Exception as exc:
            raise SurfaceError(f"Failed to extract public API at ref {ref!r}: {exc}") from exc


def has_python_changes(repo: Repo, base_ref: str, head_ref: str) -> bool:
    """Return True if any ``.py`` files differ between base_ref and head_ref.

    Args:
        repo: The git repository to inspect.
        base_ref: The earlier git ref.
        head_ref: The later git ref.

    Returns:
        ``True`` if at least one ``.py`` file appears in the diff,
        ``False`` otherwise.
    """
    base_commit = repo.commit(base_ref)
    head_commit = repo.commit(head_ref)
    diffs = base_commit.diff(head_commit)
    for d in diffs:
        a_path: str = d.a_path or ""
        b_path: str = d.b_path or ""
        if a_path.endswith(".py") or b_path.endswith(".py"):
            return True
    return False


def get_api_at_index(repo: Repo, src_path: str = "src") -> dict[str, list[str]]:
    """Extract the public API surface from the current git staging area (index).

    Materialises the staged tree via ``repo.index.write_tree()``, then uses
    ``git archive`` on the resulting tree SHA to extract files into a temporary
    directory before invoking ``sheridan.iceberg.get_public_api()``.

    Args:
        repo: The git repository whose index (staging area) to inspect.
        src_path: Relative path within the repo that contains Python packages.

    Returns:
        A mapping of fully-qualified module name to list of public names,
        as returned by ``sheridan.iceberg.get_public_api``.

    Raises:
        GitError: If tree materialisation or archive extraction fails.
        SurfaceError: If ``get_public_api`` raises any exception.

    Notes:
        ``write_tree()`` flushes the in-memory index to ``.git/index`` as a
        side effect before returning the tree object.
    """
    tree = repo.index.write_tree()
    tree_sha: str = tree.hexsha

    with tempfile.TemporaryDirectory() as tmp:
        proc = repo.git.archive(tree_sha, format="tar", as_process=True)
        with tarfile.open(fileobj=proc.stdout, mode="r|") as tar:
            tar.extractall(tmp, filter="data")
        proc.wait()

        api_root = Path(tmp) / src_path
        if not api_root.exists():
            api_root = Path(tmp)

        try:
            return get_public_api(api_root)
        except Exception as exc:
            raise SurfaceError(f"Failed to extract public API from index: {exc}") from exc


def has_python_changes_index(repo: Repo) -> bool:
    """Return True if any ``.py`` files differ between HEAD and the staging area.

    Compares the current HEAD commit against the git index (staging area).
    If the repository has no HEAD commit (initial commit edge case), returns
    ``True`` to conservatively assume changes exist.

    Args:
        repo: The git repository to inspect.

    Returns:
        ``True`` if at least one ``.py`` file appears in the diff between HEAD
        and the index, or if no HEAD commit exists. ``False`` otherwise.
    """
    try:
        diffs = repo.head.commit.diff(index=True)
    except ValueError:  # repo.head.commit raises ValueError when HEAD is unborn (initial commit)
        return True
    for d in diffs:
        a_path: str = d.a_path or ""
        b_path: str = d.b_path or ""
        if a_path.endswith(".py") or b_path.endswith(".py"):
            return True
    return False
