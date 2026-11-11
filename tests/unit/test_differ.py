"""Tests for sheridan.diffract._differ."""

from typing import Literal

from sheridan.diffract._differ import diff_surfaces
from sheridan.diffract._enums import ChangeKind
from sheridan.diffract._models import ApiDiff
from sheridan.iceberg import Assignment, Class, Function, Module, Parameter, Reference
from tests.unit.conftest import surface


def _names_diff(base: dict[str, list[str]], head: dict[str, list[str]]) -> ApiDiff:
    """Compare two APIs in which each public name is a plain assignment."""
    return diff_surfaces(surface(base), surface(head))


def _param(name: str, default: str | None = None) -> Parameter:
    return Parameter(name=name, annotation=None, default=default)


def _func(
    name: str = "f",
    positional: tuple[Parameter, ...] = (),
    keyword: tuple[Parameter, ...] = (),
    *,
    var_positional: bool = False,
    var_keyword: bool = False,
    kind: Literal["function", "method", "classmethod", "staticmethod", "property"] = "function",
    is_async: bool = False,
) -> Function:
    return Function(
        name=name,
        positional_parameters=positional,
        keyword_parameters=frozenset(keyword),
        var_positional=_param("args") if var_positional else None,
        var_keyword=_param("kwargs") if var_keyword else None,
        returns=None,
        is_async=is_async,
        kind=kind,
    )


def _class(
    name: str = "C",
    bases: tuple[str, ...] = (),
    keywords: tuple[str, ...] = (),
    members: tuple[Assignment | Function | Class, ...] = (),
) -> Class:
    return Class(
        name=name,
        bases=bases,
        keywords=keywords,
        assignments=tuple(m for m in members if isinstance(m, Assignment)),
        methods=tuple(m for m in members if isinstance(m, Function)),
        nested_classes=tuple(m for m in members if isinstance(m, Class)),
    )


def _module(*members: Assignment | Class | Function | Reference) -> dict[str, Module]:
    """Build an API with one module, ``pkg``, that has the given members."""
    module = Module(
        name="pkg",
        assignments=tuple(m for m in members if isinstance(m, Assignment)),
        classes=tuple(m for m in members if isinstance(m, Class)),
        functions=tuple(m for m in members if isinstance(m, Function)),
        references=tuple(m for m in members if isinstance(m, Reference)),
    )
    return {"pkg": module}


def _changes(
    base: Assignment | Class | Function | Reference, head: Assignment | Class | Function | Reference
) -> list[tuple[str, str, bool]]:
    """Compare one member at base and at head, and give each change as ``(name, detail, is_breaking)``."""
    diff = diff_surfaces(_module(base), _module(head))
    return [(change.name, change.detail, change.is_breaking) for change in diff.changed]


class TestDiffSurfaces:
    """Tests for _names_diff()."""

    def test_empty_surfaces_produce_empty_diff(self) -> None:
        """Two empty APIs must give an empty diff."""
        assert _names_diff({}, {}).is_empty

    def test_identical_surfaces_produce_empty_diff(self) -> None:
        """Two APIs that are the same must give an empty diff."""
        names = {"pkg.mod": ["Foo", "Bar"]}
        assert _names_diff(names, names).is_empty

    def test_name_added_in_head(self) -> None:
        """A name that is in head but not in base must be in added."""
        diff = _names_diff({"pkg.mod": ["Foo"]}, {"pkg.mod": ["Foo", "Bar"]})
        assert len(diff.added) == 1
        assert diff.added[0].name == "Bar"
        assert diff.added[0].kind == ChangeKind.added
        assert not diff.removed

    def test_name_removed_from_head(self) -> None:
        """A name that is in base but not in head must be in removed."""
        diff = _names_diff({"pkg.mod": ["Foo", "Bar"]}, {"pkg.mod": ["Foo"]})
        assert len(diff.removed) == 1
        assert diff.removed[0].name == "Bar"
        assert diff.removed[0].kind == ChangeKind.removed
        assert not diff.added

    def test_new_module_in_head_contributes_additions(self) -> None:
        """All the names of a module that is only in head must be in added."""
        diff = _names_diff({}, {"pkg.new": ["Alpha", "Beta"]})
        assert len(diff.added) == 2
        assert all(c.module == "pkg.new" for c in diff.added)

    def test_module_absent_from_head_contributes_removals(self) -> None:
        """All the names of a module that is only in base must be in removed."""
        diff = _names_diff({"pkg.old": ["Alpha"]}, {})
        assert len(diff.removed) == 1
        assert diff.removed[0].module == "pkg.old"

    def test_results_sorted_by_module_then_name(self) -> None:
        """The added and the removed tuples must be sorted by (module, name)."""
        base = {"b.mod": ["Z"], "a.mod": ["Z"]}
        head = {"b.mod": ["Z", "A"], "a.mod": ["Z", "A"]}
        diff = _names_diff(base, head)
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
        diff = _names_diff(base, head)
        assert len(diff.removed) == 1
        assert diff.removed[0].module == "pkg.old"
        assert len(diff.added) == 1
        assert diff.added[0].module == "pkg.new"

    def test_returns_tuples_not_lists(self) -> None:
        """diff_surfaces must give an ApiDiff with tuple fields, not lists."""
        diff = _names_diff({"m": ["A"]}, {"m": ["A", "B"]})
        assert isinstance(diff.added, tuple)
        assert isinstance(diff.removed, tuple)


class TestFunctionChanges:
    """Tests for the comparison of a function that is in base and in head."""

    def test_same_signature_gives_no_change(self) -> None:
        f = _func(positional=(_param("a"), _param("b", "1")), keyword=(_param("c", "2"),))
        assert diff_surfaces(_module(f), _module(f)).is_empty

    def test_removed_positional_parameter_is_breaking(self) -> None:
        base = _func(positional=(_param("a"), _param("b")))
        head = _func(positional=(_param("a"),))
        assert _changes(base, head) == [("f", "parameter 'b' was removed", True)]

    def test_moved_positional_parameter_is_breaking(self) -> None:
        base = _func(positional=(_param("a"), _param("b")))
        head = _func(positional=(_param("b"), _param("a")))
        assert _changes(base, head) == [
            ("f", "parameter 'a' moved from position 0 to 1", True),
            ("f", "parameter 'b' moved from position 1 to 0", True),
        ]

    def test_positional_parameter_that_became_keyword_only_is_breaking(self) -> None:
        base = _func(positional=(_param("a", "1"),))
        head = _func(keyword=(_param("a", "1"),))
        assert _changes(base, head) == [("f", "parameter 'a' is keyword-only now", True)]

    def test_keyword_only_parameter_that_became_positional_adds(self) -> None:
        base = _func(keyword=(_param("a"),))
        head = _func(positional=(_param("a", "1"),))
        assert _changes(base, head) == [
            ("f", "parameter 'a' can be positional now", False),
            ("f", "parameter 'a' has a default value now", False),
        ]

    def test_new_required_parameter_is_breaking(self) -> None:
        assert _changes(_func(), _func(positional=(_param("a"),))) == [("f", "necessary parameter 'a' was added", True)]
        assert _changes(_func(), _func(keyword=(_param("k"),))) == [("f", "necessary parameter 'k' was added", True)]

    def test_new_optional_parameter_adds(self) -> None:
        assert _changes(_func(), _func(positional=(_param("a", "1"),))) == [
            ("f", "optional parameter 'a' was added", False)
        ]
        assert _changes(_func(), _func(keyword=(_param("k", "1"),))) == [
            ("f", "optional parameter 'k' was added", False)
        ]

    def test_removed_default_is_breaking(self) -> None:
        base = _func(positional=(_param("a", "1"),), keyword=(_param("k", "2"),))
        head = _func(positional=(_param("a"),), keyword=(_param("k"),))
        assert _changes(base, head) == [
            ("f", "parameter 'a' has no default value now", True),
            ("f", "parameter 'k' has no default value now", True),
        ]

    def test_added_default_adds(self) -> None:
        base = _func(keyword=(_param("k"),))
        head = _func(keyword=(_param("k", "None"),))
        assert _changes(base, head) == [("f", "parameter 'k' has a default value now", False)]

    def test_changed_default_value_gives_no_change(self) -> None:
        base = _func(positional=(_param("a", "1"),))
        head = _func(positional=(_param("a", "2"),))
        assert _changes(base, head) == []

    def test_removed_keyword_only_parameter_is_breaking(self) -> None:
        base = _func(keyword=(_param("k", "1"),))
        assert _changes(base, _func()) == [("f", "parameter 'k' was removed", True)]

    def test_variadic_parameters(self) -> None:
        plain = _func()
        variadic = _func(var_positional=True, var_keyword=True)
        assert _changes(plain, variadic) == [("f", "*args was added", False), ("f", "**kwargs was added", False)]
        assert _changes(variadic, plain) == [("f", "*args was removed", True), ("f", "**kwargs was removed", True)]

    def test_async_change_is_breaking(self) -> None:
        assert _changes(_func(), _func(is_async=True)) == [("f", "changed to async", True)]
        assert _changes(_func(is_async=True), _func()) == [("f", "changed to not async", True)]

    def test_annotation_change_gives_no_change(self) -> None:
        base = _func(positional=(Parameter(name="a", annotation="int", default=None),))
        head = _func(positional=(Parameter(name="a", annotation="str", default=None),))
        assert _changes(base, head) == []

    def test_property_parameters_are_not_compared(self) -> None:
        base = _func(positional=(_param("self"),), kind="property")
        head = _func(positional=(_param("self"), _param("x")), kind="property")
        assert _changes(base, head) == []

    def test_each_positional_parameter_is_compared(self) -> None:
        """A change to one parameter must not stop the comparison of the parameters after it."""
        base = _func(positional=(_param("a"), _param("b"), _param("c", "1")))
        head = _func(positional=(_param("c"), _param("d", "2")), keyword=(_param("a"),))
        assert _changes(base, head) == [
            ("f", "parameter 'a' is keyword-only now", True),
            ("f", "parameter 'b' was removed", True),
            ("f", "parameter 'c' moved from position 2 to 0", True),
            ("f", "parameter 'c' has no default value now", True),
            ("f", "optional parameter 'd' was added", False),
        ]


class TestClassChanges:
    """Tests for the comparison of a class that is in base and in head."""

    def test_bases_and_keywords(self) -> None:
        base = _class(bases=("A", "B"), keywords=("metaclass=M",))
        head = _class(bases=("A", "D"), keywords=("total=False",))
        assert sorted(_changes(base, head)) == [
            ("C", "base 'B' was removed", True),
            ("C", "base 'D' was added", False),
            ("C", "class keyword 'metaclass=M' was removed", True),
            ("C", "class keyword 'total=False' was added", False),
        ]

    def test_members_are_added_and_removed_with_the_class_name(self) -> None:
        base = _class(members=(Assignment(name="x", annotation="int"), _func("old", kind="method")))
        head = _class(members=(Assignment(name="x", annotation="int"), _func("new", kind="method")))
        diff = diff_surfaces(_module(base), _module(head))
        assert [c.name for c in diff.added] == ["C.new"]
        assert [c.name for c in diff.removed] == ["C.old"]
        assert diff.is_breaking

    def test_private_members_are_ignored(self) -> None:
        base = _class(members=(_func("_helper", kind="method"),))
        assert diff_surfaces(_module(base), _module(_class())).is_empty

    def test_method_signatures_are_compared(self) -> None:
        self_param = _param("self")
        base = _class(members=(_func("m", (self_param, _param("y")), kind="method"),))
        head = _class(members=(_func("m", (self_param, _param("y", "0")), kind="method"),))
        assert _changes(base, head) == [("C.m", "parameter 'y' has a default value now", False)]

    def test_nested_classes_are_compared(self) -> None:
        base = _class(members=(_class("Inner", bases=("A",)),))
        head = _class(members=(_class("Inner"),))
        assert _changes(base, head) == [("C.Inner", "base 'A' was removed", True)]

    def test_method_kind_change_is_breaking(self) -> None:
        base = _class(members=(_func("p", (_param("self"),), kind="property"),))
        head = _class(members=(_func("p", (_param("self"),), kind="method"),))
        assert _changes(base, head) == [("C.p", "changed from a property to a method", True)]


class TestKindChanges:
    """Tests for a public name that changed to a different kind of member."""

    def test_function_to_class_is_breaking(self) -> None:
        assert _changes(_func("X"), _class("X")) == [("X", "changed from a function to a class", True)]

    def test_class_to_function_is_breaking(self) -> None:
        assert _changes(_class("X"), _func("X")) == [("X", "changed from a class to a function", True)]

    def test_assignment_or_reference_change_gives_no_change(self) -> None:
        reference = Reference(name="X", module="other", attribute="X")
        assert _changes(Assignment(name="X", annotation=None), _class("X")) == []
        assert _changes(reference, _func("X")) == []


class TestApiDiffWithChanges:
    """Tests for the effect of the signature changes on the diff."""

    def test_only_additive_changes_are_additions(self) -> None:
        diff = diff_surfaces(_module(_func()), _module(_func(keyword=(_param("k", "1"),))))
        assert diff.has_additions
        assert not diff.is_breaking
        assert not diff.is_empty

    def test_a_breaking_change_is_breaking(self) -> None:
        diff = diff_surfaces(_module(_func(positional=(_param("a"),))), _module(_func()))
        assert diff.is_breaking
