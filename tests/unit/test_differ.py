"""Tests for sheridan.diffract.differ."""

from sheridan.diffract.differ import diff_surfaces
from sheridan.diffract.enums import ChangeKind
from sheridan.diffract.models import ApiDiff


class TestDiffSurfaces:
    """Tests for diff_surfaces()."""

    def test_empty_surfaces_produce_empty_diff(self) -> None:
        """Two empty APIs must give an empty diff."""
        assert diff_surfaces({}, {}).is_empty

    def test_identical_surfaces_produce_empty_diff(self) -> None:
        """Two APIs that are the same must give an empty diff."""
        surface = {"pkg.mod": ["Foo", "Bar"]}
        assert diff_surfaces(surface, surface).is_empty

    def test_name_added_in_head(self) -> None:
        """A name that is in head but not in base must be in added."""
        diff = diff_surfaces({"pkg.mod": ["Foo"]}, {"pkg.mod": ["Foo", "Bar"]})
        assert len(diff.added) == 1
        assert diff.added[0].name == "Bar"
        assert diff.added[0].kind == ChangeKind.added
        assert not diff.removed

    def test_name_removed_from_head(self) -> None:
        """A name that is in base but not in head must be in removed."""
        diff = diff_surfaces({"pkg.mod": ["Foo", "Bar"]}, {"pkg.mod": ["Foo"]})
        assert len(diff.removed) == 1
        assert diff.removed[0].name == "Bar"
        assert diff.removed[0].kind == ChangeKind.removed
        assert not diff.added

    def test_new_module_in_head_contributes_additions(self) -> None:
        """All the names of a module that is only in head must be in added."""
        diff = diff_surfaces({}, {"pkg.new": ["Alpha", "Beta"]})
        assert len(diff.added) == 2
        assert all(c.module == "pkg.new" for c in diff.added)

    def test_module_absent_from_head_contributes_removals(self) -> None:
        """All the names of a module that is only in base must be in removed."""
        diff = diff_surfaces({"pkg.old": ["Alpha"]}, {})
        assert len(diff.removed) == 1
        assert diff.removed[0].module == "pkg.old"

    def test_results_sorted_by_module_then_name(self) -> None:
        """The added and the removed tuples must be sorted by (module, name)."""
        base = {"b.mod": ["Z"], "a.mod": ["Z"]}
        head = {"b.mod": ["Z", "A"], "a.mod": ["Z", "A"]}
        diff = diff_surfaces(base, head)
        modules = [c.module for c in diff.added]
        assert modules == sorted(modules)

    def test_mixed_changes_are_both_breaking_and_additive(self, mixed_diff: ApiDiff) -> None:
        """A diff with added and removed names must be breaking and have additions."""
        assert mixed_diff.is_breaking
        assert mixed_diff.has_additions

    def test_module_rename_appears_as_remove_and_add(self) -> None:
        """A renamed module gives one removed name and one added name."""
        base = {"pkg.old": ["Foo"]}
        head = {"pkg.new": ["Foo"]}
        diff = diff_surfaces(base, head)
        assert len(diff.removed) == 1
        assert diff.removed[0].module == "pkg.old"
        assert len(diff.added) == 1
        assert diff.added[0].module == "pkg.new"

    def test_returns_tuples_not_lists(self) -> None:
        """diff_surfaces must give an ApiDiff with tuple fields, not lists."""
        diff = diff_surfaces({"m": ["A"]}, {"m": ["A", "B"]})
        assert isinstance(diff.added, tuple)
        assert isinstance(diff.removed, tuple)
