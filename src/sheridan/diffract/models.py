"""Data models for sheridan-diffract."""

from __future__ import annotations

__all__ = ["ApiDiff", "DiffractResult", "NameChange"]

from dataclasses import dataclass

from sheridan.diffract.enums import ChangeKind, CommitType


@dataclass(frozen=True)
class NameChange:
    """A single public name that was added or removed from a module.

    Attributes:
        module: Qualified module name, e.g. ``"sheridan.diffract.enums"``.
        name: The public identifier, e.g. ``"CommitType"``.
        kind: Whether the name was added or removed.
    """

    module: str
    name: str
    kind: ChangeKind


@dataclass(frozen=True)
class ApiDiff:
    """The complete difference between two API surfaces.

    Attributes:
        added: Public names present in head but not in base.
        removed: Public names present in base but not in head.
    """

    added: tuple[NameChange, ...]
    removed: tuple[NameChange, ...]

    @property
    def is_breaking(self) -> bool:
        """Return True if any public names were removed."""
        return bool(self.removed)

    @property
    def has_additions(self) -> bool:
        """Return True if any public names were added."""
        return bool(self.added)

    @property
    def is_empty(self) -> bool:
        """Return True if no public names were added or removed."""
        return not self.added and not self.removed


@dataclass(frozen=True)
class DiffractResult:
    """The complete output of a diffract check.

    Attributes:
        commit_type: The conventional-commit type inferred from the diff.
        summary: A human-readable description of the changes.
        diff: The full API diff between base and head.
        base_ref: The earlier git ref that was compared.
        head_ref: The later git ref that was compared.
    """

    commit_type: CommitType
    summary: str
    diff: ApiDiff
    base_ref: str
    head_ref: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable representation of this result.

        Returns:
            A dict with keys ``commit_type``, ``summary``, ``base_ref``,
            ``head_ref``, and ``diff`` (which contains ``added`` and
            ``removed`` lists of ``{"module": ..., "name": ...}`` dicts).
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
