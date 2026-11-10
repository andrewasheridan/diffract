"""Give the Conventional Commit type for an API diff."""

__all__ = ["classify"]

from collections import defaultdict

from sheridan.diffract.enums import CommitType
from sheridan.diffract.models import ApiDiff, NameChange


def group_by_module(changes: tuple[NameChange, ...]) -> dict[str, list[str]]:
    """Group the name changes by module name.

    The summary of ``classify`` and the CLI output use this function.

    Args:
        changes: The name changes to group.

    Returns:
        A dict from each module name to the sorted public names of that module.
    """
    grouped: dict[str, list[str]] = defaultdict(list)
    for change in changes:
        grouped[change.module].append(change.name)
    return {mod: sorted(names) for mod, names in sorted(grouped.items())}


def _format_grouped(changes: tuple[NameChange, ...]) -> str:
    """Write the name changes as one line, grouped by module.

    Args:
        changes: The name changes to write.

    Returns:
        Each module and its changed names, for example ``"pkg.a: x, y; pkg.b: z"``.
    """
    grouped = group_by_module(changes)
    lines: list[str] = []
    for module, names in grouped.items():
        lines.append(f"{module}: {', '.join(names)}")
    return "; ".join(lines)


def classify(diff: ApiDiff, has_py_changes: bool) -> tuple[CommitType, str]:
    """Give the Conventional Commit type and a summary for an API diff.

    The rules, in order of priority:

    1. A public name was removed: ``feat!`` (a breaking change). The summary gives
       the removed names, grouped by module.
    2. A public name was added: ``feat``. The summary gives the added names, grouped
       by module.
    3. No name changed, but Python files in the source directory changed: ``refactor``.
    4. No change: ``fix``.

    Args:
        diff: The API diff from :func:`sheridan.diffract.differ.diff_surfaces`.
        has_py_changes: True if ``.py`` or ``.pyi`` files in the source directory
            changed between the two refs.

    Returns:
        The commit type and the summary.
    """
    if diff.is_breaking:
        summary = f"Breaking change. Removed public names: {_format_grouped(diff.removed)}"
        return CommitType.feat_breaking, summary

    if diff.has_additions:
        summary = f"Added public names: {_format_grouped(diff.added)}"
        return CommitType.feat, summary

    if has_py_changes:
        return CommitType.refactor, "Python files changed. The public API did not change."

    return CommitType.fix, "The public API and the Python files did not change."
