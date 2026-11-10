"""Compare the public API at two refs."""

__all__ = ["ApiSurface", "diff_surfaces", "public_names"]

from collections.abc import Iterable

from sheridan.diffract.enums import ChangeKind
from sheridan.diffract.models import ApiDiff, NameChange, SignatureChange
from sheridan.iceberg import Assignment, Class, Function, Module, Parameter, Reference

type ApiSurface = dict[str, Module]
"""The public API of a source directory: a dict from each dotted module name to its iceberg ``Module``.

The module name of a package is the name of its ``__init__`` module. diffract uses the
dotted names as keys, and not the shape of the iceberg tree, because iceberg joins a
chain of packages that have one child each into one node at the top of the tree.
"""

type _Member = Assignment | Class | Function | Reference


class _DiffBuilder:
    """Collect the changes of one module while the differ walks its public names.

    Attributes:
        module: The full module name of the changes.
        added: The public names that are only in head.
        removed: The public names that are only in base.
        changed: The changes to the public names that are in base and in head.
    """

    def __init__(self, module: str) -> None:
        self.module = module
        self.added: list[NameChange] = []
        self.removed: list[NameChange] = []
        self.changed: list[SignatureChange] = []

    def add_name(self, name: str) -> None:
        self.added.append(NameChange(module=self.module, name=name, kind=ChangeKind.added))

    def remove_name(self, name: str) -> None:
        self.removed.append(NameChange(module=self.module, name=name, kind=ChangeKind.removed))

    def breaking(self, name: str, detail: str) -> None:
        self.changed.append(SignatureChange(module=self.module, name=name, detail=detail, is_breaking=True))

    def additive(self, name: str, detail: str) -> None:
        self.changed.append(SignatureChange(module=self.module, name=name, detail=detail, is_breaking=False))


def _public_members(members: Iterable[_Member]) -> dict[str, _Member]:
    """Map each public name to its member.

    Args:
        members: The members of a module or of a class.

    Returns:
        A dict from each public name to its member. If two members have the same name,
        the last one wins, as in Python.
    """
    return {member.name: member for member in members if member.is_public}


def _module_members(module: Module) -> dict[str, _Member]:
    """Map each public name of a module to its member."""
    return _public_members((*module.assignments, *module.classes, *module.functions, *module.references))


def _class_members(cls: Class) -> dict[str, _Member]:
    """Map each public name in a class body to its member."""
    return _public_members((*cls.assignments, *cls.methods, *cls.nested_classes))


def public_names(surface: ApiSurface) -> dict[str, list[str]]:
    """Collect the public names of each module in an API.

    Args:
        surface: The API, as a dict from each module name to its ``Module``.

    Returns:
        A dict from each module name to its sorted public names.
    """
    return {name: sorted(_module_members(module)) for name, module in sorted(surface.items())}


def _diff_members(builder: _DiffBuilder, prefix: str, base: dict[str, _Member], head: dict[str, _Member]) -> None:
    """Compare two groups of members by name, then compare each member that is in the two groups.

    Args:
        builder: The builder that collects the changes.
        prefix: The text in front of each name, for example ``"MyClass."``, or ``""``
            for the names of a module.
        base: The members at base.
        head: The members at head.
    """
    for name in sorted(head.keys() - base.keys()):
        builder.add_name(prefix + name)

    for name in sorted(base.keys() - head.keys()):
        builder.remove_name(prefix + name)

    for name in sorted(base.keys() & head.keys()):
        _diff_member(builder, prefix + name, base[name], head[name])


def _diff_member(builder: _DiffBuilder, name: str, base: _Member, head: _Member) -> None:
    """Compare one public name that is in base and in head.

    A function that became a class, or a class that became a function, is a breaking
    change. diffract does not compare an assignment or an unresolved reference with a
    different kind of member, because the value of either one can be a class or a
    function.

    Args:
        builder: The builder that collects the changes.
        name: The name of the member, with the class names in front of it.
        base: The member at base.
        head: The member at head.
    """
    if isinstance(base, Function) and isinstance(head, Function):
        _diff_function(builder, name, base, head)
        return

    if isinstance(base, Class) and isinstance(head, Class):
        _diff_class(builder, name, base, head)
        return

    if isinstance(base, Function) and isinstance(head, Class):
        builder.breaking(name, "changed from a function to a class")
        return

    if isinstance(base, Class) and isinstance(head, Function):
        builder.breaking(name, "changed from a class to a function")


def _diff_class(builder: _DiffBuilder, name: str, base: Class, head: Class) -> None:
    """Compare the bases, the keywords and the members of a class.

    A removed base or class keyword (for example ``metaclass=ABCMeta``) is a breaking
    change. An added base or class keyword only adds to the class.

    Args:
        builder: The builder that collects the changes.
        name: The name of the class, with the names of the outer classes in front of it.
        base: The class at base.
        head: The class at head.
    """
    for expression in base.bases:
        if expression not in head.bases:
            builder.breaking(name, f"base {expression!r} was removed")

    for expression in head.bases:
        if expression not in base.bases:
            builder.additive(name, f"base {expression!r} was added")

    for keyword in base.keywords:
        if keyword not in head.keywords:
            builder.breaking(name, f"class keyword {keyword!r} was removed")

    for keyword in head.keywords:
        if keyword not in base.keywords:
            builder.additive(name, f"class keyword {keyword!r} was added")

    _diff_members(builder, f"{name}.", _class_members(base), _class_members(head))


def _diff_function(builder: _DiffBuilder, name: str, base: Function, head: Function) -> None:
    """Compare the kind and the parameters of a function or a method.

    diffract does not compare the annotations, the decorators or the overloads. A
    change to the kind (for example from a method to a property) or from ``def`` to
    ``async def`` is a breaking change.

    Args:
        builder: The builder that collects the changes.
        name: The name of the function, with the class names in front of it.
        base: The function at base.
        head: The function at head.
    """
    if base.kind != head.kind:
        builder.breaking(name, f"changed from a {base.kind} to a {head.kind}")
        return

    if base.is_async != head.is_async:
        builder.breaking(name, "changed to async" if head.is_async else "changed to not async")

    if base.kind == "property":
        return

    _diff_positional(builder, name, base, head)
    _diff_keyword_only(builder, name, base, head)
    _diff_variadic(builder, name, "*args", base.var_positional, head.var_positional)
    _diff_variadic(builder, name, "**kwargs", base.var_keyword, head.var_keyword)


def _diff_default(builder: _DiffBuilder, name: str, base: Parameter, head: Parameter) -> None:
    """Compare the default values of one parameter.

    A removed default is a breaking change, because the parameter becomes necessary.
    An added default only adds to the function. diffract does not compare the values.
    """
    if base.default is not None and head.default is None:
        builder.breaking(name, f"parameter {base.name!r} has no default value now")
    elif base.default is None and head.default is not None:
        builder.additive(name, f"parameter {base.name!r} has a default value now")


def _diff_new_parameter(builder: _DiffBuilder, name: str, parameter: Parameter) -> None:
    """Record a parameter that is only in head.

    A new parameter without a default is a breaking change, because each call must
    give it. A new parameter with a default only adds to the function.
    """
    if parameter.default is None:
        builder.breaking(name, f"necessary parameter {parameter.name!r} was added")
    else:
        builder.additive(name, f"optional parameter {parameter.name!r} was added")


def _diff_positional(builder: _DiffBuilder, name: str, base: Function, head: Function) -> None:
    """Compare the positional parameters of a function.

    A positional parameter that was removed, that moved to a different position or
    that became keyword-only is a breaking change, because calls that give the
    arguments by position stop. iceberg does not tell positional-only parameters
    from the other positional parameters. Thus a new name for a positional-only
    parameter is also a breaking change.

    Args:
        builder: The builder that collects the changes.
        name: The name of the function, with the class names in front of it.
        base: The function at base.
        head: The function at head.
    """
    head_positions = {parameter.name: index for index, parameter in enumerate(head.positional_parameters)}
    head_keywords = {parameter.name: parameter for parameter in head.keyword_parameters}
    base_keywords = {parameter.name for parameter in base.keyword_parameters}

    for index, parameter in enumerate(base.positional_parameters):
        if parameter.name in head_keywords:
            builder.breaking(name, f"parameter {parameter.name!r} is keyword-only now")
            _diff_default(builder, name, parameter, head_keywords[parameter.name])
            continue

        head_index = head_positions.get(parameter.name)
        if head_index is None:
            builder.breaking(name, f"parameter {parameter.name!r} was removed")
            continue

        if head_index != index:
            builder.breaking(name, f"parameter {parameter.name!r} moved from position {index} to {head_index}")

        _diff_default(builder, name, parameter, head.positional_parameters[head_index])

    base_positional = {parameter.name for parameter in base.positional_parameters}
    for parameter in head.positional_parameters:
        if parameter.name in base_positional or parameter.name in base_keywords:
            continue

        _diff_new_parameter(builder, name, parameter)


def _diff_keyword_only(builder: _DiffBuilder, name: str, base: Function, head: Function) -> None:
    """Compare the keyword-only parameters of a function.

    A keyword-only parameter that became positional is not a breaking change, because
    calls can still give it by keyword. ``_diff_positional`` compares the parameters
    that became keyword-only.

    Args:
        builder: The builder that collects the changes.
        name: The name of the function, with the class names in front of it.
        base: The function at base.
        head: The function at head.
    """
    base_keywords = {parameter.name: parameter for parameter in base.keyword_parameters}
    head_keywords = {parameter.name: parameter for parameter in head.keyword_parameters}
    base_positional = {parameter.name for parameter in base.positional_parameters}
    head_positional = {parameter.name: parameter for parameter in head.positional_parameters}

    for parameter_name in sorted(base_keywords):
        parameter = base_keywords[parameter_name]

        if parameter_name in head_keywords:
            _diff_default(builder, name, parameter, head_keywords[parameter_name])
        elif parameter_name in head_positional:
            builder.additive(name, f"parameter {parameter_name!r} can be positional now")
            _diff_default(builder, name, parameter, head_positional[parameter_name])
        else:
            builder.breaking(name, f"parameter {parameter_name!r} was removed")

    for parameter_name in sorted(head_keywords.keys() - base_keywords.keys() - base_positional):
        _diff_new_parameter(builder, name, head_keywords[parameter_name])


def _diff_variadic(
    builder: _DiffBuilder,
    name: str,
    label: str,
    base: Parameter | None,
    head: Parameter | None,
) -> None:
    """Compare the ``*args`` or the ``**kwargs`` parameter of a function.

    diffract does not compare the names of these parameters, because calls cannot
    give them by name.

    Args:
        builder: The builder that collects the changes.
        name: The name of the function, with the class names in front of it.
        label: ``"*args"`` or ``"**kwargs"``, for the detail text.
        base: The parameter at base, or ``None``.
        head: The parameter at head, or ``None``.
    """
    if base is not None and head is None:
        builder.breaking(name, f"{label} was removed")
    elif base is None and head is not None:
        builder.additive(name, f"{label} was added")


def diff_surfaces(base: ApiSurface, head: ApiSurface) -> ApiDiff:
    """Compare two public APIs and find the added, the removed and the changed names.

    The function compares the public names of each module that is in one of the two
    APIs. For a name that is in base and in head, it also compares:

    - the kind and the parameters of a function or a method,
    - the bases, the class keywords and the members of a class.

    It sorts the changes by ``(module, name)``.

    Args:
        base: The public API at the earlier ref.
        head: The public API at the later ref.

    Returns:
        An :class:`ApiDiff` with a :class:`NameChange` for each added or removed name
        and a :class:`SignatureChange` for each change to a name.
    """
    added: list[NameChange] = []
    removed: list[NameChange] = []
    changed: list[SignatureChange] = []

    for module in sorted(base.keys() | head.keys()):
        builder = _DiffBuilder(module)
        base_members = _module_members(base[module]) if module in base else {}
        head_members = _module_members(head[module]) if module in head else {}
        _diff_members(builder, "", base_members, head_members)

        added.extend(builder.added)
        removed.extend(builder.removed)
        changed.extend(builder.changed)

    added.sort(key=lambda c: (c.module, c.name))
    removed.sort(key=lambda c: (c.module, c.name))
    changed.sort(key=lambda c: (c.module, c.name))

    return ApiDiff(added=tuple(added), removed=tuple(removed), changed=tuple(changed))
