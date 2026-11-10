"""Git interaction utilities for sheridan-diffract."""

__all__ = [
    "get_api_at_index",
    "get_api_at_ref",
    "get_repo",
    "has_python_changes",
    "has_python_changes_index",
]

import tarfile
import tempfile
from collections.abc import Iterator
from pathlib import Path

from git import BadName, InvalidGitRepositoryError, Repo

from sheridan.diffract.exceptions import GitError, SurfaceError
from sheridan.iceberg import Module, Package, get_public_api


def _iter_modules(api: Package | Module) -> Iterator[Module]:
    """Find each module in an iceberg API tree, depth first.

    Args:
        api: The tree that ``sheridan.iceberg.get_public_api`` makes.

    Yields:
        Each ``Module`` in the tree.
    """
    if isinstance(api, Module):
        yield api
        return

    yield from api.modules
    for subpackage in api.subpackages:
        yield from _iter_modules(subpackage)


def _module_names(module: Module) -> list[str]:
    """Collect the public names of one module, sorted.

    Args:
        module: An iceberg ``Module``.

    Returns:
        The names of the assignments, classes, functions and unresolved references.
    """
    members = (*module.assignments, *module.classes, *module.functions, *module.references)
    return sorted(member.name for member in members)


def _read_api(api_root: Path) -> dict[str, list[str]]:
    """Extract the public API below ``api_root`` as a map of module names to public names.

    iceberg puts the name of ``api_root`` in front of each module name. If ``api_root`` is
    not a package (it has no ``__init__.py``), the function removes that prefix. Thus, the
    module names do not change with the name of the source directory or of a temporary
    directory.

    Args:
        api_root: The directory that contains the Python packages.

    Returns:
        A map of each dotted module name to its sorted public names.
    """
    api = get_public_api(api_root)
    prefix = "" if (api_root / "__init__.py").exists() else f"{api_root.name}."

    surface: dict[str, list[str]] = {}
    for module in _iter_modules(api):
        name = module.name.removeprefix(prefix)
        surface[name] = _module_names(module)

    return surface


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
        sorted. The module names are relative to ``src_path``.

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
            return _read_api(api_root)
        except Exception as exc:
            raise SurfaceError(f"Failed to extract public API at ref {ref!r}: {exc}") from exc


def has_python_changes(repo: Repo, base_ref: str, head_ref: str) -> bool:
    """Check if any ``.py`` files differ between base_ref and head_ref.

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

    Writes the staged tree with ``git write-tree``, then uses ``git archive`` on the
    resulting tree SHA to extract files into a temporary directory before invoking
    ``sheridan.iceberg.get_public_api()``.

    Args:
        repo: The git repository whose index (staging area) to inspect.
        src_path: Relative path within the repo that contains Python packages.

    Returns:
        A mapping of fully-qualified module name to list of public names,
        sorted. The module names are relative to ``src_path``.

    Raises:
        GitError: If tree materialisation or archive extraction fails.
        SurfaceError: If ``get_public_api`` raises any exception.

    Notes:
        For ``git commit -a`` and ``git commit <paths>``, git gives the hooks a
        temporary index in ``GIT_INDEX_FILE``. The ``git`` command obeys this
        variable, but GitPython's ``IndexFile`` reads ``.git/index``. Thus this
        function uses the command. It does not write ``.git/index``.
    """
    tree_sha: str = repo.git.write_tree()

    with tempfile.TemporaryDirectory() as tmp:
        proc = repo.git.archive(tree_sha, format="tar", as_process=True)
        with tarfile.open(fileobj=proc.stdout, mode="r|") as tar:
            tar.extractall(tmp, filter="data")
        proc.wait()

        api_root = Path(tmp) / src_path
        if not api_root.exists():
            api_root = Path(tmp)

        try:
            return _read_api(api_root)
        except Exception as exc:
            raise SurfaceError(f"Failed to extract public API from index: {exc}") from exc


def has_python_changes_index(repo: Repo) -> bool:
    """Check if any ``.py`` files differ between HEAD and the staging area.

    Compares the current HEAD commit against the git index (staging area) with
    ``git diff --cached``, which obeys ``GIT_INDEX_FILE`` (see ``get_api_at_index``).
    If the repository has no HEAD commit (initial commit edge case), returns
    ``True`` to conservatively assume changes exist.

    Args:
        repo: The git repository to inspect.

    Returns:
        ``True`` if at least one ``.py`` file appears in the diff between HEAD
        and the index, or if no HEAD commit exists. ``False`` otherwise.
    """
    if not repo.head.is_valid():
        return True

    # Without --no-renames, a renamed file shows only its new path.
    output: str = repo.git.diff("--cached", "--name-only", "--no-renames", "HEAD")
    return any(path.endswith(".py") for path in output.splitlines())
