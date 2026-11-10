"""Tests for sheridan.diffract.enums."""

from __future__ import annotations

from sheridan.diffract.enums import ChangeKind, CommitType


class TestCommitType:
    """Tests for CommitType StrEnum."""

    def test_values(self) -> None:
        """CommitType members must have the correct string values."""
        assert CommitType.feat == "feat"
        assert CommitType.feat_breaking == "feat!"
        assert CommitType.fix == "fix"
        assert CommitType.refactor == "refactor"

    def test_is_str(self) -> None:
        """CommitType members must be usable as plain strings."""
        assert str(CommitType.feat_breaking) == "feat!"

    def test_all_members_present(self) -> None:
        """CommitType must have exactly four members."""
        assert set(CommitType) == {
            CommitType.feat,
            CommitType.feat_breaking,
            CommitType.fix,
            CommitType.refactor,
        }


class TestChangeKind:
    """Tests for ChangeKind StrEnum."""

    def test_values(self) -> None:
        """ChangeKind members must have the correct string values."""
        assert ChangeKind.added == "added"
        assert ChangeKind.removed == "removed"

    def test_all_members_present(self) -> None:
        """ChangeKind must have exactly two members."""
        assert set(ChangeKind) == {ChangeKind.added, ChangeKind.removed}
