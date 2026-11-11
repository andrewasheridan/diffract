"""sheridan-diffract: find the public API changes between two git refs and give the commit type."""

__all__ = [
    "ApiDiff",
    "ChangeKind",
    "CommitType",
    "DiffractError",
    "DiffractResult",
    "GitError",
    "NameChange",
    "SignatureChange",
    "SurfaceError",
    "__version__",
    "check",
    "check_staged",
]

import importlib.metadata

from sheridan.diffract._checker import check, check_staged
from sheridan.diffract._enums import ChangeKind, CommitType
from sheridan.diffract._exceptions import DiffractError, GitError, SurfaceError
from sheridan.diffract._models import ApiDiff, DiffractResult, NameChange, SignatureChange

try:
    __version__: str = importlib.metadata.version("sheridan-diffract")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0+unknown"
