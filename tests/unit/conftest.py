"""The pytest fixtures for the unit tests."""

import pytest

from sheridan.diffract._differ import ApiSurface
from sheridan.diffract._enums import ChangeKind
from sheridan.diffract._models import ApiDiff, NameChange
from sheridan.iceberg import Assignment, Module


@pytest.fixture()
def empty_diff() -> ApiDiff:
    """Build an ApiDiff with no changes."""
    return ApiDiff(added=(), removed=())


@pytest.fixture()
def addition_diff() -> ApiDiff:
    """Build an ApiDiff with one added name."""
    return ApiDiff(
        added=(NameChange(module="mypackage.mod", name="NewClass", kind=ChangeKind.added),),
        removed=(),
    )


@pytest.fixture()
def removal_diff() -> ApiDiff:
    """Build an ApiDiff with one removed name."""
    return ApiDiff(
        added=(),
        removed=(NameChange(module="mypackage.mod", name="OldClass", kind=ChangeKind.removed),),
    )


@pytest.fixture()
def mixed_diff() -> ApiDiff:
    """Build an ApiDiff with added names and removed names."""
    return ApiDiff(
        added=(NameChange(module="mypackage.mod", name="NewClass", kind=ChangeKind.added),),
        removed=(NameChange(module="mypackage.mod", name="OldClass", kind=ChangeKind.removed),),
    )


def surface(names: dict[str, list[str]]) -> ApiSurface:
    """Build an API in which each public name is a plain assignment.

    Args:
        names: A dict from each module name to its public names.

    Returns:
        A dict from each module name to an iceberg ``Module``.
    """
    return {
        module: Module(
            name=module,
            assignments=tuple(Assignment(name=name, annotation=None) for name in module_names),
            classes=(),
            functions=(),
        )
        for module, module_names in names.items()
    }


def public_names(api: ApiSurface) -> dict[str, list[str]]:
    """Collect the public names of each module in an API.

    Args:
        api: A dict from each module name to its iceberg ``Module``.

    Returns:
        A dict from each module name to its sorted public names.
    """
    return {name: _module_public_names(module) for name, module in sorted(api.items())}


def _module_public_names(module: Module) -> list[str]:
    members = (*module.assignments, *module.classes, *module.functions, *module.references)
    return sorted({member.name for member in members if member.is_public})
