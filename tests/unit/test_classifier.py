"""Tests for sheridan.diffract.classifier."""

from sheridan.diffract.classifier import classify
from sheridan.diffract.enums import CommitType
from sheridan.diffract.models import ApiDiff


class TestClassify:
    """Tests for classify()."""

    def test_removed_names_produce_feat_breaking(self, removal_diff: ApiDiff) -> None:
        """Removed public names must give CommitType.feat_breaking."""
        commit_type, summary = classify(removal_diff, has_py_changes=True)
        assert commit_type == CommitType.feat_breaking
        assert "removed" in summary.lower() or "breaking" in summary.lower()

    def test_added_names_produce_feat(self, addition_diff: ApiDiff) -> None:
        """Added public names and no removed names must give CommitType.feat."""
        commit_type, _ = classify(addition_diff, has_py_changes=True)
        assert commit_type == CommitType.feat

    def test_no_api_change_with_py_changes_produces_refactor(self, empty_diff: ApiDiff) -> None:
        """No API change but changed Python files must give CommitType.refactor."""
        commit_type, _ = classify(empty_diff, has_py_changes=True)
        assert commit_type == CommitType.refactor

    def test_no_changes_at_all_produces_fix(self, empty_diff: ApiDiff) -> None:
        """No API change and no Python file change must give CommitType.fix."""
        commit_type, _ = classify(empty_diff, has_py_changes=False)
        assert commit_type == CommitType.fix

    def test_removal_takes_priority_over_addition(self, mixed_diff: ApiDiff) -> None:
        """A removed name must have priority over an added name."""
        commit_type, _ = classify(mixed_diff, has_py_changes=False)
        assert commit_type == CommitType.feat_breaking

    def test_summary_is_always_a_non_empty_string(self, empty_diff: ApiDiff) -> None:
        """classify must always give a summary that is not empty."""
        _, summary = classify(empty_diff, has_py_changes=False)
        assert isinstance(summary, str)
        assert summary

    def test_breaking_summary_names_the_removed_symbols(self, removal_diff: ApiDiff) -> None:
        """The breaking summary must give the removed public name."""
        _, summary = classify(removal_diff, has_py_changes=False)
        assert "OldClass" in summary

    def test_feat_summary_names_the_added_symbols(self, addition_diff: ApiDiff) -> None:
        """The feat summary must give the added public name."""
        _, summary = classify(addition_diff, has_py_changes=False)
        assert "NewClass" in summary


class TestSummaryText:
    """Tests for the full text of each summary."""

    def test_breaking_summary(self, removal_diff: ApiDiff) -> None:
        _, summary = classify(removal_diff, has_py_changes=False)
        assert summary == "Breaking change. Removed public names: mypackage.mod: OldClass"

    def test_feat_summary(self, addition_diff: ApiDiff) -> None:
        _, summary = classify(addition_diff, has_py_changes=False)
        assert summary == "Added public names: mypackage.mod: NewClass"

    def test_refactor_summary(self, empty_diff: ApiDiff) -> None:
        _, summary = classify(empty_diff, has_py_changes=True)
        assert summary == "Python files changed. The public API did not change."

    def test_fix_summary(self, empty_diff: ApiDiff) -> None:
        _, summary = classify(empty_diff, has_py_changes=False)
        assert summary == "The public API and the Python files did not change."
