"""Tests for the sheridan.diffract package."""

import importlib
import importlib.metadata

import pytest

import sheridan.diffract as pkg


class TestPublicApi:
    """Tests for the public API of the package."""

    def test_check_is_callable(self) -> None:
        """You must be able to import check from the package and call it."""
        assert callable(pkg.check)

    def test_version_is_non_empty_string(self) -> None:
        """__version__ must be a string that is not empty."""
        assert isinstance(pkg.__version__, str)
        assert pkg.__version__

    def test_all_names_are_present(self) -> None:
        """Each name in __all__ must be an attribute of the package."""
        for name in pkg.__all__:
            assert hasattr(pkg, name), f"Missing from package: {name}"

    def test_expected_names_in_all(self) -> None:
        """__all__ must have the main public names."""
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
    """Tests for __version__ if there is no package metadata."""

    def test_falls_back_to_unknown_when_metadata_absent(self, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """__version__ must be '0.0.0+unknown' if the package metadata is missing."""
        mocker.patch.object(
            importlib.metadata,
            "version",
            side_effect=importlib.metadata.PackageNotFoundError("sheridan-diffract"),
        )
        importlib.reload(pkg)
        assert pkg.__version__ == "0.0.0+unknown"
        # Read the real metadata again for the next tests.
        importlib.reload(pkg)
