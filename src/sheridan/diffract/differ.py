"""Compare the public API at two refs."""

__all__ = ["diff_surfaces"]

from sheridan.diffract.enums import ChangeKind
from sheridan.diffract.models import ApiDiff, NameChange


def diff_surfaces(
    base: dict[str, list[str]],
    head: dict[str, list[str]],
) -> ApiDiff:
    """Compare two public APIs and find the added and the removed names.

    The function compares the public names of each module that is in one of the two
    APIs. It sorts the changes by ``(module, name)``.

    Args:
        base: The public API at the earlier ref, as a dict from each module name to
            its public names.
        head: The public API at the later ref, in the same format.

    Returns:
        An :class:`ApiDiff` with a :class:`NameChange` for each added or removed name.
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
