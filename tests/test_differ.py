"""Tests for sheridan.diffract.differ."""

from __future__ import annotations

from sheridan.diffract.differ import diff_surfaces
from sheridan.diffract.enums import ChangeKind
from sheridan.diffract.models import ApiDiff


class TestDiffSurfaces:
    """Tests for diff_surfaces()."""

    def test_empty_surfaces_produce_empty_diff(self) -> None:
        """Two empty surfaces must produce an empty diff."""
        assert diff_surfaces({}, {}).is_empty

    def test_identical_surfaces_produce_empty_diff(self) -> None:
        """Two identical non-empty surfaces must produce an empty diff."""
        surface = {"pkg.mod": ["Foo", "Bar"]}
        assert diff_surfaces(surface, surface).is_empty

    def test_name_added_in_head(self) -> None:
        """A name present in head but not base must appear in added."""
        diff = diff_surfaces({"pkg.mod": ["Foo"]}, {"pkg.mod": ["Foo", "Bar"]})
        assert len(diff.added) == 1
        assert diff.added[0].name == "Bar"
        assert diff.added[0].kind == ChangeKind.added
        assert not diff.removed

    def test_name_removed_from_head(self) -> None:
        """A name present in base but not head must appear in removed."""
        diff = diff_surfaces({"pkg.mod": ["Foo", "Bar"]}, {"pkg.mod": ["Foo"]})
        assert len(diff.removed) == 1
        assert diff.removed[0].name == "Bar"
        assert diff.removed[0].kind == ChangeKind.removed
        assert not diff.added

    def test_new_module_in_head_contributes_additions(self) -> None:
        """A module present only in head must contribute all its names as added."""
        diff = diff_surfaces({}, {"pkg.new": ["Alpha", "Beta"]})
        assert len(diff.added) == 2
        assert all(c.module == "pkg.new" for c in diff.added)

    def test_module_absent_from_head_contributes_removals(self) -> None:
        """A module present only in base must contribute all its names as removed."""
        diff = diff_surfaces({"pkg.old": ["Alpha"]}, {})
        assert len(diff.removed) == 1
        assert diff.removed[0].module == "pkg.old"

    def test_results_sorted_by_module_then_name(self) -> None:
        """Added and removed tuples must be sorted by (module, name)."""
        base = {"b.mod": ["Z"], "a.mod": ["Z"]}
        head = {"b.mod": ["Z", "A"], "a.mod": ["Z", "A"]}
        diff = diff_surfaces(base, head)
        modules = [c.module for c in diff.added]
        assert modules == sorted(modules)

    def test_mixed_changes_are_both_breaking_and_additive(self, mixed_diff: ApiDiff) -> None:
        """A diff with both additions and removals must be breaking and additive."""
        assert mixed_diff.is_breaking
        assert mixed_diff.has_additions

    def test_module_rename_appears_as_remove_and_add(self) -> None:
        """Renaming a module manifests as one removal and one addition."""
        base = {"pkg.old": ["Foo"]}
        head = {"pkg.new": ["Foo"]}
        diff = diff_surfaces(base, head)
        assert len(diff.removed) == 1
        assert diff.removed[0].module == "pkg.old"
        assert len(diff.added) == 1
        assert diff.added[0].module == "pkg.new"

    def test_returns_tuples_not_lists(self) -> None:
        """diff_surfaces must return ApiDiff with tuple fields, not lists."""
        diff = diff_surfaces({"m": ["A"]}, {"m": ["A", "B"]})
        assert isinstance(diff.added, tuple)
        assert isinstance(diff.removed, tuple)
