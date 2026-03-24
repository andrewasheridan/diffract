"""Command-line interface for sheridan-diffract."""

from __future__ import annotations

__all__ = ["main"]

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from sheridan.diffract import __version__
from sheridan.diffract.checker import check
from sheridan.diffract.enums import CommitType
from sheridan.diffract.exceptions import DiffractError
from sheridan.diffract.models import DiffractResult, NameChange


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
        default="src",
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


def main() -> None:
    """CLI entrypoint for diffract."""
    parser = _build_parser()
    args = parser.parse_args()

    try:
        result = check(
            base_ref=args.base_ref,
            head_ref=args.head_ref,
            repo_path=Path.cwd(),
            src_path=args.src_path,
        )
    except DiffractError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(3)

    if args.output_json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(_format_human(result))

    sys.exit(_resolve_exit_code(result, args.exit_code))
