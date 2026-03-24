"""Tests for sheridan.diffract.checker."""

from __future__ import annotations

from pathlib import Path

import pytest

from sheridan.diffract.checker import check
from sheridan.diffract.enums import CommitType
from sheridan.diffract.exceptions import GitError, SurfaceError
from sheridan.diffract.models import ApiDiff, DiffractResult


class TestCheck:
    """Tests for the high-level check() function with all I/O mocked."""

    def test_returns_diffract_result(self, empty_diff: ApiDiff, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """check() must return a DiffractResult when all dependencies succeed."""
        mocker.patch("sheridan.diffract.checker.get_repo")
        mocker.patch("sheridan.diffract.checker.get_api_at_ref", return_value={})
        mocker.patch("sheridan.diffract.checker.has_python_changes", return_value=False)
        mocker.patch("sheridan.diffract.checker.diff_surfaces", return_value=empty_diff)
        mocker.patch("sheridan.diffract.checker.classify", return_value=(CommitType.fix, "No changes."))

        result = check(repo_path=Path("/tmp"))

        assert isinstance(result, DiffractResult)
        assert result.commit_type == CommitType.fix
        assert result.summary == "No changes."

    def test_passes_refs_and_src_path_through(self, empty_diff: ApiDiff, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """check() must forward base_ref, head_ref, and src_path to get_api_at_ref."""
        mocker.patch("sheridan.diffract.checker.get_repo")
        mock_get_api = mocker.patch("sheridan.diffract.checker.get_api_at_ref", return_value={})
        mocker.patch("sheridan.diffract.checker.has_python_changes", return_value=False)
        mocker.patch("sheridan.diffract.checker.diff_surfaces", return_value=empty_diff)
        mocker.patch("sheridan.diffract.checker.classify", return_value=(CommitType.fix, "ok"))

        check(base_ref="v1.0", head_ref="v2.0", src_path="lib", repo_path=Path("/tmp"))

        calls = mock_get_api.call_args_list
        assert len(calls) == 2
        _, kwargs_0 = calls[0]
        _, kwargs_1 = calls[1]
        assert kwargs_0["src_path"] == "lib"
        assert kwargs_1["src_path"] == "lib"

    def test_defaults_repo_path_to_cwd(self, empty_diff: ApiDiff, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """check() must use Path.cwd() when repo_path is not supplied."""
        mock_get_repo = mocker.patch("sheridan.diffract.checker.get_repo")
        mocker.patch("sheridan.diffract.checker.get_api_at_ref", return_value={})
        mocker.patch("sheridan.diffract.checker.has_python_changes", return_value=False)
        mocker.patch("sheridan.diffract.checker.diff_surfaces", return_value=empty_diff)
        mocker.patch("sheridan.diffract.checker.classify", return_value=(CommitType.fix, "ok"))

        check()

        mock_get_repo.assert_called_once_with(Path.cwd())

    def test_propagates_git_error_from_get_repo(self, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """check() must not swallow GitError raised by get_repo."""
        mocker.patch("sheridan.diffract.checker.get_repo", side_effect=GitError("no repo"))
        with pytest.raises(GitError, match="no repo"):
            check(repo_path=Path("/tmp"))

    def test_propagates_git_error_from_get_api_at_ref(self, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """check() must not swallow GitError raised by get_api_at_ref."""
        mocker.patch("sheridan.diffract.checker.get_repo")
        mocker.patch("sheridan.diffract.checker.get_api_at_ref", side_effect=GitError("bad ref"))
        with pytest.raises(GitError, match="bad ref"):
            check(repo_path=Path("/tmp"))

    def test_propagates_surface_error(self, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """check() must not swallow SurfaceError raised by get_api_at_ref."""
        mocker.patch("sheridan.diffract.checker.get_repo")
        mocker.patch("sheridan.diffract.checker.get_api_at_ref", side_effect=SurfaceError("boom"))
        with pytest.raises(SurfaceError, match="boom"):
            check(repo_path=Path("/tmp"))
