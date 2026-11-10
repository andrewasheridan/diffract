"""The data classes of sheridan-diffract."""

__all__ = ["ApiDiff", "DiffractResult", "NameChange"]

from dataclasses import dataclass

from sheridan.diffract.enums import ChangeKind, CommitType


@dataclass(frozen=True)
class NameChange:
    """One public name that was added to a module or removed from a module.

    Attributes:
        module: The full module name, for example ``"sheridan.diffract.enums"``.
        name: The public name, for example ``"CommitType"``.
        kind: Tells if the name was added or removed.
    """

    module: str
    name: str
    kind: ChangeKind


@dataclass(frozen=True)
class ApiDiff:
    """All the differences between two public APIs.

    Attributes:
        added: The public names that are in head but not in base.
        removed: The public names that are in base but not in head.
    """

    added: tuple[NameChange, ...]
    removed: tuple[NameChange, ...]

    @property
    def is_breaking(self) -> bool:
        """True if one or more public names were removed."""
        return bool(self.removed)

    @property
    def has_additions(self) -> bool:
        """True if one or more public names were added."""
        return bool(self.added)

    @property
    def is_empty(self) -> bool:
        """True if no public names were added or removed."""
        return not self.added and not self.removed


@dataclass(frozen=True)
class DiffractResult:
    """All the output of a diffract check.

    Attributes:
        commit_type: The Conventional Commit type that diffract gives for the diff.
        summary: A short description of the changes.
        diff: The full API diff between base and head.
        base_ref: The earlier git ref of the comparison.
        head_ref: The later git ref of the comparison.
    """

    commit_type: CommitType
    summary: str
    diff: ApiDiff
    base_ref: str
    head_ref: str

    def to_dict(self) -> dict[str, object]:
        """Convert this result to a dict that ``json.dumps`` can write.

        Returns:
            A dict with the keys ``commit_type``, ``summary``, ``base_ref``,
            ``head_ref`` and ``diff``. ``diff`` has the keys ``added`` and
            ``removed``. Each is a list of ``{"module": ..., "name": ...}`` dicts.
        """
        return {
            "commit_type": str(self.commit_type),
            "summary": self.summary,
            "base_ref": self.base_ref,
            "head_ref": self.head_ref,
            "diff": {
                "added": [{"module": c.module, "name": c.name} for c in self.diff.added],
                "removed": [{"module": c.module, "name": c.name} for c in self.diff.removed],
            },
        }
