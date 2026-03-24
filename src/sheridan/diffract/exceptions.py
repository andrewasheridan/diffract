"""Exceptions for sheridan-diffract."""

from __future__ import annotations

__all__ = ["DiffractError", "GitError", "SurfaceError"]


class DiffractError(Exception):
    """Base exception for all sheridan-diffract errors."""


class GitError(DiffractError):
    """Raised when a git operation fails (repo not found, bad ref, etc.)."""


class SurfaceError(DiffractError):
    """Raised when iceberg fails to extract a public API surface."""
