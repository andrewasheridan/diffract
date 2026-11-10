"""Tests for sheridan.diffract.git_utils."""

import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from git import Repo

from sheridan.diffract.exceptions import GitError, SurfaceError
from sheridan.diffract.git_utils import (
    get_api_at_index,
    get_api_at_ref,
    get_repo,
    has_python_changes,
    has_python_changes_index,
)
from sheridan.iceberg import Assignment, Module, Package


def _module(name: str, *names: str) -> Module:
    """Build an iceberg ``Module`` that has one public assignment for each name."""
    assignments = tuple(Assignment(name=n, annotation=None) for n in names)
    return Module(name=name, assignments=assignments, classes=(), functions=())


def _container(root: Path) -> Package:
    """Build the iceberg ``Package`` for a directory without ``__init__.py`` that holds ``mypackage.mod``."""
    mypackage = Package(
        name=f"{root.name}.mypackage",
        path=root / "mypackage",
        modules=(_module(f"{root.name}.mypackage.mod", "Foo", "Bar"),),
        subpackages=(),
    )
    return Package(name=root.name, path=root, modules=(), subpackages=(mypackage,))


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
        """Wire up the git archive + tarfile mocks shared across tests, with an empty ``src`` directory."""
        (tmp_path / "src").mkdir(exist_ok=True)
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
        """Must convert the iceberg tree to a map of module names to sorted public names."""
        repo = MagicMock()
        repo.commit.return_value = MagicMock()
        mock_tar_open = mocker.patch("sheridan.diffract.git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract.git_utils.tempfile.TemporaryDirectory")
        mocker.patch("sheridan.diffract.git_utils.get_public_api", return_value=_container(tmp_path / "src"))
        self._setup_archive_mocks(repo, tmp_path, mock_tmpdir, mock_tar_open)

        assert get_api_at_ref(repo, "HEAD") == {"mypackage.mod": ["Bar", "Foo"]}

    def test_returns_none_when_src_path_missing(
        self,
        tmp_path: Path,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """Must return None, and not read the root, when the src_path subdirectory does not exist."""
        repo = MagicMock()
        repo.commit.return_value = MagicMock()
        mock_tar_open = mocker.patch("sheridan.diffract.git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract.git_utils.tempfile.TemporaryDirectory")
        mock_api = mocker.patch("sheridan.diffract.git_utils.get_public_api")
        self._setup_archive_mocks(repo, tmp_path, mock_tmpdir, mock_tar_open)

        assert get_api_at_ref(repo, "HEAD", src_path="lib") is None
        mock_api.assert_not_called()

    def test_reads_the_root_when_src_path_is_a_dot(
        self,
        tmp_path: Path,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """Must read the temp root when src_path is ``"."``."""
        repo = MagicMock()
        repo.commit.return_value = MagicMock()
        captured: list[Path] = []

        def capture(path: Path) -> Package:
            captured.append(path)
            return _container(path)

        mock_tar_open = mocker.patch("sheridan.diffract.git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract.git_utils.tempfile.TemporaryDirectory")
        mocker.patch("sheridan.diffract.git_utils.get_public_api", side_effect=capture)
        self._setup_archive_mocks(repo, tmp_path, mock_tmpdir, mock_tar_open)

        assert get_api_at_ref(repo, "HEAD", src_path=".") == {"mypackage.mod": ["Bar", "Foo"]}
        assert captured == [tmp_path]


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
        repo.git.write_tree.return_value = tree_sha
        (tmp_path / "src").mkdir(exist_ok=True)

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
        mock_tar_open = mocker.patch("sheridan.diffract.git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract.git_utils.tempfile.TemporaryDirectory")
        mocker.patch("sheridan.diffract.git_utils.get_public_api", return_value=_container(tmp_path / "src"))
        self._setup_index_mocks(repo, tmp_path, mock_tmpdir, mock_tar_open)

        assert get_api_at_index(repo) == {"mypackage.mod": ["Bar", "Foo"]}

    def test_uses_tree_sha_for_archive(
        self,
        tmp_path: Path,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        repo = MagicMock()
        mock_tar_open = mocker.patch("sheridan.diffract.git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract.git_utils.tempfile.TemporaryDirectory")
        mocker.patch("sheridan.diffract.git_utils.get_public_api", return_value=_container(tmp_path / "src"))
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
        repo.git.write_tree.side_effect = Exception("index error")

        with pytest.raises(Exception, match="index error"):
            get_api_at_index(repo)

    def test_returns_none_when_src_path_missing(
        self,
        tmp_path: Path,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """Must return None, and not read the root, when the src_path subdirectory does not exist."""
        repo = MagicMock()
        mock_tar_open = mocker.patch("sheridan.diffract.git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract.git_utils.tempfile.TemporaryDirectory")
        mock_api = mocker.patch("sheridan.diffract.git_utils.get_public_api")
        self._setup_index_mocks(repo, tmp_path, mock_tmpdir, mock_tar_open)

        assert get_api_at_index(repo, src_path="lib") is None
        mock_api.assert_not_called()


class TestHasPythonChangesIndex:
    """Tests for has_python_changes_index()."""

    def _repo(self, diff_output: str) -> MagicMock:
        repo = MagicMock()
        repo.head.is_valid.return_value = True
        repo.git.diff.return_value = diff_output
        return repo

    def test_returns_true_when_py_file_in_index_diff(self) -> None:
        assert has_python_changes_index(self._repo("README.md\nmodule.py")) is True

    def test_returns_false_when_only_non_py_files_in_index_diff(self) -> None:
        assert has_python_changes_index(self._repo("README.md")) is False

    def test_returns_false_when_index_diff_is_empty(self) -> None:
        assert has_python_changes_index(self._repo("")) is False

    def test_returns_true_on_initial_commit(self) -> None:
        repo = self._repo("")
        repo.head.is_valid.return_value = False

        assert has_python_changes_index(repo) is True
        repo.git.diff.assert_not_called()

    def test_diffs_the_index_against_head_with_the_git_command(self) -> None:
        repo = self._repo("")

        has_python_changes_index(repo)

        repo.git.diff.assert_called_once_with("--cached", "--name-only", "--no-renames", "HEAD")
        repo.index.diff.assert_not_called()


class TestStagingAreaInARealRepository:
    """Run the index functions on a real repository with a temporary ``GIT_INDEX_FILE``."""

    def test_functions_read_git_index_file_and_do_not_write_git_index(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        for key in [key for key in os.environ if key.startswith("GIT_")]:
            monkeypatch.delenv(key)
        monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
        monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
        for role in ("AUTHOR", "COMMITTER"):
            monkeypatch.setenv(f"GIT_{role}_NAME", "Test")
            monkeypatch.setenv(f"GIT_{role}_EMAIL", "test@example.com")

        repo = Repo.init(tmp_path, initial_branch="main")
        (tmp_path / "README.md").write_text("# pkg\n", encoding="utf-8")
        repo.git.add("README.md")
        repo.git.commit("--quiet", "--no-verify", "--no-gpg-sign", "-m", "docs: x")
        index = tmp_path / ".git" / "index"
        staged = index.read_bytes()

        (tmp_path / "mod.py").write_text('__all__ = ["alpha"]\n\nalpha = 1\n', encoding="utf-8")
        temporary_index = tmp_path / "temporary-index"
        shutil.copyfile(index, temporary_index)
        monkeypatch.setenv("GIT_INDEX_FILE", str(temporary_index))
        repo.git.add("mod.py")

        assert has_python_changes_index(repo) is True
        assert get_api_at_index(repo, src_path=".") == {"mod": ["alpha"]}
        assert index.read_bytes() == staged


class TestReadApi:
    """Tests for the conversion of the iceberg tree. These tests run the real iceberg on files in ``tmp_path``."""

    def _write(self, root: Path, files: dict[str, str]) -> None:
        for relative, text in files.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")

    def _api(self, tmp_path: Path, src_path: str, mocker: pytest.fixture) -> dict[str, list[str]]:  # type: ignore[type-arg]
        """Run ``get_api_at_ref`` with the archive step mocked, so that iceberg reads ``tmp_path``."""
        repo = MagicMock()
        mocker.patch("sheridan.diffract.git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract.git_utils.tempfile.TemporaryDirectory")
        mock_tmpdir.return_value.__enter__.return_value = str(tmp_path)
        api = get_api_at_ref(repo, "HEAD", src_path=src_path)
        assert api is not None
        return api

    def test_collects_each_kind_of_public_name(self, tmp_path: Path, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """Must include assignments, classes, functions and unresolved references, sorted."""
        source = 'from os import sep\n__all__ = ["sep", "f", "C", "X"]\nX = 1\nclass C: ...\ndef f() -> None: ...\n'
        self._write(tmp_path, {"src/pkg/__init__.py": source})

        assert self._api(tmp_path, "src", mocker) == {"pkg": ["C", "X", "f", "sep"]}

    def test_names_do_not_include_the_source_directory(
        self,
        tmp_path: Path,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """Must remove the name of a source directory that is not a package, at each depth."""
        self._write(
            tmp_path,
            {
                "lib/top.py": "def top() -> None: ...\n",
                "lib/pkg/__init__.py": "A = 1\n",
                "lib/pkg/sub/mod.py": "B = 2\n",
            },
        )

        assert self._api(tmp_path, "lib", mocker) == {"top": ["top"], "pkg": ["A"], "pkg.sub.mod": ["B"]}

    def test_keeps_the_name_of_a_package_root(self, tmp_path: Path, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """Must keep the package name when ``src_path`` is itself a package."""
        self._write(tmp_path, {"src/pkg/__init__.py": "A = 1\n", "src/pkg/mod.py": "B = 2\n"})

        assert self._api(tmp_path, "src/pkg", mocker) == {"pkg": ["A"], "pkg.mod": ["B"]}

    def test_skips_private_modules(self, tmp_path: Path, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """Must not report the names in a private module."""
        self._write(tmp_path, {"src/pkg/__init__.py": "A = 1\n", "src/pkg/_impl.py": "B = 2\n"})

        assert self._api(tmp_path, "src", mocker) == {"pkg": ["A"]}

    def test_accepts_a_single_module(self, tmp_path: Path, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """Must accept a ``Module`` from iceberg, which it gives for one file."""
        (tmp_path / "src").mkdir()
        mocker.patch("sheridan.diffract.git_utils.get_public_api", return_value=_module("solo", "X"))

        assert self._api(tmp_path, "src", mocker) == {"solo": ["X"]}
