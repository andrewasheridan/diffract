"""Command-line interface for [[ cookiecutter.project_slug ]]."""

__all__ = [
    "main",
]

import argparse
import sys

from sheridan.[[ cookiecutter.package_name ]] import __version__


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="[[ cookiecutter.cli_command ]]",
        description="[[ cookiecutter.description ]]",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # TODO: Add subcommands here
    subparsers.add_parser("version", help="Print the version and exit")

    return parser


def main() -> None:
    """CLI entrypoint for [[ cookiecutter.cli_command ]]."""
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "version":
        print(__version__)
        sys.exit(0)
    else:
        parser.print_help()
        sys.exit(1)
