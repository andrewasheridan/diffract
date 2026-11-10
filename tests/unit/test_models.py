"""Tests for sheridan.diffract.models."""

from __future__ import annotations

import json

import pytest

from sheridan.diffract.enums import ChangeKind, CommitType
from sheridan.diffract.models import ApiDiff, DiffractResult, NameChange


class TestNameChange:
    """Tests for the NameChange frozen dataclass."""

    def test_fields_stored_correctly(self) -> None:
        """NameChange must store module, name, and kind."""
        nc = NameChange(module="pkg.mod", name="Foo", kind=ChangeKind.added)
        assert nc.module == "pkg.mod"
        assert nc.name == "Foo"
        assert nc.kind == ChangeKind.added

    def test_is_frozen(self) -> None:
        """NameChange must be immutable."""
        nc = NameChange(module="pkg.mod", name="Foo", kind=ChangeKind.added)
        with pytest.raises(AttributeError):
            nc.name = "Bar"  # type: ignore[misc]

    def test_equality(self) -> None:
        """Two NameChanges with identical fields must be equal."""
        a = NameChange(module="m", name="X", kind=ChangeKind.added)
        b = NameChange(module="m", name="X", kind=ChangeKind.added)
        assert a == b

    def test_hashable(self) -> None:
        """NameChange must be usable as a dict key / set member."""
        nc = NameChange(module="m", name="X", kind=ChangeKind.added)
        assert {nc}


class TestApiDiff:
    """Tests for ApiDiff dataclass and its computed properties."""

    def test_is_empty_when_no_changes(self, empty_diff: ApiDiff) -> None:
        """is_empty must be True when there are no added or removed names."""
        assert empty_diff.is_empty

    def test_is_not_empty_with_additions(self, addition_diff: ApiDiff) -> None:
        """is_empty must be False when names were added."""
        assert not addition_diff.is_empty

    def test_is_not_empty_with_removals(self, removal_diff: ApiDiff) -> None:
        """is_empty must be False when names were removed."""
        assert not removal_diff.is_empty

    def test_is_breaking_false_for_additions_only(self, addition_diff: ApiDiff) -> None:
        """is_breaking must be False when no names were removed."""
        assert not addition_diff.is_breaking

    def test_is_breaking_true_when_names_removed(self, removal_diff: ApiDiff) -> None:
        """is_breaking must be True when names were removed."""
        assert removal_diff.is_breaking

    def test_is_breaking_true_for_mixed_diff(self, mixed_diff: ApiDiff) -> None:
        """is_breaking must be True even when names were also added."""
        assert mixed_diff.is_breaking

    def test_has_additions_true(self, addition_diff: ApiDiff) -> None:
        """has_additions must be True when names were added."""
        assert addition_diff.has_additions

    def test_has_additions_false_for_empty(self, empty_diff: ApiDiff) -> None:
        """has_additions must be False when nothing was added."""
        assert not empty_diff.has_additions

    def test_is_frozen(self) -> None:
        """ApiDiff must be immutable."""
        diff = ApiDiff(added=(), removed=())
        with pytest.raises(AttributeError):
            diff.added = ()  # type: ignore[misc]


class TestDiffractResult:
    """Tests for DiffractResult and its to_dict() method."""

    def _make_result(self, diff: ApiDiff, commit_type: CommitType = CommitType.feat) -> DiffractResult:
        return DiffractResult(
            commit_type=commit_type,
            summary="Added Foo",
            diff=diff,
            base_ref="HEAD~1",
            head_ref="HEAD",
        )

    def test_to_dict_has_expected_keys(self, addition_diff: ApiDiff) -> None:
        """to_dict must include all five top-level keys."""
        d = self._make_result(addition_diff).to_dict()
        assert set(d.keys()) == {"commit_type", "summary", "base_ref", "head_ref", "diff"}

    def test_to_dict_commit_type_is_plain_string(self, empty_diff: ApiDiff) -> None:
        """commit_type in to_dict must be the plain string value, not an enum repr."""
        result = self._make_result(empty_diff, CommitType.feat_breaking)
        assert result.to_dict()["commit_type"] == "feat!"

    def test_to_dict_diff_added_structure(self, addition_diff: ApiDiff) -> None:
        """diff.added in to_dict must be a list of {module, name} dicts."""
        diff_dict = self._make_result(addition_diff).to_dict()["diff"]
        assert isinstance(diff_dict, dict)
        added = diff_dict["added"]  # type: ignore[index]
        assert len(added) == 1
        assert added[0] == {"module": "mypackage.mod", "name": "NewClass"}

    def test_to_dict_diff_removed_structure(self, removal_diff: ApiDiff) -> None:
        """diff.removed in to_dict must be a list of {module, name} dicts."""
        diff_dict = self._make_result(removal_diff).to_dict()["diff"]
        removed = diff_dict["removed"]  # type: ignore[index]
        assert len(removed) == 1
        assert removed[0] == {"module": "mypackage.mod", "name": "OldClass"}

    def test_to_dict_is_json_serialisable(self, mixed_diff: ApiDiff) -> None:
        """to_dict output must round-trip through json.dumps/loads without error."""
        result = DiffractResult(
            commit_type=CommitType.feat_breaking,
            summary="Breaking change",
            diff=mixed_diff,
            base_ref="v1.0",
            head_ref="v2.0",
        )
        parsed = json.loads(json.dumps(result.to_dict()))
        assert parsed["commit_type"] == "feat!"
        assert parsed["base_ref"] == "v1.0"

    def test_is_frozen(self, empty_diff: ApiDiff) -> None:
        """DiffractResult must be immutable."""
        result = self._make_result(empty_diff)
        with pytest.raises(AttributeError):
            result.summary = "changed"  # type: ignore[misc]
