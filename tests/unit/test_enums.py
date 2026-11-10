"""Tests for sheridan.diffract.enums."""

from sheridan.diffract.enums import ChangeKind, CommitType


class TestCommitType:
    """Tests for the CommitType StrEnum."""

    def test_values(self) -> None:
        """CommitType members must have the correct string values."""
        assert CommitType.feat == "feat"
        assert CommitType.feat_breaking == "feat!"
        assert CommitType.code == "code"
        assert CommitType.test == "test"
        assert CommitType.other == "other"

    def test_is_str(self) -> None:
        """You must be able to use CommitType members as strings."""
        assert str(CommitType.feat_breaking) == "feat!"

    def test_all_members_present(self) -> None:
        """CommitType must have exactly five members."""
        assert set(CommitType) == {
            CommitType.feat,
            CommitType.feat_breaking,
            CommitType.code,
            CommitType.test,
            CommitType.other,
        }

    def test_possible_types(self) -> None:
        """Each group must give the Conventional Commit types that are possible for it."""
        assert CommitType.feat_breaking.possible_types == ("feat!",)
        assert CommitType.feat.possible_types == ("feat",)
        assert CommitType.code.possible_types == ("fix", "refactor", "perf", "style")
        assert CommitType.test.possible_types == ("test",)
        assert CommitType.other.possible_types == ("docs", "ci", "chore", "build")


class TestChangeKind:
    """Tests for the ChangeKind StrEnum."""

    def test_values(self) -> None:
        """ChangeKind members must have the correct string values."""
        assert ChangeKind.added == "added"
        assert ChangeKind.removed == "removed"

    def test_all_members_present(self) -> None:
        """ChangeKind must have exactly two members."""
        assert set(ChangeKind) == {ChangeKind.added, ChangeKind.removed}
