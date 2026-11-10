"""The exceptions of sheridan-diffract."""

__all__ = ["DiffractError", "GitError", "SurfaceError"]


class DiffractError(Exception):
    """The base class of all sheridan-diffract errors."""


class GitError(DiffractError):
    """A git command failed. For example, the repository or the ref does not exist."""


class SurfaceError(DiffractError):
    """iceberg cannot extract the public API."""
