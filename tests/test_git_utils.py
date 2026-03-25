"""Tests for sheridan.diffract.git_utils."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sheridan.diffract.exceptions import GitError, SurfaceError
from sheridan.diffract.git_utils import (
    get_api_at_index,
    get_api_at_ref,
    get_repo,
    has_python_changes,
    has_python_changes_index,
)


class TestGetRepo:
    """Tests for get_repo()."""

    def test_raises_git_error_when_no_repo(self, tmp_path: Path, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """get_repo must raise GitError when no git repository exists at path."""
        from git import InvalidGitRepositoryError

        mocker.patch("sheridan.diffract.git_utils.Repo", side_effect=InvalidGitRepositoryError)
        with pytest.raises(GitError, match="No git repository found"):
            get_repo(tmp_path)

    def test_returns_repo_on_success(self, tmp_path: Path, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """get_repo must return the Repo instance when a repository is found."""
        mock_repo = MagicMock()
        mocker.patch("sheridan.diffract.git_utils.Repo", return_value=mock_repo)
        assert get_repo(tmp_path) is mock_repo


class TestHasPythonChanges:
    """Tests for has_python_changes()."""

    def _diff_item(self, a_path: str, b_path: str) -> MagicMock:
        item = MagicMock()
        item.a_path = a_path
        item.b_path = b_path
        return item

    def _repo_with_diff(self, items: list[MagicMock]) -> MagicMock:
        repo = MagicMock()
        repo.commit.return_value.diff.return_value = items
        return repo

    def test_returns_true_when_py_file_changed(self) -> None:
        """Must return True when a .py file appears in the diff."""
        repo = self._repo_with_diff([self._diff_item("module.py", "module.py")])
        assert has_python_changes(repo, "HEAD~1", "HEAD") is True

    def test_returns_false_when_only_non_py_files_changed(self) -> None:
        """Must return False when only non-.py files appear in the diff."""
        repo = self._repo_with_diff([self._diff_item("README.md", "README.md")])
        assert has_python_changes(repo, "HEAD~1", "HEAD") is False

    def test_returns_false_when_diff_is_empty(self) -> None:
        """Must return False when there are no diffed files at all."""
        repo = self._repo_with_diff([])
        assert has_python_changes(repo, "HEAD~1", "HEAD") is False

    def test_detects_py_change_via_b_path(self) -> None:
        """Must return True when b_path is a .py file (e.g. newly created file)."""
        repo = self._repo_with_diff([self._diff_item("", "new_module.py")])
        assert has_python_changes(repo, "HEAD~1", "HEAD") is True


class TestGetApiAtRef:
    """Tests for get_api_at_ref()."""

    def _setup_archive_mocks(
        self,
        repo: MagicMock,
        tmp_path: Path,
        mock_tmpdir: MagicMock,
        mock_tar_open: MagicMock,
    ) -> None:
        """Wire up the git archive + tarfile mocks shared across tests."""
        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        repo.git.archive.return_value = mock_proc
        mock_tmpdir.return_value.__enter__.return_value = str(tmp_path)
        mock_tmpdir.return_value.__exit__.return_value = False
        mock_tar_open.return_value.__enter__.return_value = MagicMock()
        mock_tar_open.return_value.__exit__.return_value = False

    def test_raises_git_error_for_bad_ref(self, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """Must raise GitError when the ref is not valid in the repository."""
        from git import BadName

        repo = MagicMock()
        repo.commit.side_effect = BadName("bad-ref")
        with pytest.raises(GitError, match="Unknown ref: bad-ref"):
            get_api_at_ref(repo, "bad-ref")

    def test_raises_surface_error_when_iceberg_fails(
        self,
        tmp_path: Path,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """Must raise SurfaceError when get_public_api raises."""
        repo = MagicMock()
        repo.commit.return_value = MagicMock()
        mock_tar_open = mocker.patch("sheridan.diffract.git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract.git_utils.tempfile.TemporaryDirectory")
        mocker.patch("sheridan.diffract.git_utils.get_public_api", side_effect=RuntimeError("boom"))
        self._setup_archive_mocks(repo, tmp_path, mock_tmpdir, mock_tar_open)

        with pytest.raises(SurfaceError, match="Failed to extract"):
            get_api_at_ref(repo, "HEAD")

    def test_returns_api_mapping_on_success(
        self,
        tmp_path: Path,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """Must return the dict from get_public_api when everything succeeds."""
        repo = MagicMock()
        repo.commit.return_value = MagicMock()
        expected: dict[str, list[str]] = {"mypackage.mod": ["Foo", "Bar"]}
        mock_tar_open = mocker.patch("sheridan.diffract.git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract.git_utils.tempfile.TemporaryDirectory")
        mocker.patch("sheridan.diffract.git_utils.get_public_api", return_value=expected)
        self._setup_archive_mocks(repo, tmp_path, mock_tmpdir, mock_tar_open)

        assert get_api_at_ref(repo, "HEAD") == expected

    def test_falls_back_to_tmp_root_when_src_path_missing(
        self,
        tmp_path: Path,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """Must fall back to the temp root when the src_path subdirectory does not exist."""
        repo = MagicMock()
        repo.commit.return_value = MagicMock()
        captured: list[Path] = []

        def capture(path: Path) -> dict[str, list[str]]:
            captured.append(path)
            return {}

        mock_tar_open = mocker.patch("sheridan.diffract.git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract.git_utils.tempfile.TemporaryDirectory")
        mocker.patch("sheridan.diffract.git_utils.get_public_api", side_effect=capture)
        self._setup_archive_mocks(repo, tmp_path, mock_tmpdir, mock_tar_open)

        # tmp_path has no "src" subdirectory, so the fallback to tmp root is triggered.
        get_api_at_ref(repo, "HEAD", src_path="src")
        assert captured[0] == tmp_path


class TestGetApiAtIndex:
    """Tests for get_api_at_index()."""

    def _setup_index_mocks(
        self,
        repo: MagicMock,
        tmp_path: Path,
        mock_tmpdir: MagicMock,
        mock_tar_open: MagicMock,
        tree_sha: str = "abc123",
    ) -> None:
        mock_tree = MagicMock()
        mock_tree.hexsha = tree_sha
        repo.index.write_tree.return_value = mock_tree

        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        repo.git.archive.return_value = mock_proc

        mock_tmpdir.return_value.__enter__.return_value = str(tmp_path)
        mock_tmpdir.return_value.__exit__.return_value = False
        mock_tar_open.return_value.__enter__.return_value = MagicMock()
        mock_tar_open.return_value.__exit__.return_value = False

    def test_returns_api_mapping_on_success(
        self,
        tmp_path: Path,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        repo = MagicMock()
        expected: dict[str, list[str]] = {"mypackage.mod": ["Foo", "Bar"]}
        mock_tar_open = mocker.patch("sheridan.diffract.git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract.git_utils.tempfile.TemporaryDirectory")
        mocker.patch("sheridan.diffract.git_utils.get_public_api", return_value=expected)
        self._setup_index_mocks(repo, tmp_path, mock_tmpdir, mock_tar_open)

        assert get_api_at_index(repo) == expected

    def test_uses_tree_sha_for_archive(
        self,
        tmp_path: Path,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        repo = MagicMock()
        mock_tar_open = mocker.patch("sheridan.diffract.git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract.git_utils.tempfile.TemporaryDirectory")
        mocker.patch("sheridan.diffract.git_utils.get_public_api", return_value={})
        self._setup_index_mocks(repo, tmp_path, mock_tmpdir, mock_tar_open, tree_sha="deadbeef")

        get_api_at_index(repo)

        repo.git.archive.assert_called_once_with("deadbeef", format="tar", as_process=True)

    def test_raises_surface_error_when_iceberg_fails(
        self,
        tmp_path: Path,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        repo = MagicMock()
        mock_tar_open = mocker.patch("sheridan.diffract.git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract.git_utils.tempfile.TemporaryDirectory")
        mocker.patch("sheridan.diffract.git_utils.get_public_api", side_effect=RuntimeError("boom"))
        self._setup_index_mocks(repo, tmp_path, mock_tmpdir, mock_tar_open)

        with pytest.raises(SurfaceError, match="Failed to extract public API from index"):
            get_api_at_index(repo)

    def test_propagates_exception_when_write_tree_fails(
        self,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        # write_tree() failures are not wrapped — they propagate to the caller.
        repo = MagicMock()
        repo.index.write_tree.side_effect = Exception("index error")

        with pytest.raises(Exception, match="index error"):
            get_api_at_index(repo)

    def test_falls_back_to_tmp_root_when_src_path_missing(
        self,
        tmp_path: Path,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        repo = MagicMock()
        captured: list[Path] = []

        def capture(path: Path) -> dict[str, list[str]]:
            captured.append(path)
            return {}

        mock_tar_open = mocker.patch("sheridan.diffract.git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract.git_utils.tempfile.TemporaryDirectory")
        mocker.patch("sheridan.diffract.git_utils.get_public_api", side_effect=capture)
        self._setup_index_mocks(repo, tmp_path, mock_tmpdir, mock_tar_open)

        # tmp_path has no "src" subdirectory, so the fallback to tmp root is triggered.
        get_api_at_index(repo, src_path="src")
        assert captured[0] == tmp_path


class TestHasPythonChangesIndex:
    """Tests for has_python_changes_index()."""

    def _diff_item(self, a_path: str, b_path: str) -> MagicMock:
        item = MagicMock()
        item.a_path = a_path
        item.b_path = b_path
        return item

    def test_returns_true_when_py_file_in_index_diff(self) -> None:
        repo = MagicMock()
        diff_item = self._diff_item("module.py", "module.py")
        repo.index.diff.return_value = [diff_item]
        assert has_python_changes_index(repo) is True

    def test_returns_false_when_only_non_py_files_in_index_diff(self) -> None:
        repo = MagicMock()
        diff_item = self._diff_item("README.md", "README.md")
        repo.index.diff.return_value = [diff_item]
        assert has_python_changes_index(repo) is False

    def test_returns_false_when_index_diff_is_empty(self) -> None:
        repo = MagicMock()
        repo.index.diff.return_value = []
        assert has_python_changes_index(repo) is False

    def test_returns_true_on_initial_commit(self) -> None:
        repo = MagicMock()
        # Simulate initial commit: accessing head.commit raises ValueError.
        type(repo.head).commit = property(lambda self: (_ for _ in ()).throw(ValueError("no HEAD")))
        assert has_python_changes_index(repo) is True

    def test_detects_py_change_via_b_path(self) -> None:
        repo = MagicMock()
        diff_item = self._diff_item("", "new_module.py")
        repo.index.diff.return_value = [diff_item]
        assert has_python_changes_index(repo) is True

    def test_diff_called_with_head_commit(self) -> None:
        repo = MagicMock()
        repo.index.diff.return_value = []
        has_python_changes_index(repo)
        repo.index.diff.assert_called_once_with(repo.head.commit)
