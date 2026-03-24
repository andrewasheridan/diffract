"""High-level API entry point for sheridan-diffract."""

from __future__ import annotations

__all__ = ["check"]

from pathlib import Path

from sheridan.diffract.classifier import classify
from sheridan.diffract.differ import diff_surfaces
from sheridan.diffract.git_utils import get_api_at_ref, get_repo, has_python_changes
from sheridan.diffract.models import DiffractResult


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
        SurfaceError: If API surface extraction fails for either ref.
    """
    resolved_path = repo_path if repo_path is not None else Path.cwd()
    repo = get_repo(resolved_path)

    base_surface = get_api_at_ref(repo, base_ref, src_path=src_path)
    head_surface = get_api_at_ref(repo, head_ref, src_path=src_path)

    diff = diff_surfaces(base_surface, head_surface)
    py_changed = has_python_changes(repo, base_ref, head_ref)
    commit_type, summary = classify(diff, py_changed)

    return DiffractResult(
        commit_type=commit_type,
        summary=summary,
        diff=diff,
        base_ref=base_ref,
        head_ref=head_ref,
    )
