"""Tests for sheridan.diffract._cli."""

import argparse
import json
import sys
from pathlib import Path

import pytest

from sheridan.diffract import __version__
from sheridan.diffract._cli import (
    _build_parser,
    _describe_allowed,
    _format_commit_type,
    _format_human,
    _is_allowed,
    _is_feat_without_api_change,
    _is_written_by_git,
    _parse_written_type,
    _remove_comments,
    _resolve_exit_code,
    _WrittenType,
    main,
)
from sheridan.diffract._config import DiffractConfig
from sheridan.diffract._enums import ChangeKind, CommitType
from sheridan.diffract._exceptions import GitError
from sheridan.diffract._models import ApiDiff, DiffractResult, NameChange, SignatureChange


def _make_result(
    commit_type: CommitType,
    diff: ApiDiff,
    summary: str = "summary",
    base_ref: str = "HEAD~1",
    head_ref: str = "HEAD",
) -> DiffractResult:
    """Build a DiffractResult for the tests."""
    return DiffractResult(
        commit_type=commit_type,
        summary=summary,
        diff=diff,
        base_ref=base_ref,
        head_ref=head_ref,
    )


_MSG_FILE_HELP = (
    "The path of a commit message file. The check fails if the commit type tells less than "
    "the change to the public API. Removed public names and breaking changes need a '!' or a "
    "'BREAKING CHANGE:' footer. Added public names need 'feat' or a '!'. If no public name "
    "changed, each known type passes. A message with no known type fails. diffract does not "
    "check merge, revert, fixup, amend and squash messages from git."
)

# One row for each argument: (option strings, dest, nargs, default, metavar, help, action class).
_EXPECTED_ACTIONS: list[tuple[list[str], str, int | str | None, object, str | None, str, str]] = [
    (["-h", "--help"], "help", 0, argparse.SUPPRESS, None, "show this help message and exit", "_HelpAction"),
    (["--version"], "version", 0, argparse.SUPPRESS, None, "show program's version number and exit", "_VersionAction"),
    (
        [],
        "base_ref",
        "?",
        None,
        "BASE_REF",
        "The earlier git ref to compare (default: HEAD~1). "
        "If you use --validate-msg-file and give no refs, "
        "diffract compares HEAD with the staging area.",
        "_StoreAction",
    ),
    (
        [],
        "head_ref",
        "?",
        None,
        "HEAD_REF",
        "The later git ref to compare (default: HEAD). "
        "If you give only BASE_REF, diffract uses HEAD as HEAD_REF. "
        "If you use --validate-msg-file and give no refs, "
        "diffract compares HEAD with the staging area.",
        "_StoreAction",
    ),
    (
        ["--src"],
        "src_path",
        None,
        None,
        "SRC",
        "The directory in the repository that contains the Python packages (default: src).",
        "_StoreAction",
    ),
    (
        ["--tests"],
        "tests_path",
        None,
        None,
        "TESTS",
        "The directory in the repository that contains the tests (default: tests).",
        "_StoreAction",
    ),
    (["--json"], "output_json", 0, False, None, "Write JSON to stdout, not text.", "_StoreTrueAction"),
    (
        ["--exit-code"],
        "exit_code",
        0,
        False,
        None,
        "Exit 1 if a public name was removed or had a breaking change, 2 if a public name was added "
        "or had a change that only adds to it, and 0 if no public name changed.",
        "_StoreTrueAction",
    ),
    (["--validate-msg-file"], "validate_msg_file", None, None, "MSGFILE", _MSG_FILE_HELP, "_StoreAction"),
]


class TestBuildParser:
    """Tests for _build_parser().

    The functional tests start the CLI in a subprocess, thus mutmut cannot see them.
    These tests examine the parser directly.
    """

    def test_prog_and_description(self) -> None:
        """The parser must have the correct program name and description."""
        parser = _build_parser()
        assert parser.prog == "diffract"
        assert parser.description == (
            "Find the public API changes between two git refs and give the possible commit types."
        )

    def test_actions(self) -> None:
        """Each argument must have the correct flags, destination, default, metavar and help."""
        actions = [
            (
                action.option_strings,
                action.dest,
                action.nargs,
                action.default,
                action.metavar,
                action.help,
                type(action).__name__,
            )
            for action in _build_parser()._actions
        ]
        assert actions == _EXPECTED_ACTIONS

    def test_version(self, capsys: pytest.CaptureFixture[str]) -> None:
        """The --version flag must write the program name and the version."""
        with pytest.raises(SystemExit) as exc_info:
            _build_parser().parse_args(["--version"])
        assert exc_info.value.code == 0
        assert capsys.readouterr().out == f"diffract {__version__}\n"

    def test_usage_error_exits_three(self, capsys: pytest.CaptureFixture[str]) -> None:
        """A usage error must exit 3 and write the error to stderr."""
        with pytest.raises(SystemExit) as exc_info:
            _build_parser().parse_args(["--unknown"])
        assert exc_info.value.code == 3
        assert "diffract: error: unrecognized arguments: --unknown" in capsys.readouterr().err


class TestFormatHuman:
    """Tests for _format_human()."""

    def test_full_output_for_all_kinds_of_change(self) -> None:
        """The output must have each section, with the exact headings, markers and blank lines."""
        diff = ApiDiff(
            added=(NameChange(module="pkg.mod", name="New", kind=ChangeKind.added),),
            removed=(NameChange(module="pkg.mod", name="Old", kind=ChangeKind.removed),),
            changed=(
                SignatureChange(module="pkg.mod", name="f", detail="parameter 'x' was removed", is_breaking=True),
                SignatureChange(module="pkg.mod", name="g", detail="*args was added", is_breaking=False),
            ),
        )

        output = _format_human(_make_result(CommitType.feat_breaking, diff))

        assert output == (
            "Detected: feat!  (breaking change)\n"
            "\n"
            "Removed public names:\n"
            "  pkg.mod:\n"
            "    - Old\n"
            "Added public names:\n"
            "  pkg.mod:\n"
            "    + New\n"
            "Breaking changes:\n"
            "  pkg.mod:\n"
            "    ! f: parameter 'x' was removed\n"
            "Changes that add to public names:\n"
            "  pkg.mod:\n"
            "    ~ g: *args was added\n"
            "\n"
            "Suggested commit prefix: feat!:"
        )

    def test_full_output_for_no_change(self, empty_diff: ApiDiff) -> None:
        """The output for a result with no API change must have the exact text and blank lines."""
        output = _format_human(_make_result(CommitType.other, empty_diff))

        assert output == (
            "Detected: other\n\nThe public API did not change.\n\nThis can be a docs, ci, chore or build commit."
        )

    def test_no_changes_output(self) -> None:
        """The output for an other result must give the possible types and no prefix."""
        result = _make_result(CommitType.other, ApiDiff(added=(), removed=()))
        output = _format_human(result)
        assert "The public API did not change." in output
        assert "This can be a docs, ci, chore or build commit." in output
        assert "Suggested commit prefix" not in output

    def test_breaking_change_output(self, removal_diff: ApiDiff) -> None:
        """The output for a feat! result must say that it is a breaking change."""
        result = _make_result(CommitType.feat_breaking, removal_diff)
        output = _format_human(result)
        assert "breaking change" in output
        assert "feat!:" in output

    def test_addition_output_lists_names(self, addition_diff: ApiDiff) -> None:
        """The output for a feat result must list the added public names."""
        result = _make_result(CommitType.feat, addition_diff)
        output = _format_human(result)
        assert "Added public names" in output
        assert "NewClass" in output

    def test_removal_output_lists_names(self, removal_diff: ApiDiff) -> None:
        """The output for a feat! result must list the removed public names."""
        result = _make_result(CommitType.feat_breaking, removal_diff)
        output = _format_human(result)
        assert "Removed public names" in output
        assert "OldClass" in output

    def test_code_output(self, empty_diff: ApiDiff) -> None:
        """The output for a code result must give the possible types and no prefix."""
        result = _make_result(CommitType.code, empty_diff)
        output = _format_human(result)
        assert "Detected: code" in output
        assert "This can be a fix, refactor, perf, style or docs commit." in output
        assert "Suggested commit prefix" not in output

    def test_test_output(self, empty_diff: ApiDiff) -> None:
        """The output for a test result must give the one possible type and no prefix."""
        result = _make_result(CommitType.test, empty_diff)
        output = _format_human(result)
        assert "This can be a test commit." in output
        assert "Suggested commit prefix" not in output

    @pytest.mark.parametrize(
        ("commit_type", "prefix"),
        [(CommitType.feat, "feat:"), (CommitType.feat_breaking, "feat!:")],
    )
    def test_feature_output_has_a_suggested_prefix(
        self, commit_type: CommitType, prefix: str, addition_diff: ApiDiff
    ) -> None:
        output = _format_human(_make_result(commit_type, addition_diff))
        assert f"Suggested commit prefix: {prefix}" in output
        assert "This can be" not in output


class TestResolveExitCode:
    """Tests for _resolve_exit_code()."""

    def test_always_zero_without_flag(self, removal_diff: ApiDiff) -> None:
        """Without --exit-code, the exit code must always be 0."""
        result = _make_result(CommitType.feat_breaking, removal_diff)
        assert _resolve_exit_code(result, use_exit_code=False) == 0

    def test_one_for_breaking_with_flag(self, removal_diff: ApiDiff) -> None:
        """With --exit-code, a breaking change must give exit code 1."""
        result = _make_result(CommitType.feat_breaking, removal_diff)
        assert _resolve_exit_code(result, use_exit_code=True) == 1

    def test_two_for_non_breaking_api_change_with_flag(self, addition_diff: ApiDiff) -> None:
        """With --exit-code, an API change that is not breaking must give exit code 2."""
        result = _make_result(CommitType.feat, addition_diff)
        assert _resolve_exit_code(result, use_exit_code=True) == 2

    def test_zero_for_no_changes_with_flag(self, empty_diff: ApiDiff) -> None:
        """With --exit-code, no change must give exit code 0."""
        result = _make_result(CommitType.other, empty_diff)
        assert _resolve_exit_code(result, use_exit_code=True) == 0


class TestMain:
    """Integration tests for main()."""

    def test_version_flag_exits_zero(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """'diffract --version' must exit 0."""
        monkeypatch.setattr(sys, "argv", ["diffract", "--version"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_human_output_exits_zero(
        self,
        empty_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """'diffract' must print text and exit 0 by default."""
        result = _make_result(CommitType.other, empty_diff)
        monkeypatch.setattr(sys, "argv", ["diffract"])
        mocker.patch("sheridan.diffract._cli.check", return_value=result)
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        assert "Detected: other" in capsys.readouterr().out

    def test_json_output(
        self,
        empty_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """'diffract --json' must write correct JSON to stdout."""
        result = _make_result(CommitType.other, empty_diff)
        monkeypatch.setattr(sys, "argv", ["diffract", "--json"])
        mocker.patch("sheridan.diffract._cli.check", return_value=result)
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["group"] == "other"
        assert parsed["possible_types"] == ["docs", "ci", "chore", "build"]
        assert out == json.dumps(result.to_dict(), indent=2) + "\n"

    def test_diffract_error_exits_three(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """'diffract' must print to stderr and exit 3 for a DiffractError."""
        monkeypatch.setattr(sys, "argv", ["diffract"])
        mocker.patch("sheridan.diffract._cli.check", side_effect=GitError("no repo found"))
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 3
        assert "no repo found" in capsys.readouterr().err

    @pytest.mark.parametrize(
        "argv",
        [
            ["diffract", "--bogus"],
            ["diffract", "a", "b", "c"],
        ],
    )
    def test_usage_error_exits_three(
        self,
        argv: list[str],
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """'diffract' must print the usage and exit 3 for a usage error, not 2 as for an API change."""
        monkeypatch.setattr(sys, "argv", argv)
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 3
        assert "usage: diffract" in capsys.readouterr().err

    def test_unexpected_error_exits_three(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """'diffract' must print a short message with the issue tracker and exit 3 for an unexpected exception."""
        monkeypatch.setattr(sys, "argv", ["diffract"])
        mocker.patch("sheridan.diffract._cli.check", side_effect=RuntimeError("iceberg crashed"))
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 3
        err = capsys.readouterr().err
        assert "RuntimeError: iceberg crashed" in err
        assert "https://github.com/andrewasheridan/diffract/issues" in err
        assert "Traceback" not in err

    @pytest.mark.parametrize(
        ("file_name", "content"),
        [
            ("diffract.toml", "src = 3\n"),
            ("pyproject.toml", '[tool]\ndiffract = "x"\n'),
        ],
    )
    def test_invalid_config_exits_three(
        self,
        file_name: str,
        content: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """'diffract' must print an error without a traceback and exit 3 if the configuration file is not correct."""
        (tmp_path / file_name).write_text(content, encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["diffract"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 3
        err = capsys.readouterr().err
        assert err.startswith("Error: ")
        assert file_name in err
        assert "Traceback" not in err

    def test_exit_code_breaking(
        self,
        removal_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """'diffract --exit-code' must exit 1 for a breaking change."""
        result = _make_result(CommitType.feat_breaking, removal_diff)
        monkeypatch.setattr(sys, "argv", ["diffract", "--exit-code"])
        mocker.patch("sheridan.diffract._cli.check", return_value=result)
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_exit_code_addition(
        self,
        addition_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """'diffract --exit-code' must exit 2 for an API change that is not breaking."""
        result = _make_result(CommitType.feat, addition_diff)
        monkeypatch.setattr(sys, "argv", ["diffract", "--exit-code"])
        mocker.patch("sheridan.diffract._cli.check", return_value=result)
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2

    def test_forwards_custom_refs_and_src(
        self,
        empty_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """'diffract' must give the positional refs and --src to check()."""
        result = _make_result(CommitType.other, empty_diff, base_ref="v1.0", head_ref="v2.0")
        monkeypatch.setattr(sys, "argv", ["diffract", "v1.0", "v2.0", "--src", "lib"])
        mock_check = mocker.patch("sheridan.diffract._cli.check", return_value=result)
        with pytest.raises(SystemExit):
            main()
        mock_check.assert_called_once()
        kwargs = mock_check.call_args.kwargs
        assert kwargs["base_ref"] == "v1.0"
        assert kwargs["head_ref"] == "v2.0"
        assert kwargs["src_path"] == "lib"

    def test_mixed_diff_shows_both_sections(
        self,
        mixed_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """The output for removed and added names must show the two lists."""
        result = _make_result(CommitType.feat_breaking, mixed_diff)
        monkeypatch.setattr(sys, "argv", ["diffract"])
        mocker.patch("sheridan.diffract._cli.check", return_value=result)
        with pytest.raises(SystemExit):
            main()
        out = capsys.readouterr().out
        assert "Removed public names" in out
        assert "Added public names" in out

    def test_src_from_config_used_when_no_flag(
        self,
        empty_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """main() must use src from the configuration file if there is no --src."""
        result = _make_result(CommitType.other, empty_diff)
        monkeypatch.setattr(sys, "argv", ["diffract"])
        mocker.patch("sheridan.diffract._cli.load_config", return_value=DiffractConfig(src="python/src"))
        mock_check = mocker.patch("sheridan.diffract._cli.check", return_value=result)
        with pytest.raises(SystemExit):
            main()
        kwargs = mock_check.call_args.kwargs
        assert kwargs["src_path"] == "python/src"

    def test_cli_flag_overrides_config_src(
        self,
        empty_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """main() must use --src, not the value in the configuration file."""
        result = _make_result(CommitType.other, empty_diff)
        monkeypatch.setattr(sys, "argv", ["diffract", "--src", "cli-src"])
        mocker.patch("sheridan.diffract._cli.load_config", return_value=DiffractConfig(src="config-src"))
        mock_check = mocker.patch("sheridan.diffract._cli.check", return_value=result)
        with pytest.raises(SystemExit):
            main()
        kwargs = mock_check.call_args.kwargs
        assert kwargs["src_path"] == "cli-src"

    def test_default_src_used_when_no_flag_and_no_config(
        self,
        empty_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """main() must use 'src' if --src and the configuration file give no value."""
        result = _make_result(CommitType.other, empty_diff)
        monkeypatch.setattr(sys, "argv", ["diffract"])
        mocker.patch("sheridan.diffract._cli.load_config", return_value=DiffractConfig())
        mock_check = mocker.patch("sheridan.diffract._cli.check", return_value=result)
        with pytest.raises(SystemExit):
            main()
        kwargs = mock_check.call_args.kwargs
        assert kwargs["src_path"] == "src"

    @pytest.mark.parametrize(
        ("argv", "config", "expected"),
        [
            (["diffract"], DiffractConfig(), "tests"),
            (["diffract"], DiffractConfig(tests="src/pkg/tests"), "src/pkg/tests"),
            (["diffract", "--tests", "cli-tests"], DiffractConfig(tests="config-tests"), "cli-tests"),
        ],
        ids=["default", "config", "flag-overrides-config"],
    )
    def test_tests_path_from_flag_config_or_default(
        self,
        empty_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
        argv: list[str],
        config: DiffractConfig,
        expected: str,
    ) -> None:
        """main() must use --tests first, then the configuration file, then 'tests'."""
        monkeypatch.setattr(sys, "argv", argv)
        mocker.patch("sheridan.diffract._cli.load_config", return_value=config)
        mock_check = mocker.patch(
            "sheridan.diffract._cli.check", return_value=_make_result(CommitType.other, empty_diff)
        )
        with pytest.raises(SystemExit):
            main()
        assert mock_check.call_args.kwargs["tests_path"] == expected

    def test_tests_path_goes_to_check_staged(
        self,
        tmp_path: Path,
        empty_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("test: add a test\n", encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["diffract", "--tests", "qa", "--validate-msg-file", str(msg_file)])
        mocker.patch("sheridan.diffract._cli.load_config", return_value=DiffractConfig())
        mock_check = mocker.patch(
            "sheridan.diffract._cli.check_staged", return_value=_make_result(CommitType.test, empty_diff)
        )
        with pytest.raises(SystemExit):
            main()
        assert mock_check.call_args.kwargs["tests_path"] == "qa"

    def test_check_gets_the_current_directory_and_the_flags(
        self,
        tmp_path: Path,
        empty_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """check() must get the current directory as repo_path, and the --src and --tests values."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["diffract", "--src", "lib", "--tests", "qa"])
        mocker.patch("sheridan.diffract._cli.get_repo", side_effect=GitError("no repo"))
        mock_check = mocker.patch(
            "sheridan.diffract._cli.check", return_value=_make_result(CommitType.other, empty_diff)
        )
        with pytest.raises(SystemExit):
            main()
        mock_check.assert_called_once_with(
            base_ref="HEAD~1", head_ref="HEAD", repo_path=Path.cwd(), src_path="lib", tests_path="qa"
        )

    def test_check_staged_gets_the_current_directory_and_the_flags(
        self,
        tmp_path: Path,
        empty_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """check_staged() must get the current directory as repo_path, and the --src and --tests values."""
        monkeypatch.chdir(tmp_path)
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("docs: x\n", encoding="utf-8")
        argv = ["diffract", "--src", "lib", "--tests", "qa", "--validate-msg-file", str(msg_file)]
        monkeypatch.setattr(sys, "argv", argv)
        mocker.patch("sheridan.diffract._cli.get_repo", side_effect=GitError("no repo"))
        mock_check = mocker.patch(
            "sheridan.diffract._cli.check_staged", return_value=_make_result(CommitType.other, empty_diff)
        )
        with pytest.raises(SystemExit):
            main()
        mock_check.assert_called_once_with(repo_path=Path.cwd(), src_path="lib", tests_path="qa")


class TestParseWrittenType:
    """Unit tests for _parse_written_type()."""

    @pytest.mark.parametrize(
        ("message", "expected"),
        [
            ("feat: add thing", _WrittenType("feat", None, breaking=False)),
            ("feat!: remove thing", _WrittenType("feat", None, breaking=True)),
            ("feat(api)!: remove thing", _WrittenType("feat", "api", breaking=True)),
            ("feat(api): add thing", _WrittenType("feat", "api", breaking=False)),
            ("feat(my-scope): add thing", _WrittenType("feat", "my-scope", breaking=False)),
            ("fix: correct bug", _WrittenType("fix", None, breaking=False)),
            ("fix(parser): correct bug", _WrittenType("fix", "parser", breaking=False)),
            ("fix!: correct bug", _WrittenType("fix", None, breaking=True)),
            ("refactor: restructure", _WrittenType("refactor", None, breaking=False)),
            ("perf: faster", _WrittenType("perf", None, breaking=False)),
            ("style: format", _WrittenType("style", None, breaking=False)),
            ("test(cli): add a test", _WrittenType("test", "cli", breaking=False)),
            ("docs: update readme", _WrittenType("docs", None, breaking=False)),
            ("ci!: drop a job", _WrittenType("ci", None, breaking=True)),
            ("chore: bump deps", _WrittenType("chore", None, breaking=False)),
            ("build(deps): bump", _WrittenType("build", "deps", breaking=False)),
            ("revert: undo x", _WrittenType("revert", None, breaking=False)),
            ("fix: x\n\nBREAKING CHANGE: y", _WrittenType("fix", None, breaking=True)),
            ("chore: x\n\nBREAKING-CHANGE: y", _WrittenType("chore", None, breaking=True)),
            ("fix: x\nBREAKING CHANGE: y", _WrittenType("fix", None, breaking=True)),
            ("fix: BREAKING CHANGE: y", _WrittenType("fix", None, breaking=False)),
            ("fix: x\n\nNot a BREAKING CHANGE: y", _WrittenType("fix", None, breaking=False)),
            ("wip: something", None),
            ("Feat: add thing", None),
            ("", None),
            ("just a message", None),
            ("   ", None),
        ],
    )
    def test_parse(self, message: str, expected: _WrittenType | None) -> None:
        assert _parse_written_type(message) == expected


class TestRemoveComments:
    """Unit tests for _remove_comments()."""

    @pytest.mark.parametrize(
        ("message", "prefixes", "expected"),
        [
            ("chore: x", ("#",), "chore: x"),
            ("# type(scope): subject\nchore: x", ("#",), "chore: x"),
            ("\n\n  \nchore: x\n\nbody", ("#",), "chore: x\n\nbody"),
            ("# a\n\n# b\nchore: x\n# c\nbody", ("#",), "chore: x\nbody"),
            ("; a\n# b\nchore: x", (";",), "# b\nchore: x"),
            ("; a\n# b\nchore: x", ("#", ";"), "chore: x"),
            ("// a\n/ b", ("//",), "/ b"),
            ("# only a comment\n", ("#",), ""),
        ],
    )
    def test_remove(self, message: str, prefixes: tuple[str, ...], expected: str) -> None:
        assert _remove_comments(message, prefixes) == expected

    def test_breaking_footer_in_a_comment_line_is_not_breaking(self) -> None:
        message = _remove_comments("# BREAKING CHANGE: y\nfix: x\n\n; BREAKING CHANGE: y", ("#", ";"))
        assert _parse_written_type(message) == _WrittenType("fix", None, breaking=False)


class TestIsWrittenByGit:
    """Unit tests for _is_written_by_git()."""

    @pytest.mark.parametrize(
        "message",
        [
            "Merge branch 'main' into feature",
            'Revert "feat: add thing"\n\nThis reverts commit abc.',
            "fixup! fix: correct bug",
            "squash! feat: add thing",
            "amend! chore: x",
        ],
    )
    def test_git_messages(self, message: str) -> None:
        assert _is_written_by_git(message)

    @pytest.mark.parametrize("message", ["feat: add thing", "Merged things", "tidy up", ""])
    def test_other_messages(self, message: str) -> None:
        assert not _is_written_by_git(message)


_ALL_TYPES = ("feat", "fix", "refactor", "perf", "style", "test", "docs", "ci", "chore", "build")
_NO_API_CHANGE = (CommitType.code, CommitType.test, CommitType.other)
_ALL_CONVENTIONAL_TYPES = "build, chore, ci, docs, feat, fix, perf, refactor, revert, style, test"


class TestIsAllowed:
    """Unit tests for _is_allowed(): only a change to the public API limits the type."""

    @pytest.mark.parametrize("base", _ALL_TYPES)
    def test_removal_needs_a_breaking_message(self, base: str) -> None:
        assert not _is_allowed(_WrittenType(base, None, breaking=False), CommitType.feat_breaking)
        assert _is_allowed(_WrittenType(base, None, breaking=True), CommitType.feat_breaking)

    @pytest.mark.parametrize("base", _ALL_TYPES)
    def test_addition_needs_feat_or_a_breaking_message(self, base: str) -> None:
        assert _is_allowed(_WrittenType(base, None, breaking=False), CommitType.feat) is (base == "feat")
        assert _is_allowed(_WrittenType(base, None, breaking=True), CommitType.feat)

    @pytest.mark.parametrize("commit_type", _NO_API_CHANGE)
    @pytest.mark.parametrize("base", _ALL_TYPES)
    @pytest.mark.parametrize("breaking", [False, True])
    def test_each_type_passes_with_no_api_change(self, commit_type: CommitType, base: str, breaking: bool) -> None:
        assert _is_allowed(_WrittenType(base, None, breaking=breaking), commit_type)

    @pytest.mark.parametrize("commit_type", list(CommitType))
    def test_revert_type_always_passes(self, commit_type: CommitType) -> None:
        assert _is_allowed(_WrittenType("revert", None, breaking=False), commit_type)


class TestDescribeAllowed:
    """Unit tests for _describe_allowed()."""

    @pytest.mark.parametrize(
        ("commit_type", "expected"),
        [
            (CommitType.feat_breaking, "any type with a '!' or a 'BREAKING CHANGE:' footer"),
            (CommitType.feat, "feat, or any type with a '!' or a 'BREAKING CHANGE:' footer"),
            (CommitType.code, f"any Conventional Commit type ({_ALL_CONVENTIONAL_TYPES})"),
            (CommitType.test, f"any Conventional Commit type ({_ALL_CONVENTIONAL_TYPES})"),
            (CommitType.other, f"any Conventional Commit type ({_ALL_CONVENTIONAL_TYPES})"),
        ],
    )
    def test_describe(self, commit_type: CommitType, expected: str) -> None:
        assert _describe_allowed(commit_type) == expected


class TestIsFeatWithoutApiChange:
    """Unit tests for _is_feat_without_api_change()."""

    @pytest.mark.parametrize("commit_type", _NO_API_CHANGE)
    def test_feat_with_no_api_change(self, commit_type: CommitType) -> None:
        assert _is_feat_without_api_change(_WrittenType("feat", None, breaking=False), commit_type)

    @pytest.mark.parametrize("commit_type", [CommitType.feat_breaking, CommitType.feat])
    def test_feat_with_an_api_change(self, commit_type: CommitType) -> None:
        assert not _is_feat_without_api_change(_WrittenType("feat", None, breaking=False), commit_type)

    @pytest.mark.parametrize("commit_type", _NO_API_CHANGE)
    def test_breaking_feat(self, commit_type: CommitType) -> None:
        assert not _is_feat_without_api_change(_WrittenType("feat", None, breaking=True), commit_type)

    @pytest.mark.parametrize("base", [t for t in _ALL_TYPES if t != "feat"])
    def test_other_types(self, base: str) -> None:
        assert not _is_feat_without_api_change(_WrittenType(base, None, breaking=False), CommitType.code)


class TestValidateMsgFile:
    """Integration tests for --validate-msg-file through main()."""

    def test_match_feat_exits_zero(
        self,
        tmp_path: Path,
        addition_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("feat: add thing\n", encoding="utf-8")
        result = _make_result(CommitType.feat, addition_diff)
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_match_feat_breaking_exits_zero(
        self,
        tmp_path: Path,
        removal_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("feat!: remove thing\n", encoding="utf-8")
        result = _make_result(CommitType.feat_breaking, removal_diff)
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_match_fix_exits_zero(
        self,
        tmp_path: Path,
        empty_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("fix: correct bug\n", encoding="utf-8")
        result = _make_result(CommitType.code, empty_diff)
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_refactor_with_code_change_exits_zero(
        self,
        tmp_path: Path,
        empty_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("refactor: restructure\n", encoding="utf-8")
        result = _make_result(CommitType.code, empty_diff)
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_mismatch_exits_one(
        self,
        tmp_path: Path,
        addition_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("fix: tiny change\n", encoding="utf-8")
        result = _make_result(CommitType.feat, addition_diff)
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_mismatch_stderr_shows_both_types(
        self,
        tmp_path: Path,
        addition_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("fix: tiny change\n", encoding="utf-8")
        result = _make_result(CommitType.feat, addition_diff)
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "written:  fix\n" in err
        assert "possible: feat, or any type with a '!'" in err

    def test_mismatch_stderr_includes_api_diff(
        self,
        tmp_path: Path,
        addition_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("fix: thing\n", encoding="utf-8")
        result = _make_result(CommitType.feat, addition_diff)
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit):
            main()
        err = capsys.readouterr().err
        assert "NewClass" in err

    def test_mismatch_stderr_includes_suggested_prefix(
        self,
        tmp_path: Path,
        addition_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("fix: thing\n", encoding="utf-8")
        result = _make_result(CommitType.feat, addition_diff)
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit):
            main()
        err = capsys.readouterr().err
        assert "Suggested commit prefix" in err

    def test_unrecognised_type_exits_zero(
        self,
        tmp_path: Path,
        empty_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("docs: update readme\n", encoding="utf-8")
        result = _make_result(CommitType.other, empty_diff)
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_chore_exits_zero(
        self,
        tmp_path: Path,
        empty_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("chore: bump deps\n", encoding="utf-8")
        result = _make_result(CommitType.other, empty_diff)
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_empty_file_exits_one(
        self,
        tmp_path: Path,
        empty_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("", encoding="utf-8")
        result = _make_result(CommitType.other, empty_diff)
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_whitespace_only_file_exits_one(
        self,
        tmp_path: Path,
        empty_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("\n\n  \n", encoding="utf-8")
        result = _make_result(CommitType.other, empty_diff)
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_multiline_only_first_line_used(
        self,
        tmp_path: Path,
        addition_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("feat: add\n\nThis is the body", encoding="utf-8")
        result = _make_result(CommitType.feat, addition_diff)
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_scope_bang_matches_feat_breaking(
        self,
        tmp_path: Path,
        removal_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("feat(api)!: remove Bar\n", encoding="utf-8")
        result = _make_result(CommitType.feat_breaking, removal_diff)
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    @pytest.mark.parametrize(
        ("message", "commit_type", "diff_fixture"),
        [
            pytest.param("fix: correct off-by-one\n", CommitType.code, "empty_diff", id="fix-body-change"),
            pytest.param("feat: new behavior\n", CommitType.code, "empty_diff", id="feat-no-new-name"),
            pytest.param("feat!: new behavior\n", CommitType.code, "empty_diff", id="feat-bang-no-removal"),
            pytest.param("fix!: remove Bar\n", CommitType.feat_breaking, "removal_diff", id="fix-bang-removal"),
            pytest.param("refactor!: remove Bar\n", CommitType.feat_breaking, "removal_diff", id="refactor-bang"),
            pytest.param(
                "fix: remove Bar\n\nBREAKING CHANGE: Bar is gone.\n",
                CommitType.feat_breaking,
                "removal_diff",
                id="breaking-footer",
            ),
            pytest.param("fix!: add NewClass\n", CommitType.feat, "addition_diff", id="fix-bang-addition"),
        ],
    )
    def test_message_that_tells_enough_exits_zero(
        self,
        message: str,
        commit_type: CommitType,
        diff_fixture: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        request: pytest.FixtureRequest,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """A message that tells the same as or more than the API change passes."""
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text(message, encoding="utf-8")
        result = _make_result(commit_type, request.getfixturevalue(diff_fixture))
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    @pytest.mark.parametrize(
        ("message", "commit_type", "diff_fixture"),
        [
            pytest.param("feat: remove Bar\n", CommitType.feat_breaking, "removal_diff", id="feat-removal"),
            pytest.param("refactor: remove Bar\n", CommitType.feat_breaking, "removal_diff", id="refactor-removal"),
            pytest.param("refactor: add NewClass\n", CommitType.feat, "addition_diff", id="refactor-addition"),
        ],
    )
    def test_message_that_tells_less_exits_one(
        self,
        message: str,
        commit_type: CommitType,
        diff_fixture: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        request: pytest.FixtureRequest,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """A message that hides a removed or an added public name fails."""
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text(message, encoding="utf-8")
        result = _make_result(commit_type, request.getfixturevalue(diff_fixture))
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    @pytest.mark.parametrize(
        ("message", "commit_type", "diff_fixture"),
        [
            pytest.param("chore: tidy up\n", CommitType.feat_breaking, "removal_diff", id="chore-removal"),
            pytest.param("docs: add\n", CommitType.feat, "addition_diff", id="docs-addition"),
            pytest.param("tidy up\n", CommitType.other, "empty_diff", id="no-type"),
            pytest.param("wip: tidy up\n", CommitType.other, "empty_diff", id="unknown-type"),
        ],
    )
    def test_type_not_possible_exits_one(
        self,
        message: str,
        commit_type: CommitType,
        diff_fixture: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        request: pytest.FixtureRequest,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """A message with no type, an unknown type or a type that tells less than the API change fails."""
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text(message, encoding="utf-8")
        result = _make_result(commit_type, request.getfixturevalue(diff_fixture))
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    @pytest.mark.parametrize(
        ("message", "commit_type", "diff_fixture"),
        [
            pytest.param("docs: fix a docstring\n", CommitType.code, "empty_diff", id="docs-code"),
            pytest.param("fix: correct\n", CommitType.test, "empty_diff", id="fix-test"),
            pytest.param("test: add\n", CommitType.other, "empty_diff", id="test-other"),
            pytest.param("feat: add\n", CommitType.other, "empty_diff", id="feat-other"),
            pytest.param("chore!: drop\n", CommitType.other, "empty_diff", id="chore-bang-other"),
            pytest.param("perf: faster\n", CommitType.code, "empty_diff", id="perf-code"),
            pytest.param("style: format\n", CommitType.code, "empty_diff", id="style-code"),
            pytest.param("test: add\n", CommitType.test, "empty_diff", id="test-test"),
            pytest.param("ci: add a job\n", CommitType.other, "empty_diff", id="ci-other"),
            pytest.param("build: bump\n", CommitType.other, "empty_diff", id="build-other"),
            pytest.param("chore!: drop\n", CommitType.feat_breaking, "removal_diff", id="chore-bang-removal"),
            pytest.param("revert: undo\n", CommitType.code, "empty_diff", id="revert-type"),
        ],
    )
    def test_possible_type_exits_zero(
        self,
        message: str,
        commit_type: CommitType,
        diff_fixture: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        request: pytest.FixtureRequest,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """A message with a type that tells enough about the API change passes."""
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text(message, encoding="utf-8")
        result = _make_result(commit_type, request.getfixturevalue(diff_fixture))
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    @pytest.mark.parametrize(
        "message",
        [
            "Merge branch 'main' into feature\n",
            'Revert "feat: add thing"\n\nThis reverts commit abc.\n',
            "fixup! fix: correct bug\n",
            "squash! feat: add thing\n",
            "amend! chore: x\n",
        ],
    )
    def test_git_message_exits_zero(
        self,
        message: str,
        tmp_path: Path,
        removal_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """diffract does not check the messages that git writes."""
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text(message, encoding="utf-8")
        result = _make_result(CommitType.feat_breaking, removal_diff)
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_no_type_stderr_shows_written_and_possible_types(
        self,
        tmp_path: Path,
        empty_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("tidy up\n", encoding="utf-8")
        result = _make_result(CommitType.code, empty_diff)
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit):
            main()
        err = capsys.readouterr().err
        assert "written:  (no known type)\n" in err
        assert f"possible: any Conventional Commit type ({_ALL_CONVENTIONAL_TYPES})" in err

    @pytest.mark.parametrize(
        ("message", "commit_type", "diff_fixture", "warns"),
        [
            pytest.param("feat: new behavior\n", CommitType.code, "empty_diff", True, id="feat-code"),
            pytest.param("feat: new behavior\n", CommitType.other, "empty_diff", True, id="feat-other"),
            pytest.param("feat!: new behavior\n", CommitType.code, "empty_diff", False, id="feat-bang-code"),
            pytest.param("feat: add NewClass\n", CommitType.feat, "addition_diff", False, id="feat-addition"),
            pytest.param("docs: fix a docstring\n", CommitType.code, "empty_diff", False, id="docs-code"),
        ],
    )
    def test_feat_with_no_api_change_warns_and_passes(
        self,
        message: str,
        commit_type: CommitType,
        diff_fixture: str,
        warns: bool,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        request: pytest.FixtureRequest,
        capsys: pytest.CaptureFixture[str],
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """feat with no API change writes a warning to stderr, but the commit continues."""
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text(message, encoding="utf-8")
        result = _make_result(commit_type, request.getfixturevalue(diff_fixture))
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        err = capsys.readouterr().err
        expected = (
            "diffract: warning: the type is feat, but no public name changed. "
            "Make sure that the commit adds a feature.\n"
        )
        assert err == (expected if warns else "")

    def test_missing_file_exits_three(
        self,
        tmp_path: Path,
        empty_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        missing = tmp_path / "no_such_file.txt"
        result = _make_result(CommitType.other, empty_diff)
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(missing)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 3
        assert "cannot read" in capsys.readouterr().err


class TestFormatCommitType:
    """Unit tests for _format_commit_type()."""

    @pytest.mark.parametrize(
        ("commit_type", "scope", "expected"),
        [
            (CommitType.feat, None, "feat:"),
            (CommitType.feat_breaking, None, "feat!:"),
            (CommitType.feat, "api", "feat(api):"),
            (CommitType.feat_breaking, "api", "feat(api)!:"),
        ],
    )
    def test_format_commit_type(self, commit_type: CommitType, scope: str | None, expected: str) -> None:
        assert _format_commit_type(commit_type, scope) == expected


class TestScopedValidateMsgFile:
    """Tests that the output keeps the scope in the written and the suggested commit type."""

    def test_mismatch_with_scope_shows_scope_in_written_and_suggested(
        self,
        tmp_path: Path,
        addition_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """For fix(parser): and a feat result, stderr must show fix(parser) and feat(parser):."""
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("fix(parser): correct something\n", encoding="utf-8")
        result = _make_result(CommitType.feat, addition_diff)
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "written:  fix(parser)\n" in err
        assert "feat(parser):" in err

    def test_mismatch_with_scope_suggested_prefix_contains_scope(
        self,
        tmp_path: Path,
        addition_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """The suggested commit prefix in the _format_human output must have the scope."""
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("fix(api): nothing\n", encoding="utf-8")
        result = _make_result(CommitType.feat, addition_diff)
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "feat(api):" in err

    def test_mismatch_breaking_with_scope_shows_bang(
        self,
        tmp_path: Path,
        removal_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """For fix(core): and a feat! result, stderr must show feat(core)!: as the suggested prefix."""
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("fix(core): correct something\n", encoding="utf-8")
        result = _make_result(CommitType.feat_breaking, removal_diff)
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "written:  fix(core)\n" in err
        assert "feat(core)!:" in err

    def test_scope_ignored_for_type_classification(
        self,
        tmp_path: Path,
        addition_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """The scope has no effect on the type: feat(any-scope): is a feat type."""
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("feat(completely-irrelevant-scope): add\n", encoding="utf-8")
        result = _make_result(CommitType.feat, addition_diff)
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_match_with_scope_exits_zero(
        self,
        tmp_path: Path,
        empty_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """fix(scope): for a code result must exit 0."""
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("fix(scope): patch something\n", encoding="utf-8")
        result = _make_result(CommitType.code, empty_diff)
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0


class TestValidateMsgFileRouting:
    """Tests that main() calls check_staged or check correctly with --validate-msg-file."""

    def test_validate_msg_file_without_refs_calls_check_staged(
        self,
        tmp_path: Path,
        addition_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("feat: add thing\n", encoding="utf-8")
        result = _make_result(CommitType.feat, addition_diff)
        mock_check_staged = mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        mock_check = mocker.patch("sheridan.diffract._cli.check", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit):
            main()
        mock_check_staged.assert_called_once()
        mock_check.assert_not_called()

    def test_validate_msg_file_with_explicit_refs_calls_check(
        self,
        tmp_path: Path,
        addition_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("feat: add thing\n", encoding="utf-8")
        result = _make_result(CommitType.feat, addition_diff, base_ref="HEAD~2", head_ref="HEAD")
        mock_check_staged = mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        mock_check = mocker.patch("sheridan.diffract._cli.check", return_value=result)
        monkeypatch.setattr(
            sys,
            "argv",
            ["diffract", "HEAD~2", "HEAD", "--validate-msg-file", str(msg_file)],
        )
        with pytest.raises(SystemExit):
            main()
        mock_check.assert_called_once()
        mock_check_staged.assert_not_called()

    def test_validate_msg_file_with_explicit_refs_passes_refs_to_check(
        self,
        tmp_path: Path,
        addition_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("feat: add thing\n", encoding="utf-8")
        result = _make_result(CommitType.feat, addition_diff, base_ref="HEAD~2", head_ref="HEAD")
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        mock_check = mocker.patch("sheridan.diffract._cli.check", return_value=result)
        monkeypatch.setattr(
            sys,
            "argv",
            ["diffract", "HEAD~2", "HEAD", "--validate-msg-file", str(msg_file)],
        )
        with pytest.raises(SystemExit):
            main()
        kwargs = mock_check.call_args.kwargs
        assert kwargs["base_ref"] == "HEAD~2"
        assert kwargs["head_ref"] == "HEAD"

    def test_no_validate_msg_file_calls_check_with_default_refs(
        self,
        empty_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        result = _make_result(CommitType.other, empty_diff)
        mock_check_staged = mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        mock_check = mocker.patch("sheridan.diffract._cli.check", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract"])
        with pytest.raises(SystemExit):
            main()
        mock_check.assert_called_once()
        mock_check_staged.assert_not_called()
        kwargs = mock_check.call_args.kwargs
        assert kwargs["base_ref"] == "HEAD~1"
        assert kwargs["head_ref"] == "HEAD"

    def test_no_validate_msg_file_with_custom_refs(
        self,
        empty_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        result = _make_result(CommitType.other, empty_diff, base_ref="v1.0", head_ref="v2.0")
        mock_check = mocker.patch("sheridan.diffract._cli.check", return_value=result)
        mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "v1.0", "v2.0"])
        with pytest.raises(SystemExit):
            main()
        mock_check.assert_called_once()
        kwargs = mock_check.call_args.kwargs
        assert kwargs["base_ref"] == "v1.0"
        assert kwargs["head_ref"] == "v2.0"

    def test_validate_msg_file_only_base_ref_given_calls_check(
        self,
        tmp_path: Path,
        empty_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("fix: patch\n", encoding="utf-8")
        result = _make_result(CommitType.other, empty_diff)
        mock_check_staged = mocker.patch("sheridan.diffract._cli.check_staged", return_value=result)
        mock_check = mocker.patch("sheridan.diffract._cli.check", return_value=result)
        # base_ref is set and head_ref is None. Thus diffract does not compare with the staging area.
        monkeypatch.setattr(
            sys,
            "argv",
            ["diffract", "HEAD~3", "--validate-msg-file", str(msg_file)],
        )
        with pytest.raises(SystemExit):
            main()
        mock_check.assert_called_once()
        mock_check_staged.assert_not_called()
