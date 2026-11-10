"""The data classes of sheridan-diffract."""

__all__ = ["ApiDiff", "DiffractResult", "NameChange", "SignatureChange"]

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
class SignatureChange:
    """One change to a public name that is in base and in head.

    Attributes:
        module: The full module name, for example ``"sheridan.diffract.enums"``.
        name: The public name, for example ``"check"`` or ``"ApiDiff.is_empty"``.
        detail: What changed, for example ``"parameter 'ref' was removed"``.
        is_breaking: True if the change can stop code that uses the name. False if
            the change only adds to the name, for example a new optional parameter.
    """

    module: str
    name: str
    detail: str
    is_breaking: bool


@dataclass(frozen=True)
class ApiDiff:
    """All the differences between two public APIs.

    Attributes:
        added: The public names that are in head but not in base. A name in a class
            has the class name in front of it, for example ``"ApiDiff.changed"``.
        removed: The public names that are in base but not in head, in the same
            format.
        changed: The changes to the signatures, the bases and the kinds of the public
            names that are in base and in head.
    """

    added: tuple[NameChange, ...]
    removed: tuple[NameChange, ...]
    changed: tuple[SignatureChange, ...] = ()

    @property
    def breaking_changes(self) -> tuple[SignatureChange, ...]:
        """The changes in ``changed`` that can stop code that uses the name."""
        return tuple(change for change in self.changed if change.is_breaking)

    @property
    def additive_changes(self) -> tuple[SignatureChange, ...]:
        """The changes in ``changed`` that only add to the name."""
        return tuple(change for change in self.changed if not change.is_breaking)

    @property
    def is_breaking(self) -> bool:
        """True if a public name was removed or had a breaking change."""
        return bool(self.removed or self.breaking_changes)

    @property
    def has_additions(self) -> bool:
        """True if a public name was added or had a change that only adds to it."""
        return bool(self.added or self.additive_changes)

    @property
    def is_empty(self) -> bool:
        """True if no public name was added, removed or changed."""
        return not self.added and not self.removed and not self.changed


@dataclass(frozen=True)
class DiffractResult:
    """All the output of a diffract check.

    Attributes:
        commit_type: The group of Conventional Commit types that diffract gives for
            the diff. ``commit_type.possible_types`` gives the types in the group.
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
            A dict with the keys ``group``, ``possible_types``, ``summary``,
            ``base_ref``, ``head_ref`` and ``diff``. ``group`` is the value of
            ``commit_type``. ``possible_types`` is a list of the types in that group.
            ``diff`` has the keys ``added``, ``removed`` and ``changed``. ``added``
            and ``removed`` are lists of ``{"module": ..., "name": ...}`` dicts.
            ``changed`` is a list of ``{"module": ..., "name": ..., "detail": ...,
            "breaking": ...}`` dicts.
        """
        return {
            "group": str(self.commit_type),
            "possible_types": list(self.commit_type.possible_types),
            "summary": self.summary,
            "base_ref": self.base_ref,
            "head_ref": self.head_ref,
            "diff": {
                "added": [{"module": c.module, "name": c.name} for c in self.diff.added],
                "removed": [{"module": c.module, "name": c.name} for c in self.diff.removed],
                "changed": [
                    {"module": c.module, "name": c.name, "detail": c.detail, "breaking": c.is_breaking}
                    for c in self.diff.changed
                ],
            },
        }
