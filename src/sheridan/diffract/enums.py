"""The enumerations of sheridan-diffract."""

__all__ = [
    "ChangeKind",
    "CommitType",
]

from enum import StrEnum


class CommitType(StrEnum):
    """The group of Conventional Commit types that diffract gives.

    diffract compares only the public names and the changed files. Thus it cannot
    always find one type. For example, it cannot tell a fix from a refactor. It gives
    the group of types that are possible for the change.

    Attributes:
        feat_breaking: A public name was removed. This is a breaking change.
        feat: A public name was added, and no public name was removed.
        code: No public name changed, but Python files in the source directory changed.
        test: No public name changed, and only Python files in the test directory
            changed.
        other: No public name changed, and no Python file in the source directory or
            in the test directory changed.
    """

    feat_breaking = "feat!"
    feat = "feat"
    code = "code"
    test = "test"
    other = "other"

    @property
    def possible_types(self) -> tuple[str, ...]:
        """The Conventional Commit types that are possible for this group."""
        return _POSSIBLE_TYPES[self]


_POSSIBLE_TYPES: dict[CommitType, tuple[str, ...]] = {
    CommitType.feat_breaking: ("feat!",),
    CommitType.feat: ("feat",),
    CommitType.code: ("fix", "refactor", "perf", "style"),
    CommitType.test: ("test",),
    CommitType.other: ("docs", "ci", "chore", "build"),
}


class ChangeKind(StrEnum):
    """Whether a public name was added or removed.

    Attributes:
        added: The name is in head but not in base.
        removed: The name is in base but not in head.
    """

    added = "added"
    removed = "removed"
