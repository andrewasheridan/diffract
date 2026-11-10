"""High-level API entry point for sheridan-diffract."""

__all__ = ["check", "check_staged"]

from pathlib import Path

from sheridan.diffract.classifier import classify
from sheridan.diffract.differ import diff_surfaces
from sheridan.diffract.exceptions import SurfaceError
from sheridan.diffract.git_utils import (
    get_api_at_index,
    get_api_at_ref,
    get_repo,
    has_python_changes,
    has_python_changes_index,
)
from sheridan.diffract.models import DiffractResult

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


def check(
    base_ref: str = "HEAD~1",
    head_ref: str = "HEAD",
    repo_path: Path | None = None,
    src_path: str = "src",
) -> DiffractResult:
    """Detect API changes between two git refs and classify the commit type.

    Args:
        base_ref: The earlier git ref (default: ``HEAD~1``).
        head_ref: The later git ref (default: ``HEAD``).
        repo_path: Path to (or inside) the git repository. Defaults to the
            current working directory.
        src_path: Subdirectory within the repo to scan for Python packages.

    Returns:
        A :class:`~sheridan.diffract.models.DiffractResult` describing the
        commit type, a human-readable summary, and the full API diff.

    Raises:
        GitError: If the repository cannot be found or either ref is invalid.
        SurfaceError: If API surface extraction fails for either ref, or if
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
    py_changed = has_python_changes(repo, base_ref, head_ref, src_path=src_path)
    commit_type, summary = classify(diff, py_changed)

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
) -> DiffractResult:
    """Detect API changes between HEAD and the git staging area and classify the commit type.

    Intended for use in commit-msg hooks, where the working tree is not yet
    committed. Compares the public API at ``HEAD`` against the public API
    materialised from the current index (staged files).

    Args:
        repo_path: Path to (or inside) the git repository. Defaults to the
            current working directory.
        src_path: Subdirectory within the repo to scan for Python packages.

    Returns:
        A :class:`~sheridan.diffract.models.DiffractResult` describing the
        commit type, a human-readable summary, and the full API diff.
        The ``base_ref`` field is set to ``"HEAD"`` and ``head_ref`` is set
        to ``":staged"``.

    Raises:
        GitError: If the repository cannot be found.
        SurfaceError: If API surface extraction fails for the index, or if
            ``src_path`` does not exist at ``HEAD`` and in the staging area.
    """
    resolved_path = repo_path if repo_path is not None else Path.cwd()
    repo = get_repo(resolved_path)

    # initial commit — no prior surface
    base = get_api_at_ref(repo, "HEAD", src_path=src_path) if repo.head.is_valid() else {}
    base_surface, head_surface = _resolve_surfaces(
        base,
        get_api_at_index(repo, src_path=src_path),
        src_path,
        "HEAD",
        "the staging area",
    )

    diff = diff_surfaces(base_surface, head_surface)
    py_changed = has_python_changes_index(repo, src_path=src_path)
    commit_type, summary = classify(diff, py_changed)

    return DiffractResult(
        commit_type=commit_type,
        summary=summary,
        diff=diff,
        base_ref="HEAD",
        head_ref=":staged",  # sentinel — not a real git ref
    )
