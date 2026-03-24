"""Enumerations for sheridan-diffract."""

__all__ = [
    "ChangeKind",
    "CommitType",
]

from enum import StrEnum


class CommitType(StrEnum):
    """Conventional-commit type produced by diffract.

    Attributes:
        feat: A backwards-compatible addition was detected.
        feat_breaking: A breaking change (removal) was detected.
        fix: No API surface changes were detected.
        refactor: Internal Python changes only; public API surface unchanged.
    """

    feat = "feat"
    feat_breaking = "feat!"
    fix = "fix"
    refactor = "refactor"


class ChangeKind(StrEnum):
    """Whether a public name was added or removed.

    Attributes:
        added: The name appeared in head but not in base.
        removed: The name appeared in base but not in head.
    """

    added = "added"
    removed = "removed"
