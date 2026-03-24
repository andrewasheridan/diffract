"""API surface diffing for sheridan-diffract."""

from __future__ import annotations

__all__ = ["diff_surfaces"]

from sheridan.diffract.enums import ChangeKind
from sheridan.diffract.models import ApiDiff, NameChange


def diff_surfaces(
    base: dict[str, list[str]],
    head: dict[str, list[str]],
) -> ApiDiff:
    """Compare two API surfaces and return added/removed NameChanges.

    Iterates over every module present in either surface and computes the
    symmetric difference of its public names. Results are sorted by
    ``(module, name)``.

    Args:
        base: The API surface at the earlier ref, as returned by
            ``sheridan.iceberg.get_public_api``.
        head: The API surface at the later ref, as returned by
            ``sheridan.iceberg.get_public_api``.

    Returns:
        An :class:`ApiDiff` containing tuples of :class:`NameChange` objects
        for all names that were added or removed.
    """
    all_modules = set(base) | set(head)
    added: list[NameChange] = []
    removed: list[NameChange] = []

    for module in all_modules:
        base_names = set(base.get(module, []))
        head_names = set(head.get(module, []))

        for name in sorted(head_names - base_names):
            added.append(NameChange(module=module, name=name, kind=ChangeKind.added))

        for name in sorted(base_names - head_names):
            removed.append(NameChange(module=module, name=name, kind=ChangeKind.removed))

    added.sort(key=lambda c: (c.module, c.name))
    removed.sort(key=lambda c: (c.module, c.name))

    return ApiDiff(added=tuple(added), removed=tuple(removed))
