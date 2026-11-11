"""Tests for sheridan.diffract._classifier."""

from sheridan.diffract._classifier import classify
from sheridan.diffract._enums import CommitType
from sheridan.diffract._models import ApiDiff, SignatureChange


class TestClassify:
    """Tests for classify()."""

    def test_removed_names_produce_feat_breaking(self, removal_diff: ApiDiff) -> None:
        """Removed public names must give CommitType.feat_breaking."""
        commit_type, summary = classify(removal_diff, code_changed=True, tests_changed=True)
        assert commit_type == CommitType.feat_breaking
        assert "removed" in summary.lower() or "breaking" in summary.lower()

    def test_added_names_produce_feat(self, addition_diff: ApiDiff) -> None:
        """Added public names and no removed names must give CommitType.feat."""
        commit_type, _ = classify(addition_diff, code_changed=True, tests_changed=True)
        assert commit_type == CommitType.feat

    def test_source_changes_produce_code(self, empty_diff: ApiDiff) -> None:
        """No API change but changed source files must give CommitType.code."""
        commit_type, _ = classify(empty_diff, code_changed=True, tests_changed=False)
        assert commit_type == CommitType.code

    def test_source_and_test_changes_produce_code(self, empty_diff: ApiDiff) -> None:
        """A change to the source files must have priority over a change to the test files."""
        commit_type, _ = classify(empty_diff, code_changed=True, tests_changed=True)
        assert commit_type == CommitType.code

    def test_only_test_changes_produce_test(self, empty_diff: ApiDiff) -> None:
        """No API change and changed test files only must give CommitType.test."""
        commit_type, _ = classify(empty_diff, code_changed=False, tests_changed=True)
        assert commit_type == CommitType.test

    def test_no_python_changes_produce_other(self, empty_diff: ApiDiff) -> None:
        """No API change and no changed source or test files must give CommitType.other."""
        commit_type, _ = classify(empty_diff, code_changed=False, tests_changed=False)
        assert commit_type == CommitType.other

    def test_addition_takes_priority_over_code(self, addition_diff: ApiDiff) -> None:
        """An added name must have priority over changed source files."""
        commit_type, _ = classify(addition_diff, code_changed=True, tests_changed=True)
        assert commit_type == CommitType.feat

    def test_removal_takes_priority_over_addition(self, mixed_diff: ApiDiff) -> None:
        """A removed name must have priority over an added name."""
        commit_type, _ = classify(mixed_diff, code_changed=False, tests_changed=False)
        assert commit_type == CommitType.feat_breaking

    def test_summary_is_always_a_non_empty_string(self, empty_diff: ApiDiff) -> None:
        """classify must always give a summary that is not empty."""
        _, summary = classify(empty_diff, code_changed=False, tests_changed=False)
        assert isinstance(summary, str)
        assert summary

    def test_breaking_summary_names_the_removed_symbols(self, removal_diff: ApiDiff) -> None:
        """The breaking summary must give the removed public name."""
        _, summary = classify(removal_diff, code_changed=False, tests_changed=False)
        assert "OldClass" in summary

    def test_feat_summary_names_the_added_symbols(self, addition_diff: ApiDiff) -> None:
        """The feat summary must give the added public name."""
        _, summary = classify(addition_diff, code_changed=False, tests_changed=False)
        assert "NewClass" in summary


class TestSummaryText:
    """Tests for the full text of each summary."""

    def test_breaking_summary(self, removal_diff: ApiDiff) -> None:
        _, summary = classify(removal_diff, code_changed=False, tests_changed=False)
        assert summary == "Breaking change. Removed public names: mypackage.mod: OldClass"

    def test_feat_summary(self, addition_diff: ApiDiff) -> None:
        _, summary = classify(addition_diff, code_changed=False, tests_changed=False)
        assert summary == "Added public names: mypackage.mod: NewClass"

    def test_code_summary(self, empty_diff: ApiDiff) -> None:
        _, summary = classify(empty_diff, code_changed=True, tests_changed=False)
        assert summary == "Python files in the source directory changed. The public API did not change."

    def test_test_summary(self, empty_diff: ApiDiff) -> None:
        _, summary = classify(empty_diff, code_changed=False, tests_changed=True)
        assert summary == "Only Python files in the test directory changed."

    def test_other_summary(self, empty_diff: ApiDiff) -> None:
        _, summary = classify(empty_diff, code_changed=False, tests_changed=False)
        assert summary == "No Python file in the source directory or in the test directory changed."


class TestSignatureChangeSummary:
    """Tests for the summaries of the signature changes."""

    def test_breaking_change_gives_feat_breaking(self) -> None:
        """A breaking signature change gives ``feat!`` and names the change in the summary."""
        diff = ApiDiff(added=(), removed=(), changed=(_change("f", "parameter 'a' was removed", breaking=True),))

        commit_type, summary = classify(diff, code_changed=True, tests_changed=False)

        assert commit_type == CommitType.feat_breaking
        assert summary == "Breaking change. Breaking changes to public names: pkg: f (parameter 'a' was removed)"

    def test_removed_names_and_breaking_changes_are_both_in_the_summary(self, removal_diff: ApiDiff) -> None:
        """The summary gives the removed names, then the breaking changes."""
        diff = ApiDiff(
            added=(), removed=removal_diff.removed, changed=(_change("f", "*args was removed", breaking=True),)
        )

        _, summary = classify(diff, code_changed=True, tests_changed=False)

        assert summary == (
            "Breaking change. Removed public names: mypackage.mod: OldClass "
            "Breaking changes to public names: pkg: f (*args was removed)"
        )

    def test_additive_change_gives_feat(self, addition_diff: ApiDiff) -> None:
        """A change that only adds to a name gives ``feat``, and the summary gives the added names first."""
        changes = (
            _change("g", "optional parameter 'b' was added", breaking=False),
            _change("C", "base 'Mixin' was added", breaking=False),
        )
        diff = ApiDiff(added=addition_diff.added, removed=(), changed=changes)

        commit_type, summary = classify(diff, code_changed=True, tests_changed=False)

        assert commit_type == CommitType.feat
        assert summary == (
            "Added public names: mypackage.mod: NewClass "
            "Changes that add to public names: pkg: C (base 'Mixin' was added), g (optional parameter 'b' was added)"
        )


def _change(name: str, detail: str, *, breaking: bool) -> SignatureChange:
    return SignatureChange(module="pkg", name=name, detail=detail, is_breaking=breaking)
