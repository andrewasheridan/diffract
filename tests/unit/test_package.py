"""Tests for the sheridan.diffract top-level package."""

from __future__ import annotations

import importlib
import importlib.metadata

import pytest

import sheridan.diffract as pkg


class TestPublicApi:
    """Verify that the package's public API surface is correct."""

    def test_check_is_callable(self) -> None:
        """check must be importable and callable from the top-level package."""
        assert callable(pkg.check)

    def test_version_is_non_empty_string(self) -> None:
        """__version__ must be a non-empty string."""
        assert isinstance(pkg.__version__, str)
        assert pkg.__version__

    def test_all_names_are_present(self) -> None:
        """Every name declared in __all__ must exist as a package attribute."""
        for name in pkg.__all__:
            assert hasattr(pkg, name), f"Missing from package: {name}"

    def test_expected_names_in_all(self) -> None:
        """__all__ must include the core public names."""
        expected = {
            "__version__",
            "check",
            "ApiDiff",
            "ChangeKind",
            "CommitType",
            "DiffractError",
            "DiffractResult",
            "GitError",
            "NameChange",
            "SurfaceError",
        }
        assert expected <= set(pkg.__all__)


class TestVersionFallback:
    """Tests for the __version__ PackageNotFoundError fallback."""

    def test_falls_back_to_unknown_when_metadata_absent(self, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """__version__ must fall back to '0.0.0+unknown' when package metadata is missing."""
        mocker.patch.object(
            importlib.metadata,
            "version",
            side_effect=importlib.metadata.PackageNotFoundError("sheridan-diffract"),
        )
        importlib.reload(pkg)
        assert pkg.__version__ == "0.0.0+unknown"
        # Restore real metadata for subsequent tests.
        importlib.reload(pkg)
