"""Get the files and the public API of sheridan-diffract from git."""

__all__ = [
    "get_api_at_index",
    "get_api_at_ref",
    "get_changed_paths",
    "get_changed_paths_index",
    "get_repo",
    "has_python_changes",
]

import tarfile
import tempfile
from collections.abc import Iterable, Iterator
from pathlib import Path, PurePosixPath

from git import BadName, GitCommandError, InvalidGitRepositoryError, Repo

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


_PYTHON_SUFFIXES = (".py", ".pyi")


def _is_in(path: str, directory: str) -> bool:
    """Find if ``path`` is in ``directory``.

    Args:
        path: A path relative to the repository root, as git shows it.
        directory: A directory relative to the repository root. ``"."`` is the root.

    Returns:
        ``True`` if ``path`` is in ``directory`` or in one of its subdirectories.
        ``False`` if not.
    """
    dir_parts = PurePosixPath(directory).parts
    path_parts = PurePosixPath(path).parts
    return path_parts[: len(dir_parts)] == dir_parts


def has_python_changes(paths: Iterable[str], directory: str, exclude: str | None = None) -> bool:
    """Find if one of ``paths`` is a ``.py`` or ``.pyi`` file in ``directory``.

    Use ``exclude`` when the test directory is in the source directory, for example
    ``src/pkg/tests``. Then a change to a test file does not count as a code change.

    Args:
        paths: The changed paths, relative to the repository root, as git shows them.
        directory: The directory to find changes in. ``"."`` is the repository root.
        exclude: A directory in which a changed file does not count, or ``None``.

    Returns:
        ``True`` if one or more paths end with ``.py`` or ``.pyi``, are in
        ``directory`` and are not in ``exclude``. ``False`` if not.
    """
    for path in paths:
        if not path.endswith(_PYTHON_SUFFIXES):
            continue
        if exclude is not None and _is_in(path, exclude):
            continue
        if _is_in(path, directory):
            return True

    return False


def _extract_src(repo: Repo, treeish: str, src_path: str, dest: Path) -> Path | None:
    """Write ``src_path`` of a tree to ``dest`` with ``git archive``.

    The function archives only ``src_path``, not the full repository. Thus a file that
    tar extraction refuses (for example an absolute symbolic link) has no effect when it
    is outside ``src_path``, and a large repository is quick to extract.

    Args:
        repo: The git repository to archive.
        treeish: A commit ref or a tree SHA.
        src_path: The source directory relative to the repository root. ``"."`` is the root.
        dest: An empty directory to write the files to.

    Returns:
        The path of ``src_path`` in ``dest``. ``None`` if ``src_path`` is not in the tree.

    Raises:
        GitError: If ``git archive`` fails or tar extraction refuses a file.
    """
    src = PurePosixPath(src_path)
    pathspec: list[str] = []
    if src.parts:
        pathspec = ["--", str(src)]
        # git archive fails for a pathspec that has no match. Thus find the directory first.
        if not repo.git.ls_tree(treeish, *pathspec):
            return None

    try:
        proc = repo.git.archive(treeish, *pathspec, format="tar", as_process=True)
        with tarfile.open(fileobj=proc.stdout, mode="r|") as tar:
            tar.extractall(dest, filter="data")
        proc.wait()
    except (GitCommandError, tarfile.TarError) as exc:
        raise GitError(f"Cannot extract {src_path!r} at {treeish!r}: {exc}") from exc

    api_root = dest / src
    if not api_root.is_dir():
        return None

    return api_root


def get_repo(path: Path) -> Repo:
    """Find the git repository at ``path`` or in a parent directory of ``path``.

    Args:
        path: The root of the git repository, or a path in it.

    Returns:
        The ``git.Repo`` of the repository.

    Raises:
        GitError: If there is no git repository at or above ``path``.
    """
    try:
        return Repo(str(path), search_parent_directories=True)
    except InvalidGitRepositoryError as exc:
        raise GitError(f"Cannot find a git repository at or above {path}") from exc


def get_api_at_ref(repo: Repo, ref: str, src_path: str = "src") -> dict[str, list[str]] | None:
    """Extract the public API at a git ref.

    The function uses ``git archive`` to write only ``src_path`` to a temporary
    directory. Then it calls ``sheridan.iceberg.get_public_api()`` on that directory.
    To read the repository root, use ``"."``.

    Args:
        repo: The git repository to archive.
        ref: The git ref (a branch, a tag or a commit SHA) to read.
        src_path: The directory in the repository that contains the Python packages.

    Returns:
        A dict from each full module name to its sorted public names. The module names
        are relative to ``src_path``. ``None`` if ``src_path`` does not exist at ``ref``.

    Raises:
        GitError: If ``ref`` is not a ref in the repository, or if ``git archive`` or
            the tar extraction fails.
        SurfaceError: If ``get_public_api`` raises an exception.
    """
    # Check the ref first to give a clear error message.
    try:
        repo.commit(ref)
    except BadName as exc:
        raise GitError(f"The ref does not exist: {ref}") from exc

    with tempfile.TemporaryDirectory() as tmp:
        api_root = _extract_src(repo, ref, src_path, Path(tmp))
        if api_root is None:
            return None

        try:
            return _read_api(api_root)
        except Exception as exc:
            raise SurfaceError(f"Cannot extract the public API at ref {ref!r}: {exc}") from exc


def get_changed_paths(repo: Repo, base_ref: str, head_ref: str) -> list[str]:
    """Get the paths of the files that changed between the two refs.

    For a renamed file, the list has the old path and the new path.

    Args:
        repo: The git repository.
        base_ref: The earlier git ref.
        head_ref: The later git ref.

    Returns:
        The changed paths, relative to the repository root.
    """
    base_commit = repo.commit(base_ref)
    head_commit = repo.commit(head_ref)

    paths: list[str] = []
    for d in base_commit.diff(head_commit):
        paths.extend(path for path in (d.a_path, d.b_path) if path)

    return paths


def get_api_at_index(repo: Repo, src_path: str = "src") -> dict[str, list[str]] | None:
    """Extract the public API from the git staging area (the index).

    The function writes the staged tree with ``git write-tree``. Then it uses
    ``git archive`` on that tree to write only ``src_path`` to a temporary directory.
    Then it calls ``sheridan.iceberg.get_public_api()`` on that directory.

    Args:
        repo: The git repository. The function reads its staging area.
        src_path: The directory in the repository that contains the Python packages.

    Returns:
        A dict from each full module name to its sorted public names. The module names
        are relative to ``src_path``. ``None`` if ``src_path`` does not exist in the
        staging area.

    Raises:
        GitError: If ``git archive`` or the tar extraction fails.
        SurfaceError: If ``get_public_api`` raises an exception.

    Notes:
        For ``git commit -a`` and ``git commit <paths>``, git gives the hooks a
        temporary index in ``GIT_INDEX_FILE``. The ``git`` command obeys this
        variable, but GitPython's ``IndexFile`` reads ``.git/index``. Thus this
        function uses the command. It does not write ``.git/index``.
    """
    tree_sha: str = repo.git.write_tree()

    with tempfile.TemporaryDirectory() as tmp:
        api_root = _extract_src(repo, tree_sha, src_path, Path(tmp))
        if api_root is None:
            return None

        try:
            return _read_api(api_root)
        except Exception as exc:
            raise SurfaceError(f"Cannot extract the public API from the staging area: {exc}") from exc


def get_changed_paths_index(repo: Repo) -> list[str]:
    """Get the paths of the files that changed between HEAD and the staging area.

    The function uses ``git diff --cached``, which obeys ``GIT_INDEX_FILE`` (see
    ``get_api_at_index``). Before the first commit, the repository has no HEAD commit.
    Then all the files in the staging area are new, and the function gives all of them.

    Args:
        repo: The git repository.

    Returns:
        The changed paths, relative to the repository root.
    """
    if not repo.head.is_valid():
        output: str = repo.git.ls_files()
        return output.splitlines()

    # With --no-renames, git shows a renamed file as a deletion of the old path and an
    # addition of the new path. Thus the list has the two paths.
    output = repo.git.diff("--cached", "--name-only", "--no-renames", "HEAD")
    return output.splitlines()
