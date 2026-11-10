"""Tests for sheridan.diffract.checker."""

from pathlib import Path

import pytest

from sheridan.diffract.checker import check, check_staged
from sheridan.diffract.enums import CommitType
from sheridan.diffract.exceptions import GitError, SurfaceError
from sheridan.diffract.models import ApiDiff, DiffractResult


class TestCheck:
    """Tests for check(). The tests mock all the I/O."""

    def test_returns_diffract_result(self, empty_diff: ApiDiff, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """check() must give a DiffractResult if all the calls are successful."""
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
        """check() must give base_ref, head_ref and src_path to get_api_at_ref."""
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
        """check() must use Path.cwd() if there is no repo_path."""
        mock_get_repo = mocker.patch("sheridan.diffract.checker.get_repo")
        mocker.patch("sheridan.diffract.checker.get_api_at_ref", return_value={})
        mocker.patch("sheridan.diffract.checker.has_python_changes", return_value=False)
        mocker.patch("sheridan.diffract.checker.diff_surfaces", return_value=empty_diff)
        mocker.patch("sheridan.diffract.checker.classify", return_value=(CommitType.fix, "ok"))

        check()

        mock_get_repo.assert_called_once_with(Path.cwd())

    def test_propagates_git_error_from_get_repo(self, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """check() must not stop a GitError from get_repo."""
        mocker.patch("sheridan.diffract.checker.get_repo", side_effect=GitError("no repo"))
        with pytest.raises(GitError, match="no repo"):
            check(repo_path=Path("/tmp"))

    def test_propagates_git_error_from_get_api_at_ref(self, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """check() must not stop a GitError from get_api_at_ref."""
        mocker.patch("sheridan.diffract.checker.get_repo")
        mocker.patch("sheridan.diffract.checker.get_api_at_ref", side_effect=GitError("bad ref"))
        with pytest.raises(GitError, match="bad ref"):
            check(repo_path=Path("/tmp"))

    def test_propagates_surface_error(self, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """check() must not stop a SurfaceError from get_api_at_ref."""
        mocker.patch("sheridan.diffract.checker.get_repo")
        mocker.patch("sheridan.diffract.checker.get_api_at_ref", side_effect=SurfaceError("boom"))
        with pytest.raises(SurfaceError, match="boom"):
            check(repo_path=Path("/tmp"))


class TestCheckStaged:
    """Tests for check_staged(). The tests mock all the I/O."""

    def test_happy_path_returns_diffract_result(
        self,
        empty_diff: ApiDiff,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        mocker.patch("sheridan.diffract.checker.get_repo")
        mocker.patch(
            "sheridan.diffract.checker.get_api_at_ref",
            return_value={"mod": ["Foo"]},
        )
        mocker.patch(
            "sheridan.diffract.checker.get_api_at_index",
            return_value={"mod": ["Foo", "Bar"]},
        )
        mocker.patch("sheridan.diffract.checker.has_python_changes_index", return_value=True)
        mocker.patch("sheridan.diffract.checker.diff_surfaces")
        mocker.patch("sheridan.diffract.checker.classify", return_value=(CommitType.feat, "Added Bar."))

        result = check_staged(repo_path=Path("/tmp"))

        assert isinstance(result, DiffractResult)
        assert result.commit_type == CommitType.feat
        assert result.base_ref == "HEAD"
        assert result.head_ref == ":staged"

    def test_passes_src_path_to_has_python_changes_index(
        self,
        empty_diff: ApiDiff,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        mocker.patch("sheridan.diffract.checker.get_repo")
        mocker.patch("sheridan.diffract.checker.get_api_at_ref", return_value={})
        mocker.patch("sheridan.diffract.checker.get_api_at_index", return_value={})
        mock_changes = mocker.patch("sheridan.diffract.checker.has_python_changes_index", return_value=False)
        mocker.patch("sheridan.diffract.checker.diff_surfaces", return_value=empty_diff)
        mocker.patch("sheridan.diffract.checker.classify", return_value=(CommitType.fix, "ok"))

        check_staged(repo_path=Path("/tmp"), src_path="lib")

        mock_changes.assert_called_once_with(mocker.ANY, src_path="lib")

    def test_uses_head_as_base_ref(
        self,
        empty_diff: ApiDiff,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        mocker.patch("sheridan.diffract.checker.get_repo")
        mock_get_api_at_ref = mocker.patch(
            "sheridan.diffract.checker.get_api_at_ref",
            return_value={},
        )
        mocker.patch("sheridan.diffract.checker.get_api_at_index", return_value={})
        mocker.patch("sheridan.diffract.checker.has_python_changes_index", return_value=False)
        mocker.patch("sheridan.diffract.checker.diff_surfaces", return_value=empty_diff)
        mocker.patch("sheridan.diffract.checker.classify", return_value=(CommitType.fix, "ok"))

        check_staged(repo_path=Path("/tmp"))

        mock_get_api_at_ref.assert_called_once()
        call_args = mock_get_api_at_ref.call_args
        positional_ref = call_args.args[1] if len(call_args.args) > 1 else None
        resolved_ref = call_args.kwargs.get("ref", positional_ref)
        assert resolved_ref == "HEAD"

    def test_initial_commit_uses_empty_base_surface(
        self,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        mock_repo = mocker.MagicMock()
        mock_repo.head.is_valid.return_value = False
        mocker.patch("sheridan.diffract.checker.get_repo", return_value=mock_repo)
        mock_get_api_at_ref = mocker.patch("sheridan.diffract.checker.get_api_at_ref")
        mocker.patch(
            "sheridan.diffract.checker.get_api_at_index",
            return_value={"mod": ["NewClass"]},
        )
        mocker.patch("sheridan.diffract.checker.has_python_changes_index", return_value=True)
        mock_diff = mocker.patch("sheridan.diffract.checker.diff_surfaces")
        mocker.patch("sheridan.diffract.checker.classify", return_value=(CommitType.feat, "Added."))

        result = check_staged(repo_path=Path("/tmp"))

        assert isinstance(result, DiffractResult)
        assert result.commit_type == CommitType.feat
        # Before the first commit, HEAD has no commit to read.
        mock_get_api_at_ref.assert_not_called()
        # The base API is an empty dict.
        base_arg = mock_diff.call_args.args[0]
        assert base_arg == {}

    def test_surface_error_from_index_propagates(
        self,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        mocker.patch("sheridan.diffract.checker.get_repo")
        mocker.patch("sheridan.diffract.checker.get_api_at_ref", return_value={})
        mocker.patch(
            "sheridan.diffract.checker.get_api_at_index",
            side_effect=SurfaceError("index boom"),
        )

        with pytest.raises(SurfaceError, match="index boom"):
            check_staged(repo_path=Path("/tmp"))

    def test_defaults_repo_path_to_cwd(
        self,
        empty_diff: ApiDiff,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        mock_get_repo = mocker.patch("sheridan.diffract.checker.get_repo")
        mocker.patch("sheridan.diffract.checker.get_api_at_ref", return_value={})
        mocker.patch("sheridan.diffract.checker.get_api_at_index", return_value={})
        mocker.patch("sheridan.diffract.checker.has_python_changes_index", return_value=False)
        mocker.patch("sheridan.diffract.checker.diff_surfaces", return_value=empty_diff)
        mocker.patch("sheridan.diffract.checker.classify", return_value=(CommitType.fix, "ok"))

        check_staged()

        mock_get_repo.assert_called_once_with(Path.cwd())

    def test_propagates_git_error_from_get_repo(
        self,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        mocker.patch("sheridan.diffract.checker.get_repo", side_effect=GitError("no repo"))

        with pytest.raises(GitError, match="no repo"):
            check_staged(repo_path=Path("/tmp"))

    def test_passes_src_path_to_get_api_at_index(
        self,
        empty_diff: ApiDiff,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        mocker.patch("sheridan.diffract.checker.get_repo")
        mocker.patch("sheridan.diffract.checker.get_api_at_ref", return_value={})
        mock_index = mocker.patch("sheridan.diffract.checker.get_api_at_index", return_value={})
        mocker.patch("sheridan.diffract.checker.has_python_changes_index", return_value=False)
        mocker.patch("sheridan.diffract.checker.diff_surfaces", return_value=empty_diff)
        mocker.patch("sheridan.diffract.checker.classify", return_value=(CommitType.fix, "ok"))

        check_staged(repo_path=Path("/tmp"), src_path="lib")

        _, kwargs = mock_index.call_args
        assert kwargs["src_path"] == "lib"


class TestMissingSourceDirectory:
    """Tests for a ``src_path`` that does not exist at one ref or at the two refs."""

    def _patch(self, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        mocker.patch("sheridan.diffract.checker.get_repo")
        mocker.patch("sheridan.diffract.checker.has_python_changes", return_value=True)
        mocker.patch("sheridan.diffract.checker.has_python_changes_index", return_value=True)

    def test_missing_at_base_gives_an_empty_base(self, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """The names at the head are added, because the base API is empty."""
        self._patch(mocker)
        mocker.patch("sheridan.diffract.checker.get_api_at_ref", side_effect=[None, {"pkg": ["a"]}])

        result = check(repo_path=Path("/tmp"))

        assert result.commit_type == CommitType.feat
        assert [(c.module, c.name) for c in result.diff.added] == [("pkg", "a")]
        assert result.diff.removed == ()

    def test_missing_at_head_gives_an_empty_head(self, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """The names at the base are removed, because the head API is empty."""
        self._patch(mocker)
        mocker.patch("sheridan.diffract.checker.get_api_at_ref", side_effect=[{"pkg": ["a"]}, None])

        result = check(repo_path=Path("/tmp"))

        assert result.commit_type == CommitType.feat_breaking
        assert [(c.module, c.name) for c in result.diff.removed] == [("pkg", "a")]

    def test_missing_at_both_refs_raises(self, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """A missing source directory at the two refs is an error, not an empty diff."""
        self._patch(mocker)
        mocker.patch("sheridan.diffract.checker.get_api_at_ref", return_value=None)

        with pytest.raises(SurfaceError, match="'lib' does not exist at v1 or at v2"):
            check(base_ref="v1", head_ref="v2", repo_path=Path("/tmp"), src_path="lib")

    def test_staged_missing_at_head_and_index_raises(self, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """The commit-msg hook mode also fails if the directory is missing at HEAD and in the index."""
        self._patch(mocker)
        mocker.patch("sheridan.diffract.checker.get_api_at_ref", return_value=None)
        mocker.patch("sheridan.diffract.checker.get_api_at_index", return_value=None)

        with pytest.raises(SurfaceError, match="does not exist at HEAD or at the staging area"):
            check_staged(repo_path=Path("/tmp"))

    def test_staged_missing_at_head_gives_an_empty_base(self, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """The staged names are added names if the directory is missing at HEAD."""
        self._patch(mocker)
        mocker.patch("sheridan.diffract.checker.get_api_at_ref", return_value=None)
        mocker.patch("sheridan.diffract.checker.get_api_at_index", return_value={"pkg": ["a"]})

        result = check_staged(repo_path=Path("/tmp"))

        assert result.commit_type == CommitType.feat
