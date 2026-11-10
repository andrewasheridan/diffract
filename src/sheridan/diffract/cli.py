"""The ``diffract`` command."""

__all__ = ["main"]

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn, override

from sheridan.diffract import __version__
from sheridan.diffract.checker import check, check_staged
from sheridan.diffract.classifier import group_by_module
from sheridan.diffract.config import load_config
from sheridan.diffract.enums import CommitType
from sheridan.diffract.exceptions import DiffractError
from sheridan.diffract.git_utils import get_repo
from sheridan.diffract.models import ApiDiff, DiffractResult

_COMMIT_TYPE_RE: re.Pattern[str] = re.compile(r"^(feat|fix|refactor)(\([^)]*\))?(!)?:")
_BREAKING_FOOTER_RE: re.Pattern[str] = re.compile(r"^BREAKING[ -]CHANGE: ", re.MULTILINE)
_ISSUES_URL = "https://github.com/andrewasheridan/diffract/issues"
_ERROR_EXIT_CODE = 3
# Only for these groups can diffract give one commit prefix.
_FEATURE_TYPES = (CommitType.feat_breaking, CommitType.feat)


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
    """Make the argument parser for the ``diffract`` command.

    Returns:
        The argument parser, with all the arguments of the command.
    """
    parser = _ArgumentParser(
        prog="diffract",
        description="Find the public API changes between two git refs and give the possible commit types.",
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
            "If you use --validate-msg-file and give no refs, "
            "diffract compares HEAD with the staging area."
        ),
    )
    parser.add_argument(
        "head_ref",
        nargs="?",
        default=None,
        metavar="HEAD_REF",
        help=(
            "The later git ref to compare (default: HEAD). "
            "If you give only BASE_REF, diffract uses HEAD as HEAD_REF. "
            "If you use --validate-msg-file and give no refs, "
            "diffract compares HEAD with the staging area."
        ),
    )
    parser.add_argument(
        "--src",
        default=None,
        metavar="SRC",
        dest="src_path",
        help="The directory in the repository that contains the Python packages (default: src).",
    )
    parser.add_argument(
        "--tests",
        default=None,
        metavar="TESTS",
        dest="tests_path",
        help="The directory in the repository that contains the tests (default: tests).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Write JSON to stdout, not text.",
    )
    parser.add_argument(
        "--exit-code",
        action="store_true",
        dest="exit_code",
        help="Exit 1 if a public name was removed, 2 if a public name was added, and 0 if no public name changed.",
    )
    parser.add_argument(
        "--validate-msg-file",
        dest="validate_msg_file",
        metavar="MSGFILE",
        help=(
            "The path of a commit message file. The check fails only if the message tells less "
            "than the API change: removed public names need a '!' or a 'BREAKING CHANGE:' "
            "footer, and added public names need 'feat' or a '!'. "
            "diffract does not check types other than feat, fix and refactor."
        ),
    )

    return parser


def _format_human(result: DiffractResult, scope: str | None = None) -> str:
    """Write a ``DiffractResult`` as text for a terminal.

    Args:
        result: The diffract result to write.
        scope: The Conventional Commit scope for the suggested commit prefix, without
            parentheses, or ``None``. For example, ``"api"`` gives ``"feat(api):"``,
            not ``"feat:"``.

    Returns:
        The text, in one or more lines.
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
        lines.append("The public API did not change.")
    else:
        if result.diff.removed:
            lines.append("Removed public names:")
            for module, names in group_by_module(result.diff.removed).items():
                lines.append(f"  {module}:")
                for name in names:
                    lines.append(f"    - {name}")
        if result.diff.added:
            lines.append("Added public names:")
            for module, names in group_by_module(result.diff.added).items():
                lines.append(f"  {module}:")
                for name in names:
                    lines.append(f"    + {name}")

    lines.append("")
    if result.commit_type in _FEATURE_TYPES:
        lines.append(f"Suggested commit prefix: {_format_commit_type(result.commit_type, scope)}")
    else:
        lines.append(f"This can be a {_join_types(result.commit_type.possible_types)} commit.")

    return "\n".join(lines)


def _join_types(types: tuple[str, ...]) -> str:
    """Write a list of commit types as text.

    Args:
        types: The commit types, for example ``("fix", "refactor", "perf")``.

    Returns:
        The types as text, for example ``"fix, refactor or perf"``.
    """
    if len(types) == 1:
        return types[0]
    return f"{', '.join(types[:-1])} or {types[-1]}"


def _resolve_exit_code(result: DiffractResult, use_exit_code: bool) -> int:
    """Find the exit code for a result.

    Args:
        result: The diffract result.
        use_exit_code: True if the command has the ``--exit-code`` flag.

    Returns:
        ``0`` if ``use_exit_code`` is ``False``. If ``use_exit_code`` is ``True``:
        ``1`` if a public name was removed, ``2`` if a public name was added, and
        ``0`` if no public name changed.
    """
    if not use_exit_code:
        return 0
    if result.diff.is_breaking:
        return 1
    if not result.diff.is_empty:
        return 2
    return 0


def _parse_written_type(message: str) -> _WrittenType | None:
    """Parse the Conventional Commit type from a commit message.

    The function knows only ``feat``, ``fix`` and ``refactor``, with or without a scope
    and a ``!``. Other types, for example ``docs:`` or ``chore:``, give ``None``. Thus
    diffract never blocks them.

    Args:
        message: The full commit message. The type is in the first line. A
            ``BREAKING CHANGE:`` or ``BREAKING-CHANGE:`` footer can be in the lines after it.

    Returns:
        The written type, or ``None`` if the first line has no known type.
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
    """Get the scope from the first line of a commit message.

    Args:
        first_line: The first line of the commit message.

    Returns:
        The scope without parentheses, for example ``"parser"`` from
        ``"feat(parser): …"``. ``None`` if the line has no scope, or if the line
        does not start with a known Conventional Commit type.
    """
    m = _COMMIT_TYPE_RE.match(first_line)
    if m is None:
        return None
    raw = m.group(2)
    return raw[1:-1] if raw is not None else None


def _format_commit_type(commit_type: CommitType, scope: str | None) -> str:
    """Write a commit type and a scope as a Conventional Commit prefix.

    Args:
        commit_type: The commit type to write.
        scope: The scope without parentheses, or ``None``.

    Returns:
        A string such as ``"feat:"``, ``"feat(api):"`` or ``"feat(api)!:"``.
    """
    if scope is None:
        return f"{commit_type}:"
    if commit_type == CommitType.feat_breaking:
        return f"feat({scope})!:"
    return f"{commit_type}({scope}):"


def main() -> None:
    """Run the ``diffract`` command.

    The command reads the configuration files and the command-line arguments. Then it
    calls ``check`` or ``check_staged`` to find the public API changes. It writes the
    result as text or as JSON. With ``--validate-msg-file``, it checks the commit type
    in a commit message.

    If you use ``--validate-msg-file`` and give no BASE_REF or HEAD_REF, the command
    compares ``HEAD`` with the staging area. It uses
    :func:`~sheridan.diffract.checker.check_staged` for this.

    An unexpected exception does not show a traceback. diffract writes a short message
    with a link to the issue tracker to stderr.

    The exit codes:
      - 0: No public name changed, or the command has no ``--exit-code`` flag.
      - 1: A public name was removed (with ``--exit-code``), or the commit message
        tells less than the API change.
      - 2: A public name was added and no public name was removed (with ``--exit-code``).
      - 3: An error. This can be a usage error, a git, file or configuration error, or
        an unexpected exception.
    """
    try:
        _run()
    except Exception as exc:  # Every unexpected error must exit 3, not 1.
        print(
            f"diffract: unexpected error: {type(exc).__name__}: {exc}\n"
            f"This is a bug in diffract. Report it at {_ISSUES_URL}",
            file=sys.stderr,
        )
        sys.exit(_ERROR_EXIT_CODE)


def _run() -> None:
    """Parse the arguments, run the check and exit with the applicable code."""
    parser = _build_parser()
    args = parser.parse_args()

    repo_path = Path.cwd()
    # Find the root of the repository. Thus load_config finds the configuration files
    # also when you start diffract in a subdirectory.
    try:
        repo_root = Path(get_repo(repo_path).working_dir)
    except DiffractError:
        repo_root = repo_path  # No repository. check() will raise the correct error.

    try:
        config = load_config(repo_root)
        # The flags have priority over the configuration file and the defaults.
        src_path: str = args.src_path or config.src or "src"
        tests_path: str = args.tests_path or config.tests or "tests"

        if args.validate_msg_file is not None and not args.base_ref and not args.head_ref:
            result = check_staged(repo_path=repo_path, src_path=src_path, tests_path=tests_path)
        else:
            result = check(
                base_ref=args.base_ref or "HEAD~1",
                head_ref=args.head_ref or "HEAD",
                repo_path=repo_path,
                src_path=src_path,
                tests_path=tests_path,
            )
    except DiffractError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(_ERROR_EXIT_CODE)

    if args.validate_msg_file is not None:
        msg_path = Path(args.validate_msg_file)
        try:
            raw = msg_path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"diffract: cannot read the commit message file: {exc}", file=sys.stderr)
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
