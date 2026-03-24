"""sheridan-diffract: Detect public API changes between git refs and classify commits."""

from __future__ import annotations

__all__ = [
    "ApiDiff",
    "ChangeKind",
    "CommitType",
    "DiffractConfig",
    "DiffractError",
    "DiffractResult",
    "GitError",
    "NameChange",
    "SurfaceError",
    "__version__",
    "check",
    "check_staged",
    "load_config",
]

import importlib.metadata

from sheridan.diffract.checker import check, check_staged
from sheridan.diffract.config import DiffractConfig, load_config
from sheridan.diffract.enums import ChangeKind, CommitType
from sheridan.diffract.exceptions import DiffractError, GitError, SurfaceError
from sheridan.diffract.models import ApiDiff, DiffractResult, NameChange

try:
    __version__: str = importlib.metadata.version("sheridan-diffract")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0+unknown"
