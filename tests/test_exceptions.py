"""Tests for sheridan.diffract.exceptions."""

from __future__ import annotations

import pytest

from sheridan.diffract.exceptions import DiffractError, GitError, SurfaceError


class TestExceptionHierarchy:
    """Tests for the exception hierarchy."""

    def test_git_error_is_diffract_error(self) -> None:
        """GitError must be a subclass of DiffractError."""
        assert issubclass(GitError, DiffractError)

    def test_surface_error_is_diffract_error(self) -> None:
        """SurfaceError must be a subclass of DiffractError."""
        assert issubclass(SurfaceError, DiffractError)

    def test_diffract_error_is_exception(self) -> None:
        """DiffractError must be a subclass of Exception."""
        assert issubclass(DiffractError, Exception)


class TestGitError:
    """Tests for GitError."""

    def test_raise_with_message(self) -> None:
        """GitError must be raise-able with a message."""
        with pytest.raises(GitError, match="bad ref"):
            raise GitError("bad ref")

    def test_caught_as_diffract_error(self) -> None:
        """GitError must be catch-able as DiffractError."""
        with pytest.raises(DiffractError):
            raise GitError("caught as base")


class TestSurfaceError:
    """Tests for SurfaceError."""

    def test_raise_with_message(self) -> None:
        """SurfaceError must be raise-able with a message."""
        with pytest.raises(SurfaceError, match="extraction failed"):
            raise SurfaceError("extraction failed")

    def test_caught_as_diffract_error(self) -> None:
        """SurfaceError must be catch-able as DiffractError."""
        with pytest.raises(DiffractError):
            raise SurfaceError("caught as base")
