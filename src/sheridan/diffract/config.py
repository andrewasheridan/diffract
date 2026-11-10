"""Read the sheridan-diffract configuration from TOML files."""

__all__ = ["DiffractConfig", "load_config"]

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sheridan.diffract.exceptions import DiffractError


@dataclass(frozen=True)
class DiffractConfig:
    """The configuration from ``diffract.toml`` or ``pyproject.toml``.

    A field is ``None`` if no configuration file sets it. The caller then uses the CLI
    flag or the default value.

    Attributes:
        src: The source directory in the repository, or ``None`` if no configuration
            file sets it.
        tests: The test directory in the repository, or ``None`` if no configuration
            file sets it.
    """

    src: str | None = None
    tests: str | None = None


def _parse_str(data: dict[str, Any], key: str, config_file: Path) -> str | None:
    """Get a value from a TOML table and make sure that it is a string.

    Args:
        data: The parsed TOML table.
        key: The key of the value, for example ``"src"``.
        config_file: The path of the configuration file, for the error message.

    Returns:
        The value of ``key``, or ``None`` if the table has no ``key`` key.

    Raises:
        DiffractError: If the value is not a string.
    """
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise DiffractError(
            f"Incorrect diffract configuration in {config_file}: {key!r} must be a string, not {type(value).__name__!r}"
        )
    return value


def _parse_config(data: dict[str, Any], config_file: Path) -> DiffractConfig:
    """Make a ``DiffractConfig`` from the diffract TOML table.

    Args:
        data: The parsed diffract TOML table.
        config_file: The path of the configuration file, for the error message.

    Returns:
        The configuration in the table.

    Raises:
        DiffractError: If ``src`` or ``tests`` is not a string.
    """
    return DiffractConfig(
        src=_parse_str(data, "src", config_file),
        tests=_parse_str(data, "tests", config_file),
    )


def _get_table(data: dict[str, Any], key: str, config_file: Path, prefix: str = "") -> dict[str, Any]:
    """Get a TOML table from a parsed TOML table.

    Args:
        data: The parsed TOML table.
        key: The key of the table to get.
        config_file: The path of the configuration file, for the error message.
        prefix: The dotted path of ``data`` in the file, for the error message.

    Returns:
        The table at ``key``, or an empty dict if ``key`` is not present.

    Raises:
        DiffractError: If the value of ``key`` is not a table.
    """
    table = data.get(key, {})
    if not isinstance(table, dict):
        raise DiffractError(
            f"Incorrect diffract configuration in {config_file}: "
            f"'{prefix}{key}' must be a table, not {type(table).__name__!r}"
        )
    return table


def _load_toml(path: Path) -> dict[str, Any]:
    """Read and parse a TOML file. Change a parse error to a ``DiffractError``.

    Args:
        path: The TOML file to read.

    Returns:
        The parsed TOML document as a dict.

    Raises:
        DiffractError: If the file is not correct TOML.
    """
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise DiffractError(f"Cannot parse {path}: {exc}") from exc


def load_config(repo_root: Path) -> DiffractConfig:
    """Read the diffract configuration from the root of the repository.

    The function reads ``diffract.toml`` first. If that file does not exist, it reads
    ``[tool.diffract]`` in ``pyproject.toml``. A field that no file sets is ``None``.

    Args:
        repo_root: The root directory of the git repository.

    Returns:
        A ``DiffractConfig`` from the first configuration file that exists, or an
        empty ``DiffractConfig`` if the two files do not exist.

    Raises:
        DiffractError: If the configuration file is not correct TOML, if ``tool`` or
            ``tool.diffract`` is not a table, or if ``src`` or ``tests`` is not a string.
    """
    diffract_toml = repo_root / "diffract.toml"
    if diffract_toml.is_file():
        data = _load_toml(diffract_toml)
        return _parse_config(data, diffract_toml)

    pyproject_toml = repo_root / "pyproject.toml"
    if pyproject_toml.is_file():
        data = _load_toml(pyproject_toml)
        tool = _get_table(data, "tool", pyproject_toml)
        tool_diffract = _get_table(tool, "diffract", pyproject_toml, prefix="tool.")
        return _parse_config(tool_diffract, pyproject_toml)

    return DiffractConfig()
