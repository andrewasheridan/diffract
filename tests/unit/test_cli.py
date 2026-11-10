"""Tests for sheridan.diffract.cli."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from sheridan.diffract.cli import (
    _extract_scope,
    _format_commit_type,
    _format_human,
    _parse_commit_type,
    _resolve_exit_code,
    main,
)
from sheridan.diffract.config import DiffractConfig
from sheridan.diffract.enums import CommitType
from sheridan.diffract.exceptions import GitError
from sheridan.diffract.models import ApiDiff, DiffractResult


def _make_result(
    commit_type: CommitType,
    diff: ApiDiff,
    summary: str = "summary",
    base_ref: str = "HEAD~1",
    head_ref: str = "HEAD",
) -> DiffractResult:
    """Construct a DiffractResult for use in tests."""
    return DiffractResult(
        commit_type=commit_type,
        summary=summary,
        diff=diff,
        base_ref=base_ref,
        head_ref=head_ref,
    )


class TestFormatHuman:
    """Tests for _format_human()."""

    def test_no_changes_output(self) -> None:
        """Output for a fix result must state no public API changes."""
        result = _make_result(CommitType.fix, ApiDiff(added=(), removed=()))
        output = _format_human(result)
        assert "No public API changes detected." in output
        assert "fix:" in output

    def test_breaking_change_output(self, removal_diff: ApiDiff) -> None:
        """Output for a feat! result must state it is a breaking change."""
        result = _make_result(CommitType.feat_breaking, removal_diff)
        output = _format_human(result)
        assert "breaking change" in output
        assert "feat!:" in output

    def test_addition_output_lists_names(self, addition_diff: ApiDiff) -> None:
        """Output for a feat result must list the added public names."""
        result = _make_result(CommitType.feat, addition_diff)
        output = _format_human(result)
        assert "Added public names" in output
        assert "NewClass" in output

    def test_removal_output_lists_names(self, removal_diff: ApiDiff) -> None:
        """Output for a feat! result must list the removed public names."""
        result = _make_result(CommitType.feat_breaking, removal_diff)
        output = _format_human(result)
        assert "Removed public names" in output
        assert "OldClass" in output

    def test_refactor_output(self, empty_diff: ApiDiff) -> None:
        """Output for a refactor result must state no API changes."""
        result = _make_result(CommitType.refactor, empty_diff)
        output = _format_human(result)
        assert "refactor:" in output


class TestResolveExitCode:
    """Tests for _resolve_exit_code()."""

    def test_always_zero_without_flag(self, removal_diff: ApiDiff) -> None:
        """Without --exit-code, exit code must always be 0 regardless of result."""
        result = _make_result(CommitType.feat_breaking, removal_diff)
        assert _resolve_exit_code(result, use_exit_code=False) == 0

    def test_one_for_breaking_with_flag(self, removal_diff: ApiDiff) -> None:
        """With --exit-code, breaking changes must produce exit code 1."""
        result = _make_result(CommitType.feat_breaking, removal_diff)
        assert _resolve_exit_code(result, use_exit_code=True) == 1

    def test_two_for_non_breaking_api_change_with_flag(self, addition_diff: ApiDiff) -> None:
        """With --exit-code, non-breaking API changes must produce exit code 2."""
        result = _make_result(CommitType.feat, addition_diff)
        assert _resolve_exit_code(result, use_exit_code=True) == 2

    def test_zero_for_no_changes_with_flag(self, empty_diff: ApiDiff) -> None:
        """With --exit-code, no changes must produce exit code 0."""
        result = _make_result(CommitType.fix, empty_diff)
        assert _resolve_exit_code(result, use_exit_code=True) == 0


class TestMain:
    """Integration tests for the main() CLI entrypoint."""

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
        """'diffract' must print human-readable output and exit 0 by default."""
        result = _make_result(CommitType.fix, empty_diff)
        monkeypatch.setattr(sys, "argv", ["diffract"])
        mocker.patch("sheridan.diffract.cli.check", return_value=result)
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        assert "fix" in capsys.readouterr().out

    def test_json_output(
        self,
        empty_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """'diffract --json' must emit valid JSON to stdout."""
        result = _make_result(CommitType.fix, empty_diff)
        monkeypatch.setattr(sys, "argv", ["diffract", "--json"])
        mocker.patch("sheridan.diffract.cli.check", return_value=result)
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        parsed = json.loads(capsys.readouterr().out)
        assert parsed["commit_type"] == "fix"

    def test_diffract_error_exits_three(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """'diffract' must print to stderr and exit 3 on DiffractError."""
        monkeypatch.setattr(sys, "argv", ["diffract"])
        mocker.patch("sheridan.diffract.cli.check", side_effect=GitError("no repo found"))
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 3
        assert "no repo found" in capsys.readouterr().err

    def test_exit_code_breaking(
        self,
        removal_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """'diffract --exit-code' must exit 1 for breaking changes."""
        result = _make_result(CommitType.feat_breaking, removal_diff)
        monkeypatch.setattr(sys, "argv", ["diffract", "--exit-code"])
        mocker.patch("sheridan.diffract.cli.check", return_value=result)
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
        """'diffract --exit-code' must exit 2 for non-breaking API changes."""
        result = _make_result(CommitType.feat, addition_diff)
        monkeypatch.setattr(sys, "argv", ["diffract", "--exit-code"])
        mocker.patch("sheridan.diffract.cli.check", return_value=result)
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
        """'diffract' must forward positional refs and --src to check()."""
        result = _make_result(CommitType.fix, empty_diff, base_ref="v1.0", head_ref="v2.0")
        monkeypatch.setattr(sys, "argv", ["diffract", "v1.0", "v2.0", "--src", "lib"])
        mock_check = mocker.patch("sheridan.diffract.cli.check", return_value=result)
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
        """Output for a mixed diff must show both Removed and Added sections."""
        result = _make_result(CommitType.feat_breaking, mixed_diff)
        monkeypatch.setattr(sys, "argv", ["diffract"])
        mocker.patch("sheridan.diffract.cli.check", return_value=result)
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
        """main() must use the config file's src when --src is not provided."""
        result = _make_result(CommitType.fix, empty_diff)
        monkeypatch.setattr(sys, "argv", ["diffract"])
        mocker.patch("sheridan.diffract.cli.load_config", return_value=DiffractConfig(src="python/src"))
        mock_check = mocker.patch("sheridan.diffract.cli.check", return_value=result)
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
        """main() must use --src over the config file value when both are present."""
        result = _make_result(CommitType.fix, empty_diff)
        monkeypatch.setattr(sys, "argv", ["diffract", "--src", "cli-src"])
        mocker.patch("sheridan.diffract.cli.load_config", return_value=DiffractConfig(src="config-src"))
        mock_check = mocker.patch("sheridan.diffract.cli.check", return_value=result)
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
        """main() must fall back to 'src' when neither --src nor config provides a value."""
        result = _make_result(CommitType.fix, empty_diff)
        monkeypatch.setattr(sys, "argv", ["diffract"])
        mocker.patch("sheridan.diffract.cli.load_config", return_value=DiffractConfig())
        mock_check = mocker.patch("sheridan.diffract.cli.check", return_value=result)
        with pytest.raises(SystemExit):
            main()
        kwargs = mock_check.call_args.kwargs
        assert kwargs["src_path"] == "src"


class TestParseCommitType:
    """Unit tests for _parse_commit_type()."""

    @pytest.mark.parametrize(
        ("first_line", "expected"),
        [
            ("feat: add thing", CommitType.feat),
            ("feat!: remove thing", CommitType.feat_breaking),
            ("feat(api)!: remove thing", CommitType.feat_breaking),
            ("feat(api): add thing", CommitType.feat),
            ("fix: correct bug", CommitType.fix),
            ("fix(parser): correct bug", CommitType.fix),
            ("refactor: restructure", CommitType.refactor),
            ("docs: update readme", None),
            ("chore: bump deps", None),
            ("", None),
            ("just a message", None),
            ("   ", None),
        ],
    )
    def test_parse(self, first_line: str, expected: CommitType | None) -> None:
        assert _parse_commit_type(first_line) == expected


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
        mocker.patch("sheridan.diffract.cli.check_staged", return_value=result)
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
        mocker.patch("sheridan.diffract.cli.check_staged", return_value=result)
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
        result = _make_result(CommitType.fix, empty_diff)
        mocker.patch("sheridan.diffract.cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_match_refactor_exits_zero(
        self,
        tmp_path: Path,
        empty_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("refactor: restructure\n", encoding="utf-8")
        result = _make_result(CommitType.refactor, empty_diff)
        mocker.patch("sheridan.diffract.cli.check_staged", return_value=result)
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
        mocker.patch("sheridan.diffract.cli.check_staged", return_value=result)
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
        mocker.patch("sheridan.diffract.cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "fix:" in err
        assert "feat:" in err

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
        mocker.patch("sheridan.diffract.cli.check_staged", return_value=result)
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
        mocker.patch("sheridan.diffract.cli.check_staged", return_value=result)
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
        result = _make_result(CommitType.fix, empty_diff)
        mocker.patch("sheridan.diffract.cli.check_staged", return_value=result)
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
        result = _make_result(CommitType.fix, empty_diff)
        mocker.patch("sheridan.diffract.cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_empty_file_exits_zero(
        self,
        tmp_path: Path,
        empty_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("", encoding="utf-8")
        result = _make_result(CommitType.fix, empty_diff)
        mocker.patch("sheridan.diffract.cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_whitespace_only_file_exits_zero(
        self,
        tmp_path: Path,
        empty_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("\n\n  \n", encoding="utf-8")
        result = _make_result(CommitType.fix, empty_diff)
        mocker.patch("sheridan.diffract.cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

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
        mocker.patch("sheridan.diffract.cli.check_staged", return_value=result)
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
        mocker.patch("sheridan.diffract.cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_missing_file_exits_three(
        self,
        tmp_path: Path,
        empty_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        missing = tmp_path / "no_such_file.txt"
        result = _make_result(CommitType.fix, empty_diff)
        mocker.patch("sheridan.diffract.cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(missing)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 3
        assert "cannot read" in capsys.readouterr().err


class TestExtractScope:
    """Unit tests for _extract_scope()."""

    @pytest.mark.parametrize(
        ("first_line", "expected"),
        [
            ("feat: add thing", None),
            ("feat!: remove thing", None),
            ("fix: correct bug", None),
            ("refactor: restructure", None),
            ("feat(api): add thing", "api"),
            ("feat(api)!: remove thing", "api"),
            ("fix(parser): correct bug", "parser"),
            ("refactor(core): restructure", "core"),
            ("feat(my-scope): add thing", "my-scope"),
            ("docs: update readme", None),
            ("chore: bump deps", None),
            ("", None),
            ("just a message", None),
        ],
    )
    def test_extract_scope(self, first_line: str, expected: str | None) -> None:
        assert _extract_scope(first_line) == expected


class TestFormatCommitType:
    """Unit tests for _format_commit_type()."""

    @pytest.mark.parametrize(
        ("commit_type", "scope", "expected"),
        [
            (CommitType.feat, None, "feat:"),
            (CommitType.feat_breaking, None, "feat!:"),
            (CommitType.fix, None, "fix:"),
            (CommitType.refactor, None, "refactor:"),
            (CommitType.feat, "api", "feat(api):"),
            (CommitType.feat_breaking, "api", "feat(api)!:"),
            (CommitType.fix, "parser", "fix(parser):"),
            (CommitType.refactor, "core", "refactor(core):"),
        ],
    )
    def test_format_commit_type(self, commit_type: CommitType, scope: str | None, expected: str) -> None:
        assert _format_commit_type(commit_type, scope) == expected


class TestScopedValidateMsgFile:
    """Tests that scope is preserved in written/suggested commit type output."""

    def test_mismatch_with_scope_shows_scope_in_written_and_detected(
        self,
        tmp_path: Path,
        addition_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """fix(parser): mismatch against feat should show fix(parser): and feat(parser): in stderr."""
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("fix(parser): correct something\n", encoding="utf-8")
        result = _make_result(CommitType.feat, addition_diff)
        mocker.patch("sheridan.diffract.cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "fix(parser):" in err
        assert "feat(parser):" in err

    def test_mismatch_with_scope_suggested_prefix_contains_scope(
        self,
        tmp_path: Path,
        addition_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """Suggested commit prefix in _format_human output should include scope."""
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("fix(api): nothing\n", encoding="utf-8")
        result = _make_result(CommitType.feat, addition_diff)
        mocker.patch("sheridan.diffract.cli.check_staged", return_value=result)
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
        """fix(core): mismatch against feat! should show feat(core)!: as detected."""
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("fix(core): correct something\n", encoding="utf-8")
        result = _make_result(CommitType.feat_breaking, removal_diff)
        mocker.patch("sheridan.diffract.cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "fix(core):" in err
        assert "feat(core)!:" in err

    def test_scope_ignored_for_type_classification(
        self,
        tmp_path: Path,
        addition_diff: ApiDiff,
        monkeypatch: pytest.MonkeyPatch,
        mocker: pytest.fixture,  # type: ignore[type-arg]
    ) -> None:
        """Regex must not care about scope: feat(any-scope): should still classify as feat."""
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("feat(completely-irrelevant-scope): add\n", encoding="utf-8")
        result = _make_result(CommitType.feat, addition_diff)
        mocker.patch("sheridan.diffract.cli.check_staged", return_value=result)
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
        """fix(scope): matching fix result should exit 0."""
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("fix(scope): patch something\n", encoding="utf-8")
        result = _make_result(CommitType.fix, empty_diff)
        mocker.patch("sheridan.diffract.cli.check_staged", return_value=result)
        monkeypatch.setattr(sys, "argv", ["diffract", "--validate-msg-file", str(msg_file)])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0


class TestValidateMsgFileRouting:
    """Tests for check_staged vs check routing in main() when --validate-msg-file is used."""

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
        mock_check_staged = mocker.patch("sheridan.diffract.cli.check_staged", return_value=result)
        mock_check = mocker.patch("sheridan.diffract.cli.check", return_value=result)
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
        mock_check_staged = mocker.patch("sheridan.diffract.cli.check_staged", return_value=result)
        mock_check = mocker.patch("sheridan.diffract.cli.check", return_value=result)
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
        mocker.patch("sheridan.diffract.cli.check_staged", return_value=result)
        mock_check = mocker.patch("sheridan.diffract.cli.check", return_value=result)
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
        result = _make_result(CommitType.fix, empty_diff)
        mock_check_staged = mocker.patch("sheridan.diffract.cli.check_staged", return_value=result)
        mock_check = mocker.patch("sheridan.diffract.cli.check", return_value=result)
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
        result = _make_result(CommitType.fix, empty_diff, base_ref="v1.0", head_ref="v2.0")
        mock_check = mocker.patch("sheridan.diffract.cli.check", return_value=result)
        mocker.patch("sheridan.diffract.cli.check_staged", return_value=result)
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
        result = _make_result(CommitType.fix, empty_diff)
        mock_check_staged = mocker.patch("sheridan.diffract.cli.check_staged", return_value=result)
        mock_check = mocker.patch("sheridan.diffract.cli.check", return_value=result)
        # Only one positional ref — head_ref will be None, but base_ref is set,
        # so the condition (base_ref is None AND head_ref is None) is False.
        monkeypatch.setattr(
            sys,
            "argv",
            ["diffract", "HEAD~3", "--validate-msg-file", str(msg_file)],
        )
        with pytest.raises(SystemExit):
            main()
        mock_check.assert_called_once()
        mock_check_staged.assert_not_called()
