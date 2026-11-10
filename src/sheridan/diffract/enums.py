"""The enumerations of sheridan-diffract."""

__all__ = [
    "ChangeKind",
    "CommitType",
]

from enum import StrEnum


class CommitType(StrEnum):
    """The Conventional Commit type that diffract gives.

    Attributes:
        feat: A public name was added, and no public name was removed.
        feat_breaking: A public name was removed. This is a breaking change.
        fix: The public API did not change, and no Python file changed.
        refactor: Python files changed, but the public API did not change.
    """

    feat = "feat"
    feat_breaking = "feat!"
    fix = "fix"
    refactor = "refactor"


class ChangeKind(StrEnum):
    """Whether a public name was added or removed.

    Attributes:
        added: The name is in head but not in base.
        removed: The name is in base but not in head.
    """

    added = "added"
    removed = "removed"
