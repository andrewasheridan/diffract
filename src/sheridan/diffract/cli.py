"""Command-line interface for sheridan-diffract."""

__all__ = ["main"]

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn, override

from sheridan.diffract import __version__
from sheridan.diffract.checker import check, check_staged
from sheridan.diffract.config import load_config
from sheridan.diffract.enums import CommitType
from sheridan.diffract.exceptions import DiffractError
from sheridan.diffract.git_utils import get_repo
from sheridan.diffract.models import ApiDiff, DiffractResult, NameChange

_COMMIT_TYPE_RE: re.Pattern[str] = re.compile(r"^(feat|fix|refactor)(\([^)]*\))?(!)?:")
_BREAKING_FOOTER_RE: re.Pattern[str] = re.compile(r"^BREAKING[ -]CHANGE: ", re.MULTILINE)
_ISSUES_URL = "https://github.com/andrewasheridan/diffract/issues"
_ERROR_EXIT_CODE = 3


@dataclass(frozen=True)
class _WrittenType:
    """The commit type that a commit message gives.

    Attributes:
        prefix: The prefix as written, for example ``"fix(parser)!:"``.
        base: The type without scope and ``!``: ``"feat"``, ``"fix"`` or ``"refactor"``.
        breaking: True if the header has a ``!`` or the body has a ``BREAKING CHANGE:`` footer.
    """

    prefix: str
    base: str
    breaking: bool


class _ArgumentParser(argparse.ArgumentParser):
    """An argument parser that exits 3 for a usage error.

    The default parser exits 2. With ``--exit-code``, 2 means an API change, so a CI job
    cannot tell a usage error from an API change.
    """

    @override
    def error(self, message: str) -> NoReturn:
        """Print the usage and the error message to stderr, then exit 3.

        Args:
            message: The usage error.
        """
        self.print_usage(sys.stderr)
        self.exit(_ERROR_EXIT_CODE, f"{self.prog}: error: {message}\n")


def _build_parser() -> argparse.ArgumentParser:
    """Construct and return the argument parser for the diffract CLI.

    Returns:
        A fully-configured :class:`argparse.ArgumentParser` instance.
    """
    parser = _ArgumentParser(
        prog="diffract",
        description="Detect public API changes between git refs and suggest a commit type.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "base_ref",
        nargs="?",
        default=None,
        metavar="BASE_REF",
        help=(
            "The earlier git ref to compare (default: HEAD~1). "
            "When --validate-msg-file is used without explicit refs, "
            "diffract automatically compares HEAD vs the staging area."
        ),
    )
    parser.add_argument(
        "head_ref",
        nargs="?",
        default=None,
        metavar="HEAD_REF",
        help=(
            "The later git ref to compare (default: HEAD). "
            "If only BASE_REF is given, HEAD is used as HEAD_REF. "
            "When --validate-msg-file is used without explicit refs, "
            "diffract automatically compares HEAD vs the staging area."
        ),
    )
    parser.add_argument(
        "--src",
        default=None,
        metavar="SRC",
        dest="src_path",
        help="Source directory within the repository to scan (default: src).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Emit JSON to stdout instead of human-readable text.",
    )
    parser.add_argument(
        "--exit-code",
        action="store_true",
        dest="exit_code",
        help="Exit 1 for breaking changes, 2 for any API change, 0 otherwise.",
    )
    parser.add_argument(
        "--validate-msg-file",
        dest="validate_msg_file",
        metavar="MSGFILE",
        help=(
            "Path to a commit message file. The check fails only if the message tells less "
            "than the API change: removed public names need a '!' or a 'BREAKING CHANGE:' "
            "footer, and added public names need 'feat' or a '!'. "
            "Types other than feat, fix and refactor are not checked."
        ),
    )

    return parser


def _group_changes(changes: tuple[NameChange, ...]) -> dict[str, list[str]]:
    """Group NameChange objects by module for display purposes.

    Args:
        changes: The name changes to group.

    Returns:
        A dict mapping module name to sorted list of public names.
    """
    grouped: dict[str, list[str]] = defaultdict(list)
    for change in changes:
        grouped[change.module].append(change.name)
    return {mod: sorted(names) for mod, names in sorted(grouped.items())}


def _format_human(result: DiffractResult, scope: str | None = None) -> str:
    """Format a DiffractResult as human-readable text.

    Args:
        result: The diffract result to format.
        scope: Optional conventional-commit scope (without parentheses) to
            include in the suggested commit prefix, e.g. ``"api"`` produces
            ``"feat(api):"`` instead of ``"feat:"``.

    Returns:
        A multi-line string suitable for printing to a terminal.
    """
    lines: list[str] = []
    commit_label = str(result.commit_type)
    is_breaking = result.commit_type == CommitType.feat_breaking

    if is_breaking:
        lines.append(f"Detected: {commit_label}  (breaking change)")
    else:
        lines.append(f"Detected: {commit_label}")

    lines.append("")

    if result.diff.is_empty:
        lines.append("No public API changes detected.")
    else:
        if result.diff.removed:
            lines.append("Removed public names:")
            for module, names in _group_changes(result.diff.removed).items():
                lines.append(f"  {module}:")
                for name in names:
                    lines.append(f"    - {name}")
        if result.diff.added:
            lines.append("Added public names:")
            for module, names in _group_changes(result.diff.added).items():
                lines.append(f"  {module}:")
                for name in names:
                    lines.append(f"    + {name}")

    lines.append("")
    lines.append(f"Suggested commit prefix: {_format_commit_type(result.commit_type, scope)}")

    return "\n".join(lines)


def _resolve_exit_code(result: DiffractResult, use_exit_code: bool) -> int:
    """Determine the process exit code based on the result and flag.

    Args:
        result: The diffract result.
        use_exit_code: Whether the ``--exit-code`` flag was passed.

    Returns:
        ``0`` normally; ``1`` for breaking changes, ``2`` for any API change,
        when ``use_exit_code`` is ``True``.
    """
    if not use_exit_code:
        return 0
    if result.diff.is_breaking:
        return 1
    if not result.diff.is_empty:
        return 2
    return 0


def _parse_written_type(message: str) -> _WrittenType | None:
    """Parse the conventional commit type from a commit message.

    Only ``feat``, ``fix`` and ``refactor`` (with or without a scope and a ``!``) are
    recognised. Other types, for example ``docs:`` or ``chore:``, give ``None`` so that
    diffract never blocks them.

    Args:
        message: The full commit message. The type is in the first line. A
            ``BREAKING CHANGE:`` or ``BREAKING-CHANGE:`` footer can be in the lines after it.

    Returns:
        The written type, or ``None`` if the first line has no recognised type.
    """
    lines = message.splitlines()
    first_line = lines[0] if lines else ""
    m = _COMMIT_TYPE_RE.match(first_line)
    if m is None:
        return None

    body = "\n".join(lines[1:])
    breaking = m.group(3) is not None or _BREAKING_FOOTER_RE.search(body) is not None

    return _WrittenType(prefix=m.group(0), base=m.group(1), breaking=breaking)


def _tells_less_than(written: _WrittenType, diff: ApiDiff) -> bool:
    """Find if a written commit type tells less than the API change.

    The detected type is only an estimate from the public names. Thus a message can
    give more than the detected type, for example ``fix:`` for a change to a function
    body, or ``feat!:`` for a change in behavior. A message fails only when it hides a
    change to the public names:

    - Removed public names, and the message is not breaking.
    - Added public names, and the type is not ``feat`` and the message is not breaking.

    Args:
        written: The commit type from the message.
        diff: The API diff for the commit.

    Returns:
        True if the message tells less than the API change.
    """
    if written.breaking:
        return False
    if diff.is_breaking:
        return True
    return diff.has_additions and written.base != "feat"


def _extract_scope(first_line: str) -> str | None:
    """Extract the optional scope from the first line of a commit message.

    Args:
        first_line: The first line of the commit message.

    Returns:
        The scope string without parentheses (e.g. ``"parser"`` from
        ``"feat(parser): …"``), or ``None`` if no scope is present or
        the line is not a recognised conventional-commit prefix.
    """
    m = _COMMIT_TYPE_RE.match(first_line)
    if m is None:
        return None
    raw = m.group(2)  # e.g. "(parser)" or None
    return raw[1:-1] if raw is not None else None


def _format_commit_type(commit_type: CommitType, scope: str | None) -> str:
    """Render a commit type with an optional scope as a conventional-commit prefix.

    Args:
        commit_type: The commit type to render.
        scope: An optional scope string (without parentheses).

    Returns:
        A string such as ``"feat:"``, ``"feat(api):"`` or ``"feat(api)!:"``.
    """
    if scope is None:
        return f"{commit_type}:"
    if commit_type == CommitType.feat_breaking:
        return f"feat({scope})!:"
    return f"{commit_type}({scope}):"


def main() -> None:
    """CLI entrypoint for diffract.

    Loads configuration from config files (if present), parses command-line arguments,
    and invokes the check() or check_staged() function to detect API changes. Outputs
    results as human-readable text or JSON, and optionally validates commit message types.

    When ``--validate-msg-file`` is provided without explicit BASE_REF/HEAD_REF positional
    arguments, diffract automatically compares ``HEAD`` against the current staging area
    via :func:`~sheridan.diffract.checker.check_staged`.

    An unexpected exception does not show a traceback. diffract writes a short message
    with a link to the issue tracker to stderr.

    Exits with code:
      - 0: No changes detected (or --exit-code not set)
      - 1: Breaking changes detected (with --exit-code), or commit message mismatch
      - 2: Non-breaking API changes detected (with --exit-code)
      - 3: Error: a usage error, a git, file or config error, or an unexpected exception
    """
    try:
        _run()
    except Exception as exc:  # Every unexpected error must exit 3, not 1.
        print(
            f"diffract: unexpected error: {type(exc).__name__}: {exc}\n"
            f"This is a bug in diffract. Please report it at {_ISSUES_URL}",
            file=sys.stderr,
        )
        sys.exit(_ERROR_EXIT_CODE)


def _run() -> None:
    """Parse the arguments, run the check and exit with the applicable code."""
    parser = _build_parser()
    args = parser.parse_args()

    repo_path = Path.cwd()
    # Resolve the actual git repo root so load_config finds config files
    # correctly even when diffract is invoked from a subdirectory.
    try:
        repo_root = Path(get_repo(repo_path).working_dir)
    except DiffractError:
        repo_root = repo_path  # no repo found; check() will raise the proper error

    try:
        config = load_config(repo_root)
        # Priority: --src flag > config file > built-in default
        src_path: str = args.src_path or config.src or "src"

        if args.validate_msg_file is not None and not args.base_ref and not args.head_ref:
            result = check_staged(repo_path=repo_path, src_path=src_path)
        else:
            result = check(
                base_ref=args.base_ref or "HEAD~1",
                head_ref=args.head_ref or "HEAD",
                repo_path=repo_path,
                src_path=src_path,
            )
    except DiffractError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(_ERROR_EXIT_CODE)

    if args.validate_msg_file is not None:
        msg_path = Path(args.validate_msg_file)
        try:
            raw = msg_path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"diffract: cannot read commit message file: {exc}", file=sys.stderr)
            sys.exit(_ERROR_EXIT_CODE)

        _lines = raw.splitlines()
        first_line = _lines[0] if _lines else ""
        written = _parse_written_type(raw)
        scope = _extract_scope(first_line)

        if written is None or not _tells_less_than(written, result.diff):
            sys.exit(0)

        print(_format_human(result, scope=scope), file=sys.stderr)
        print(
            f"\ndiffract: commit type mismatch"
            f"\n  written:  {written.prefix}"
            f"\n  detected: {_format_commit_type(result.commit_type, scope)}",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.output_json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(_format_human(result))

    sys.exit(_resolve_exit_code(result, args.exit_code))
