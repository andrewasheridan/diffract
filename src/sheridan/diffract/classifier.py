"""Commit-type classification for sheridan-diffract."""

from __future__ import annotations

__all__ = ["classify"]

from collections import defaultdict

from sheridan.diffract.enums import CommitType
from sheridan.diffract.models import ApiDiff, NameChange


def _group_by_module(changes: tuple[NameChange, ...]) -> dict[str, list[str]]:
    """Group a sequence of NameChanges by their module name.

    Args:
        changes: The name changes to group.

    Returns:
        A dict mapping module name to a sorted list of public names.
    """
    grouped: dict[str, list[str]] = defaultdict(list)
    for change in changes:
        grouped[change.module].append(change.name)
    return {mod: sorted(names) for mod, names in sorted(grouped.items())}


def _format_grouped(changes: tuple[NameChange, ...]) -> str:
    """Format grouped name changes as a multi-line string.

    Args:
        changes: The name changes to format.

    Returns:
        A human-readable string listing each module and its changed names.
    """
    grouped = _group_by_module(changes)
    lines: list[str] = []
    for module, names in grouped.items():
        lines.append(f"{module}: {', '.join(names)}")
    return "; ".join(lines)


def classify(diff: ApiDiff, has_py_changes: bool) -> tuple[CommitType, str]:
    """Map an ApiDiff to a conventional commit type and human-readable summary.

    Rules applied in priority order:

    1. Any removed names -> ``feat!`` (breaking change).
       Summary lists removed names grouped by module.
    2. Any added names -> ``feat``.
       Summary lists added names grouped by module.
    3. No name changes but Python files changed -> ``refactor``.
    4. No changes at all -> ``fix``.

    Args:
        diff: The API diff produced by :func:`sheridan.diffract.differ.diff_surfaces`.
        has_py_changes: Whether any ``.py`` files changed between the two refs.

    Returns:
        A two-tuple of ``(CommitType, summary_string)``.
    """
    if diff.is_breaking:
        summary = f"Breaking: removed public names — {_format_grouped(diff.removed)}"
        return CommitType.feat_breaking, summary

    if diff.has_additions:
        summary = f"Added public names — {_format_grouped(diff.added)}"
        return CommitType.feat, summary

    if has_py_changes:
        return CommitType.refactor, "Internal Python changes; public API surface unchanged."

    return CommitType.fix, "No public API or Python source changes detected."
