"""Tests for sheridan.diffract._git_utils."""

import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from git import Repo

from sheridan.diffract._differ import ApiSurface
from sheridan.diffract._exceptions import GitError, SurfaceError
from sheridan.diffract._git_utils import (
    get_api_at_index,
    get_api_at_ref,
    get_changed_paths,
    get_changed_paths_index,
    get_comment_prefixes,
    get_repo,
    has_python_changes,
)
from sheridan.iceberg import Assignment, Module, Package
from tests.unit.conftest import public_names


def _known(api: ApiSurface | None) -> ApiSurface:
    """Check that the source directory exists, then give its API."""
    assert api is not None
    return api


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


@pytest.fixture()
def git_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Repo:
    """Make an empty git repository in ``tmp_path``. The git configuration of the user has no effect."""
    for key in [key for key in os.environ if key.startswith("GIT_")]:
        monkeypatch.delenv(key)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "Test")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "test@example.com")

    return Repo.init(tmp_path, initial_branch="main")


def _commit(repo: Repo, files: dict[str, str]) -> None:
    """Write the files to the work tree, then commit them."""
    root = Path(repo.working_dir)
    for relative, text in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    repo.git.add("--all")
    repo.git.commit("--quiet", "--no-verify", "--no-gpg-sign", "-m", "chore: x")


class TestGetRepo:
    """Tests for get_repo()."""

    def test_finds_the_repository_from_a_subdirectory(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        git_repo: Repo,
    ) -> None:
        """get_repo must search from path, not from the current directory, and also in the parent directories."""
        subdirectory = tmp_path / "pkg" / "sub"
        subdirectory.mkdir(parents=True)
        monkeypatch.chdir(tmp_path.parent)

        assert Path(get_repo(subdirectory).working_dir).resolve() == tmp_path.resolve()

    def test_raises_git_error_when_no_repo(self, tmp_path: Path, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """get_repo must raise GitError if no git repository exists at path."""
        from git import InvalidGitRepositoryError

        mocker.patch("sheridan.diffract._git_utils.Repo", side_effect=InvalidGitRepositoryError)
        with pytest.raises(GitError, match="Cannot find a git repository"):
            get_repo(tmp_path)

    def test_returns_repo_on_success(self, tmp_path: Path, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """get_repo must give the Repo if a repository exists."""
        mock_repo = MagicMock()
        mocker.patch("sheridan.diffract._git_utils.Repo", return_value=mock_repo)
        assert get_repo(tmp_path) is mock_repo


class TestGetCommentPrefixes:
    """Tests for get_comment_prefixes() in a real repository."""

    def test_default_is_hash(self, git_repo: Repo) -> None:
        assert get_comment_prefixes(git_repo) == ("#",)

    @pytest.mark.parametrize(("key", "value"), [("commentChar", ";"), ("commentString", "//")])
    def test_reads_the_value(self, git_repo: Repo, key: str, value: str) -> None:
        git_repo.git.config(f"core.{key}", value)
        assert get_comment_prefixes(git_repo) == (value,)

    def test_last_value_has_priority(self, git_repo: Repo) -> None:
        git_repo.git.config("core.commentChar", ";")
        git_repo.git.config("core.commentString", "%")
        assert get_comment_prefixes(git_repo) == ("%",)

    def test_auto_gives_each_possible_character(self, git_repo: Repo) -> None:
        git_repo.git.config("core.commentChar", "auto")
        assert get_comment_prefixes(git_repo) == ("#", ";", "@", "!", "$", "%", "^", "&", "|", ":")


class TestHasPythonChanges:
    """Tests for has_python_changes()."""

    def test_returns_true_when_py_file_changed(self) -> None:
        assert has_python_changes(["README.md", "src/pkg/module.py"], "src") is True

    def test_returns_true_when_pyi_file_changed(self) -> None:
        """A stub file is part of the public API of the package."""
        assert has_python_changes(["src/pkg/module.pyi"], "src") is True

    def test_returns_false_when_only_non_py_files_changed(self) -> None:
        assert has_python_changes(["src/pkg/data.json", "README.md"], "src") is False

    def test_finds_a_py_file_after_a_file_that_is_not_python(self) -> None:
        assert has_python_changes(["README.md", "src/pkg/mod.py"], "src")

    def test_finds_a_py_file_after_a_file_in_the_excluded_directory(self) -> None:
        assert has_python_changes(["src/pkg/tests/test_mod.py", "src/pkg/mod.py"], "src", exclude="src/pkg/tests")

    def test_returns_false_when_no_path_changed(self) -> None:
        assert has_python_changes([], "src") is False

    @pytest.mark.parametrize(
        "path",
        ["tests/test_mod.py", "tests/stubs/mod.pyi", "scripts/tool.py", "docs/conf.py", "setup.py", "srcx/mod.py"],
    )
    def test_ignores_py_files_outside_the_directory(self, path: str) -> None:
        assert has_python_changes([path], "src") is False

    @pytest.mark.parametrize(
        ("directory", "path", "expected"),
        [
            ("lib", "lib/pkg/mod.py", True),
            ("lib/", "lib/pkg/mod.py", True),
            ("./lib", "lib/pkg/mod.py", True),
            ("lib", "src/pkg/mod.py", False),
            ("python/src", "python/src/pkg/mod.py", True),
            ("python/src", "python/tests/mod.py", False),
            (".", "tests/test_mod.py", True),
            (".", "flat.py", True),
        ],
    )
    def test_uses_the_given_directory(self, directory: str, path: str, expected: bool) -> None:
        assert has_python_changes([path], directory) is expected

    @pytest.mark.parametrize(
        ("exclude", "path", "expected"),
        [
            ("src/pkg/tests", "src/pkg/tests/test_mod.py", False),
            ("src/pkg/tests", "src/pkg/mod.py", True),
            ("tests", "tests/test_mod.py", False),
            ("tests", "src/pkg/mod.py", True),
        ],
    )
    def test_ignores_files_in_the_excluded_directory(self, exclude: str, path: str, expected: bool) -> None:
        assert has_python_changes([path], ".", exclude=exclude) is expected


class TestGetChangedPaths:
    """Tests for get_changed_paths()."""

    def _diff_item(self, a_path: str | None, b_path: str | None) -> MagicMock:
        item = MagicMock()
        item.a_path = a_path
        item.b_path = b_path
        return item

    def _repo_with_diff(self, items: list[MagicMock]) -> MagicMock:
        repo = MagicMock()
        repo.commit.return_value.diff.return_value = items
        return repo

    def test_returns_an_empty_list_when_diff_is_empty(self) -> None:
        assert get_changed_paths(self._repo_with_diff([]), "HEAD~1", "HEAD") == []

    def test_returns_the_two_paths_of_a_renamed_file(self) -> None:
        repo = self._repo_with_diff([self._diff_item("src/pkg/old.py", "tests/old.py")])
        assert get_changed_paths(repo, "HEAD~1", "HEAD") == ["src/pkg/old.py", "tests/old.py"]

    def test_skips_a_missing_path(self) -> None:
        """A new file has no a_path, and a deleted file has no b_path."""
        repo = self._repo_with_diff([self._diff_item(None, "src/pkg/new.py"), self._diff_item("README.md", None)])
        assert get_changed_paths(repo, "HEAD~1", "HEAD") == ["src/pkg/new.py", "README.md"]

    def test_compares_the_two_refs(self) -> None:
        repo = self._repo_with_diff([])

        get_changed_paths(repo, "v1", "v2")

        assert [c.args for c in repo.commit.call_args_list] == [("v1",), ("v2",)]


class TestGetApiAtRef:
    """Tests for get_api_at_ref()."""

    def _setup_archive_mocks(
        self,
        repo: MagicMock,
        tmp_path: Path,
        mock_tmpdir: MagicMock,
        mock_tar_open: MagicMock,
    ) -> None:
        """Set the git archive and tarfile mocks for the tests, with an empty ``src`` directory."""
        (tmp_path / "src").mkdir(exist_ok=True)
        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        repo.git.archive.return_value = mock_proc
        mock_tmpdir.return_value.__enter__.return_value = str(tmp_path)
        mock_tmpdir.return_value.__exit__.return_value = False
        mock_tar_open.return_value.__enter__.return_value = MagicMock()
        mock_tar_open.return_value.__exit__.return_value = False

    def test_raises_git_error_for_bad_ref(self, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """Must raise GitError if the ref does not exist in the repository."""
        from git import BadName

        repo = MagicMock()
        repo.commit.side_effect = BadName("bad-ref")
        with pytest.raises(GitError, match="The ref does not exist: bad-ref"):
            get_api_at_ref(repo, "bad-ref")

    def test_raises_surface_error_when_iceberg_fails(
        self,
        tmp_path: Path,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """Must raise SurfaceError if get_public_api raises an exception."""
        repo = MagicMock()
        repo.commit.return_value = MagicMock()
        mock_tar_open = mocker.patch("sheridan.diffract._git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract._git_utils.tempfile.TemporaryDirectory")
        mocker.patch("sheridan.diffract._git_utils.get_public_api", side_effect=RuntimeError("boom"))
        self._setup_archive_mocks(repo, tmp_path, mock_tmpdir, mock_tar_open)

        with pytest.raises(SurfaceError, match="Cannot extract the public API"):
            get_api_at_ref(repo, "HEAD")

    def test_returns_api_mapping_on_success(
        self,
        tmp_path: Path,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """Must convert the iceberg tree to a dict from module names to sorted public names."""
        repo = MagicMock()
        repo.commit.return_value = MagicMock()
        mock_tar_open = mocker.patch("sheridan.diffract._git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract._git_utils.tempfile.TemporaryDirectory")
        mocker.patch("sheridan.diffract._git_utils.get_public_api", return_value=_container(tmp_path / "src"))
        self._setup_archive_mocks(repo, tmp_path, mock_tmpdir, mock_tar_open)

        assert public_names(_known(get_api_at_ref(repo, "HEAD"))) == {"mypackage.mod": ["Bar", "Foo"]}

    def test_returns_none_when_src_path_missing(
        self,
        tmp_path: Path,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """Must give None, and not read the root, if the src_path directory does not exist."""
        repo = MagicMock()
        repo.commit.return_value = MagicMock()
        mock_tar_open = mocker.patch("sheridan.diffract._git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract._git_utils.tempfile.TemporaryDirectory")
        mock_api = mocker.patch("sheridan.diffract._git_utils.get_public_api")
        self._setup_archive_mocks(repo, tmp_path, mock_tmpdir, mock_tar_open)

        assert get_api_at_ref(repo, "HEAD", src_path="lib") is None
        mock_api.assert_not_called()

    def test_reads_the_root_when_src_path_is_a_dot(
        self,
        tmp_path: Path,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """Must read the temporary root if src_path is ``"."``."""
        repo = MagicMock()
        repo.commit.return_value = MagicMock()
        captured: list[Path] = []

        def capture(path: Path) -> Package:
            captured.append(path)
            return _container(path)

        mock_tar_open = mocker.patch("sheridan.diffract._git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract._git_utils.tempfile.TemporaryDirectory")
        mocker.patch("sheridan.diffract._git_utils.get_public_api", side_effect=capture)
        self._setup_archive_mocks(repo, tmp_path, mock_tmpdir, mock_tar_open)

        assert public_names(_known(get_api_at_ref(repo, "HEAD", src_path="."))) == {"mypackage.mod": ["Bar", "Foo"]}
        assert captured == [tmp_path]

    def test_archives_only_the_src_path(
        self,
        tmp_path: Path,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """Must give the source directory to ``git archive`` as a pathspec."""
        repo = MagicMock()
        mock_tar_open = mocker.patch("sheridan.diffract._git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract._git_utils.tempfile.TemporaryDirectory")
        mocker.patch("sheridan.diffract._git_utils.get_public_api", return_value=_container(tmp_path / "src"))
        self._setup_archive_mocks(repo, tmp_path, mock_tmpdir, mock_tar_open)

        get_api_at_ref(repo, "HEAD", src_path="src/")

        repo.git.archive.assert_called_once_with("HEAD", "--", "src", format="tar", as_process=True)

    def test_archives_the_full_tree_when_src_path_is_a_dot(
        self,
        tmp_path: Path,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """Must not give a pathspec to ``git archive`` for the repository root."""
        repo = MagicMock()
        mock_tar_open = mocker.patch("sheridan.diffract._git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract._git_utils.tempfile.TemporaryDirectory")
        mocker.patch("sheridan.diffract._git_utils.get_public_api", return_value=_container(tmp_path))
        self._setup_archive_mocks(repo, tmp_path, mock_tmpdir, mock_tar_open)

        get_api_at_ref(repo, "HEAD", src_path=".")

        repo.git.archive.assert_called_once_with("HEAD", format="tar", as_process=True)
        repo.git.ls_tree.assert_not_called()

    def test_does_not_archive_when_src_path_is_not_in_the_tree(
        self,
        tmp_path: Path,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """Must give None before it runs ``git archive``, which fails for a pathspec that has no match."""
        repo = MagicMock()
        mock_tar_open = mocker.patch("sheridan.diffract._git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract._git_utils.tempfile.TemporaryDirectory")
        self._setup_archive_mocks(repo, tmp_path, mock_tmpdir, mock_tar_open)
        repo.git.ls_tree.return_value = ""

        assert get_api_at_ref(repo, "HEAD", src_path="lib") is None
        repo.git.archive.assert_not_called()

    def test_raises_git_error_when_git_archive_fails(
        self,
        tmp_path: Path,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """Must raise GitError if ``git archive`` exits with an error."""
        from git import GitCommandError

        repo = MagicMock()
        mock_tar_open = mocker.patch("sheridan.diffract._git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract._git_utils.tempfile.TemporaryDirectory")
        self._setup_archive_mocks(repo, tmp_path, mock_tmpdir, mock_tar_open)
        repo.git.archive.return_value.wait.side_effect = GitCommandError(["git", "archive"], 128)

        with pytest.raises(GitError, match="Cannot extract 'src' at 'HEAD'"):
            get_api_at_ref(repo, "HEAD")

    def test_raises_git_error_when_tar_refuses_a_member(
        self,
        tmp_path: Path,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """Must raise GitError if the ``data`` filter refuses a file."""
        import tarfile

        repo = MagicMock()
        mock_tar_open = mocker.patch("sheridan.diffract._git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract._git_utils.tempfile.TemporaryDirectory")
        self._setup_archive_mocks(repo, tmp_path, mock_tmpdir, mock_tar_open)
        refused = tarfile.AbsoluteLinkError(tarfile.TarInfo("src/link"))
        mock_tar_open.return_value.__enter__.return_value.extractall.side_effect = refused

        with pytest.raises(GitError, match="is a link to an absolute path"):
            get_api_at_ref(repo, "HEAD")


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
        mock_tar_open = mocker.patch("sheridan.diffract._git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract._git_utils.tempfile.TemporaryDirectory")
        mocker.patch("sheridan.diffract._git_utils.get_public_api", return_value=_container(tmp_path / "src"))
        self._setup_index_mocks(repo, tmp_path, mock_tmpdir, mock_tar_open)

        assert public_names(_known(get_api_at_index(repo))) == {"mypackage.mod": ["Bar", "Foo"]}

    def test_uses_tree_sha_for_archive(
        self,
        tmp_path: Path,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        repo = MagicMock()
        mock_tar_open = mocker.patch("sheridan.diffract._git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract._git_utils.tempfile.TemporaryDirectory")
        mocker.patch("sheridan.diffract._git_utils.get_public_api", return_value=_container(tmp_path / "src"))
        self._setup_index_mocks(repo, tmp_path, mock_tmpdir, mock_tar_open, tree_sha="deadbeef")

        get_api_at_index(repo)

        repo.git.archive.assert_called_once_with("deadbeef", "--", "src", format="tar", as_process=True)

    def test_raises_surface_error_when_iceberg_fails(
        self,
        tmp_path: Path,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        repo = MagicMock()
        mock_tar_open = mocker.patch("sheridan.diffract._git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract._git_utils.tempfile.TemporaryDirectory")
        mocker.patch("sheridan.diffract._git_utils.get_public_api", side_effect=RuntimeError("boom"))
        self._setup_index_mocks(repo, tmp_path, mock_tmpdir, mock_tar_open)

        with pytest.raises(SurfaceError, match="Cannot extract the public API from the staging area"):
            get_api_at_index(repo)

    def test_propagates_exception_when_write_tree_fails(
        self,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        # The function does not change a write_tree() error. The caller gets the error.
        repo = MagicMock()
        repo.git.write_tree.side_effect = Exception("index error")

        with pytest.raises(Exception, match="index error"):
            get_api_at_index(repo)

    def test_returns_none_when_src_path_missing(
        self,
        tmp_path: Path,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """Must give None, and not read the root, if the src_path directory does not exist."""
        repo = MagicMock()
        mock_tar_open = mocker.patch("sheridan.diffract._git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract._git_utils.tempfile.TemporaryDirectory")
        mock_api = mocker.patch("sheridan.diffract._git_utils.get_public_api")
        self._setup_index_mocks(repo, tmp_path, mock_tmpdir, mock_tar_open)

        assert get_api_at_index(repo, src_path="lib") is None
        mock_api.assert_not_called()


class TestGetChangedPathsIndex:
    """Tests for get_changed_paths_index()."""

    def _repo(self, diff_output: str) -> MagicMock:
        repo = MagicMock()
        repo.head.is_valid.return_value = True
        repo.git.diff.return_value = diff_output
        return repo

    def test_returns_each_path_in_the_index_diff(self) -> None:
        assert get_changed_paths_index(self._repo("README.md\nsrc/pkg/module.py")) == ["README.md", "src/pkg/module.py"]

    def test_returns_an_empty_list_when_index_diff_is_empty(self) -> None:
        assert get_changed_paths_index(self._repo("")) == []

    def test_returns_all_staged_files_on_initial_commit(self) -> None:
        repo = self._repo("")
        repo.head.is_valid.return_value = False
        repo.git.ls_files.return_value = "README.md\nsrc/pkg/mod.py"

        assert get_changed_paths_index(repo) == ["README.md", "src/pkg/mod.py"]
        repo.git.diff.assert_not_called()

    def test_diffs_the_index_against_head_with_the_git_command(self) -> None:
        repo = self._repo("")

        get_changed_paths_index(repo)

        repo.git.diff.assert_called_once_with("--cached", "--name-only", "--no-renames", "HEAD")
        repo.index.diff.assert_not_called()


class TestStagingAreaInARealRepository:
    """Run the index functions on a real repository with a temporary ``GIT_INDEX_FILE``."""

    def test_functions_read_git_index_file_and_do_not_write_git_index(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        git_repo: Repo,
    ) -> None:
        _commit(git_repo, {"README.md": "# pkg\n"})
        index = tmp_path / ".git" / "index"
        staged = index.read_bytes()

        (tmp_path / "mod.py").write_text('__all__ = ["alpha"]\n\nalpha = 1\n', encoding="utf-8")
        temporary_index = tmp_path / "temporary-index"
        shutil.copyfile(index, temporary_index)
        monkeypatch.setenv("GIT_INDEX_FILE", str(temporary_index))
        git_repo.git.add("mod.py")

        assert get_changed_paths_index(git_repo) == ["mod.py"]
        assert public_names(_known(get_api_at_index(git_repo, src_path="."))) == {"mod": ["alpha"]}
        assert index.read_bytes() == staged


class TestRealRepository:
    """Tests for the functions that read the commits of a real repository."""

    def test_changed_paths_compare_the_two_refs_and_not_the_work_tree(self, git_repo: Repo) -> None:
        _commit(git_repo, {"README.md": "# pkg\n"})
        _commit(git_repo, {"a.py": "A = 1\n"})
        _commit(git_repo, {"b.py": "B = 2\n"})

        # For an added file, GitPython gives the same a_path and b_path.
        assert get_changed_paths(git_repo, "HEAD~2", "HEAD~1") == ["a.py", "a.py"]

    def test_api_at_ref_is_none_when_src_path_is_not_in_the_tree(self, git_repo: Repo) -> None:
        _commit(git_repo, {"src/pkg/__init__.py": "A = 1\n"})

        assert get_api_at_ref(git_repo, "HEAD", src_path="lib") is None

    def test_api_at_ref_raises_git_error_for_a_bad_ref(self, git_repo: Repo) -> None:
        _commit(git_repo, {"src/pkg/__init__.py": "A = 1\n"})

        with pytest.raises(GitError, match=r"^The ref does not exist: nope$"):
            get_api_at_ref(git_repo, "nope")


class TestReadApi:
    """Tests for the conversion of the iceberg tree. These tests run the real iceberg on files in ``tmp_path``."""

    def _write(self, root: Path, files: dict[str, str]) -> None:
        for relative, text in files.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")

    def _api(self, tmp_path: Path, src_path: str, mocker: pytest.fixture) -> ApiSurface:  # type: ignore[type-arg]
        """Run ``get_api_at_ref`` with the archive step mocked, so that iceberg reads ``tmp_path``."""
        repo = MagicMock()
        mocker.patch("sheridan.diffract._git_utils.tarfile.open")
        mock_tmpdir = mocker.patch("sheridan.diffract._git_utils.tempfile.TemporaryDirectory")
        mock_tmpdir.return_value.__enter__.return_value = str(tmp_path)
        api = get_api_at_ref(repo, "HEAD", src_path=src_path)
        assert api is not None
        return api

    def test_collects_each_kind_of_public_name(self, tmp_path: Path, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """Must include assignments, classes, functions and unresolved references, sorted."""
        source = 'from os import sep\n__all__ = ["sep", "f", "C", "X"]\nX = 1\nclass C: ...\ndef f() -> None: ...\n'
        self._write(tmp_path, {"src/pkg/__init__.py": source})

        assert public_names(self._api(tmp_path, "src", mocker)) == {"pkg": ["C", "X", "f", "sep"]}

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

        assert public_names(self._api(tmp_path, "lib", mocker)) == {"top": ["top"], "pkg": ["A"], "pkg.sub.mod": ["B"]}

    def test_keeps_the_name_of_a_package_root(self, tmp_path: Path, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """Must keep the package name if ``src_path`` is a package."""
        self._write(tmp_path, {"src/pkg/__init__.py": "A = 1\n", "src/pkg/mod.py": "B = 2\n"})

        assert public_names(self._api(tmp_path, "src/pkg", mocker)) == {"pkg": ["A"], "pkg.mod": ["B"]}

    def test_skips_private_modules(self, tmp_path: Path, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """Must not give the names in a private module."""
        self._write(tmp_path, {"src/pkg/__init__.py": "A = 1\n", "src/pkg/_impl.py": "B = 2\n"})

        assert public_names(self._api(tmp_path, "src", mocker)) == {"pkg": ["A"]}

    def test_accepts_a_single_module(self, tmp_path: Path, mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
        """Must accept a ``Module`` from iceberg, which it gives for one file."""
        (tmp_path / "src").mkdir()
        mocker.patch("sheridan.diffract._git_utils.get_public_api", return_value=_module("solo", "X"))

        assert public_names(self._api(tmp_path, "src", mocker)) == {"solo": ["X"]}
