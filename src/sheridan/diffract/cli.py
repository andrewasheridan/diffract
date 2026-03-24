"""Command-line interface for sheridan-diffract."""

from __future__ import annotations

__all__ = ["main"]

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from sheridan.diffract import __version__
from sheridan.diffract.checker import check
from sheridan.diffract.config import load_config
from sheridan.diffract.enums import CommitType
from sheridan.diffract.exceptions import DiffractError
from sheridan.diffract.git_utils import get_repo
from sheridan.diffract.models import DiffractResult, NameChange

_COMMIT_TYPE_RE: re.Pattern[str] = re.compile(r"^(feat|fix|refactor)(\([^)]*\))?(!)?:")


def _build_parser() -> argparse.ArgumentParser:
    """Construct and return the argument parser for the diffract CLI.

    Returns:
        A fully-configured :class:`argparse.ArgumentParser` instance.
    """
    parser = argparse.ArgumentParser(
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
        default="HEAD~1",
        metavar="BASE_REF",
        help="The earlier git ref to compare (default: HEAD~1).",
    )
    parser.add_argument(
        "head_ref",
        nargs="?",
        default="HEAD",
        metavar="HEAD_REF",
        help="The later git ref to compare (default: HEAD).",
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
        help="Path to commit message file; validates written type against detected API change.",
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


def _format_human(result: DiffractResult) -> str:
    """Format a DiffractResult as human-readable text.

    Args:
        result: The diffract result to format.

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
    lines.append(f"Suggested commit prefix: {commit_label}:")

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


def _parse_commit_type(first_line: str) -> CommitType | None:
    """Parse the conventional commit type from the first line of a commit message.

    Recognises ``feat``, ``feat!``, ``fix``, and ``refactor`` (with or without
    a scope in parentheses). Any other prefix — including ``docs:``, ``chore:``,
    ``test:``, etc. — returns ``None`` so that non-conventional commits are
    never blocked.

    Args:
        first_line: The first line of the commit message.

    Returns:
        The matching :class:`~sheridan.diffract.enums.CommitType`, or ``None``
        if the line does not start with a recognised conventional-commit type.
    """
    m = _COMMIT_TYPE_RE.match(first_line)
    if m is None:
        return None
    base, _scope, bang = m.group(1), m.group(2), m.group(3)
    match (base, bool(bang)):
        case ("feat", True):
            return CommitType.feat_breaking
        case ("feat", False):
            return CommitType.feat
        case ("fix", _):
            return CommitType.fix
        case ("refactor", _):
            return CommitType.refactor
        case _:
            return None


def main() -> None:
    """CLI entrypoint for diffract.

    Loads configuration from config files (if present), parses command-line arguments,
    and invokes the check() function to detect API changes. Outputs results as
    human-readable text or JSON, and optionally validates commit message types.

    Exits with code:
      - 0: No changes detected (or --exit-code not set)
      - 1: Breaking changes detected (with --exit-code), or commit message mismatch
      - 2: Non-breaking API changes detected (with --exit-code)
      - 3: Error during processing (git, file I/O, or surface detection)
    """
    parser = _build_parser()
    args = parser.parse_args()

    repo_path = Path.cwd()
    # Resolve the actual git repo root so load_config finds config files
    # correctly even when diffract is invoked from a subdirectory.
    try:
        repo_root = Path(get_repo(repo_path).working_dir)
    except DiffractError:
        repo_root = repo_path  # no repo found; check() will raise the proper error
    config = load_config(repo_root)
    # Priority: --src flag > config file > built-in default
    src_path: str = args.src_path or config.src or "src"

    try:
        result = check(
            base_ref=args.base_ref,
            head_ref=args.head_ref,
            repo_path=repo_path,
            src_path=src_path,
        )
    except DiffractError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(3)

    if args.validate_msg_file is not None:
        msg_path = Path(args.validate_msg_file)
        try:
            raw = msg_path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"diffract: cannot read commit message file: {exc}", file=sys.stderr)
            sys.exit(3)

        _lines = raw.splitlines()
        first_line = _lines[0] if _lines else ""
        written_type = _parse_commit_type(first_line)

        if written_type is None:
            sys.exit(0)
        if written_type == result.commit_type:
            sys.exit(0)

        print(_format_human(result), file=sys.stderr)
        print(
            f"\ndiffract: commit type mismatch\n  written:  {written_type}:\n  detected: {result.commit_type}:",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.output_json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(_format_human(result))

    sys.exit(_resolve_exit_code(result, args.exit_code))
