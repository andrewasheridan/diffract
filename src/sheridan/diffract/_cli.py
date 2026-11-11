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
from sheridan.diffract._checker import check, check_staged
from sheridan.diffract._classifier import group_by_module, group_changes_by_module
from sheridan.diffract._config import load_config
from sheridan.diffract._enums import CommitType
from sheridan.diffract._exceptions import DiffractError
from sheridan.diffract._git_utils import get_comment_prefixes, get_repo
from sheridan.diffract._models import DiffractResult

_COMMIT_TYPE_RE: re.Pattern[str] = re.compile(r"^([a-z]+)(\(([^)]*)\))?(!)?:")
_BREAKING_FOOTER_RE: re.Pattern[str] = re.compile(r"^BREAKING[ -]CHANGE: ", re.MULTILINE)
_ISSUES_URL = "https://github.com/andrewasheridan/diffract/issues"
_ERROR_EXIT_CODE = 3
# Only for these groups can diffract give one commit prefix.
_FEATURE_TYPES = (CommitType.feat_breaking, CommitType.feat)
_CONVENTIONAL_TYPES = frozenset(
    {"feat", "fix", "refactor", "perf", "style", "test", "docs", "ci", "chore", "build", "revert"}
)
# git writes these messages itself. diffract does not check them.
_GIT_MESSAGE_PREFIXES = ("Merge ", 'Revert "', "fixup! ", "amend! ", "squash! ")
# A change in behavior does not always change a public name. Thus feat is also
# possible when diffract finds only a code change.
_ALLOWED_TYPES: dict[CommitType, frozenset[str]] = {
    CommitType.feat_breaking: frozenset(),
    CommitType.feat: frozenset({"feat"}),
    CommitType.code: frozenset({"fix", "refactor", "perf", "style", "feat"}),
    CommitType.test: frozenset({"test"}),
    CommitType.other: frozenset({"docs", "ci", "chore", "build"}),
}
# For these groups, a breaking message is always correct.
_BREAKING_ALLOWED = (CommitType.feat_breaking, CommitType.feat, CommitType.code)


@dataclass(frozen=True)
class _WrittenType:
    """The commit type that a commit message gives.

    Attributes:
        base: The type without scope and ``!``, for example ``"fix"``.
        scope: The scope without parentheses, for example ``"parser"``, or ``None``.
        breaking: True if the header has a ``!`` or the body has a ``BREAKING CHANGE:`` footer.
    """

    base: str
    scope: str | None
    breaking: bool

    @property
    def label(self) -> str:
        """The type as the error message shows it, for example ``"fix(parser)!"``."""
        scope = f"({self.scope})" if self.scope is not None else ""
        bang = "!" if self.breaking else ""
        return f"{self.base}{scope}{bang}"


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
        metavar="SRC",
        dest="src_path",
        help="The directory in the repository that contains the Python packages (default: src).",
    )
    parser.add_argument(
        "--tests",
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
        help=(
            "Exit 1 if a public name was removed or had a breaking change, 2 if a public name was added "
            "or had a change that only adds to it, and 0 if no public name changed."
        ),
    )
    parser.add_argument(
        "--validate-msg-file",
        metavar="MSGFILE",
        help=(
            "The path of a commit message file. The check fails if the commit type is not "
            "possible for the change. Removed public names and breaking changes need a '!' or a "
            "'BREAKING CHANGE:' footer. Added public names need 'feat' or a '!'. Code changes need "
            "fix, refactor, perf, style, feat or a '!'. Test changes need test. Other changes need "
            "docs, ci, chore or build. A message with no known type fails. diffract does not check "
            "merge, revert, fixup, amend and squash messages from git."
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
        if result.diff.breaking_changes:
            lines.append("Breaking changes:")
            for module, texts in group_changes_by_module(result.diff.breaking_changes).items():
                lines.append(f"  {module}:")
                for text in texts:
                    lines.append(f"    ! {text}")
        if result.diff.additive_changes:
            lines.append("Changes that add to public names:")
            for module, texts in group_changes_by_module(result.diff.additive_changes).items():
                lines.append(f"  {module}:")
                for text in texts:
                    lines.append(f"    ~ {text}")

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
        ``1`` if a public name was removed or had a breaking change, ``2`` if a
        public name was added or had a change that only adds to it, and ``0`` if no
        public name changed.
    """
    if not use_exit_code:
        return 0
    if result.diff.is_breaking:
        return 1
    if not result.diff.is_empty:
        return 2
    return 0


def _remove_comments(message: str, comment_prefixes: tuple[str, ...]) -> str:
    """Remove the comment lines and the blank lines at the start of a commit message.

    git gives the ``commit-msg`` hook the message file before it removes these lines.

    Args:
        message: The full commit message, as git wrote it to the message file.
        comment_prefixes: The texts at the start of a comment line.

    Returns:
        The message without its comment lines, which starts at its first line that is not blank.
    """
    lines = [line for line in message.splitlines() if not line.startswith(comment_prefixes)]
    while lines and not lines[0].strip():
        lines.pop(0)
    return "\n".join(lines)


def _parse_written_type(message: str) -> _WrittenType | None:
    """Parse the Conventional Commit type from a commit message.

    The function knows all the Conventional Commit types, with or without a scope and
    a ``!``.

    Args:
        message: The full commit message. The type is in the first line. A
            ``BREAKING CHANGE:`` or ``BREAKING-CHANGE:`` footer can be in the lines after it.

    Returns:
        The written type, or ``None`` if the first line has no type or an unknown type.
    """
    lines = message.splitlines()
    # Each first line with no type gives None, thus a different default text has no effect.
    first_line = lines[0] if lines else ""  # pragma: no mutate
    m = _COMMIT_TYPE_RE.match(first_line)
    if m is None or m.group(1) not in _CONVENTIONAL_TYPES:
        return None

    body = "\n".join(lines[1:])
    breaking = m.group(4) is not None or _BREAKING_FOOTER_RE.search(body) is not None

    return _WrittenType(base=m.group(1), scope=m.group(3), breaking=breaking)


def _is_written_by_git(message: str) -> bool:
    """Find if git wrote the commit message, for a merge, a revert, a fixup, an amend or a squash.

    Args:
        message: The full commit message.

    Returns:
        True if the first line starts as git writes it.
    """
    return message.startswith(_GIT_MESSAGE_PREFIXES)


def _is_allowed(written: _WrittenType, commit_type: CommitType) -> bool:
    """Find if a written commit type is possible for the result of diffract.

    A ``revert`` type is always possible, because a revert can undo any change.

    Args:
        written: The commit type from the message.
        commit_type: The group of possible types that diffract found.

    Returns:
        True if the written type is possible for the result.
    """
    if written.base == "revert":
        return True
    if written.breaking and commit_type in _BREAKING_ALLOWED:
        return True
    return written.base in _ALLOWED_TYPES[commit_type]


def _describe_allowed(commit_type: CommitType) -> str:
    """Write the commit types that are possible for a result, for the error message.

    Args:
        commit_type: The group of possible types that diffract found.

    Returns:
        The possible types, for example ``"fix, refactor, perf, style"``.
    """
    if commit_type == CommitType.feat_breaking:
        return "any type with a '!' or a 'BREAKING CHANGE:' footer"

    types = list(commit_type.possible_types)
    for base in sorted(_ALLOWED_TYPES[commit_type] - set(types)):
        types.append(base)
    text = ", ".join(types)

    if commit_type in _BREAKING_ALLOWED:
        text += ", or any type with a '!' or a 'BREAKING CHANGE:' footer"
    return text


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
    :func:`~sheridan.diffract._checker.check_staged` for this.

    An unexpected exception does not show a traceback. diffract writes a short message
    with a link to the issue tracker to stderr.

    The exit codes:
      - 0: No public name changed, or the command has no ``--exit-code`` flag.
      - 1: A public name was removed or had a breaking change (with ``--exit-code``),
        or the commit type in the commit message is not possible for the change.
      - 2: A public name was added or had a change that only adds to it, and no
        breaking change occurred (with ``--exit-code``).
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
    repo = None
    try:
        repo = get_repo(repo_path)
        repo_root = Path(repo.working_dir)
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
            # The case of a codec name has no effect. Only a locale that is not UTF-8 shows a missing encoding.
            raw = msg_path.read_text(encoding="utf-8")  # pragma: no mutate
        except OSError as exc:
            print(f"diffract: cannot read the commit message file: {exc}", file=sys.stderr)
            sys.exit(_ERROR_EXIT_CODE)

        comment_prefixes = get_comment_prefixes(repo) if repo is not None else ("#",)
        message = _remove_comments(raw, comment_prefixes)
        if _is_written_by_git(message):
            sys.exit(0)

        written = _parse_written_type(message)
        if written is not None and _is_allowed(written, result.commit_type):
            sys.exit(0)

        scope = written.scope if written is not None else None
        written_label = written.label if written is not None else "(no known type)"
        print(_format_human(result, scope=scope), file=sys.stderr)
        print(
            f"\ndiffract: commit type mismatch"
            f"\n  written:  {written_label}"
            f"\n  possible: {_describe_allowed(result.commit_type)}",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.output_json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(_format_human(result))

    sys.exit(_resolve_exit_code(result, args.exit_code))
