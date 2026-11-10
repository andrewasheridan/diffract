"""Shared pytest fixtures for sheridan-diffract tests."""

from __future__ import annotations

import pytest

from sheridan.diffract.enums import ChangeKind
from sheridan.diffract.models import ApiDiff, NameChange


@pytest.fixture()
def empty_diff() -> ApiDiff:
    """Return an ApiDiff with no changes."""
    return ApiDiff(added=(), removed=())


@pytest.fixture()
def addition_diff() -> ApiDiff:
    """Return an ApiDiff with one added name."""
    return ApiDiff(
        added=(NameChange(module="mypackage.mod", name="NewClass", kind=ChangeKind.added),),
        removed=(),
    )


@pytest.fixture()
def removal_diff() -> ApiDiff:
    """Return an ApiDiff with one removed name."""
    return ApiDiff(
        added=(),
        removed=(NameChange(module="mypackage.mod", name="OldClass", kind=ChangeKind.removed),),
    )


@pytest.fixture()
def mixed_diff() -> ApiDiff:
    """Return an ApiDiff with both added and removed names."""
    return ApiDiff(
        added=(NameChange(module="mypackage.mod", name="NewClass", kind=ChangeKind.added),),
        removed=(NameChange(module="mypackage.mod", name="OldClass", kind=ChangeKind.removed),),
    )
