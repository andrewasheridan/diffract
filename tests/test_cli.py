"""Tests for sheridan.diffract.cli."""

from __future__ import annotations

import json
import sys

import pytest

from sheridan.diffract.cli import _format_human, _resolve_exit_code, main
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
