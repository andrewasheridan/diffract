"""TOML config file support for sheridan-diffract."""

from __future__ import annotations

__all__ = ["DiffractConfig", "load_config"]

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sheridan.diffract.exceptions import DiffractError


@dataclass(frozen=True)
class DiffractConfig:
    """Configuration loaded from diffract.toml or pyproject.toml.

    Fields are None if not specified in any config file — the caller
    merges them with CLI flags and built-in defaults.

    Attributes:
        src: The source directory within the repository to scan, or None
            if not specified in any config file.
    """

    src: str | None = None


def _parse_src(data: dict[str, Any], config_file: Path) -> str | None:
    """Extract and validate the ``src`` key from a TOML data dict.

    Args:
        data: The parsed TOML table to read from.
        config_file: Path to the config file, used in error messages.

    Returns:
        The value of ``src`` as a string, or ``None`` if not present.

    Raises:
        DiffractError: If ``src`` is present but is not a string.
    """
    src = data.get("src")
    if src is None:
        return None
    if not isinstance(src, str):
        raise DiffractError(
            f"Invalid diffract config in {config_file}: 'src' must be a string, got {type(src).__name__!r}"
        )
    return src


def _load_toml(path: Path) -> dict[str, Any]:
    """Read and parse a TOML file, converting parse errors to DiffractError.

    Args:
        path: The TOML file to read.

    Returns:
        The parsed TOML document as a dict.

    Raises:
        DiffractError: If the file contains invalid TOML.
    """
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise DiffractError(f"Failed to parse {path}: {exc}") from exc


def load_config(repo_root: Path) -> DiffractConfig:
    """Load diffract configuration from the repo root.

    Checks for ``diffract.toml`` first, then ``pyproject.toml [tool.diffract]``.
    Returns a ``DiffractConfig`` with ``None`` for any field not found.

    Args:
        repo_root: The root directory of the git repository.

    Returns:
        A ``DiffractConfig`` populated from the first config file found,
        or an empty ``DiffractConfig`` if neither file exists.

    Raises:
        DiffractError: If a config file is found but contains invalid TOML
            or an ``src`` value that is not a string.
    """
    diffract_toml = repo_root / "diffract.toml"
    if diffract_toml.is_file():
        data = _load_toml(diffract_toml)
        return DiffractConfig(src=_parse_src(data, diffract_toml))

    pyproject_toml = repo_root / "pyproject.toml"
    if pyproject_toml.is_file():
        data = _load_toml(pyproject_toml)
        tool_diffract: dict[str, Any] = data.get("tool", {}).get("diffract", {})
        return DiffractConfig(src=_parse_src(tool_diffract, pyproject_toml))

    return DiffractConfig()
