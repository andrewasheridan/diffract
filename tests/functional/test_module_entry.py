"""Run diffract as a module with ``python -m sheridan.diffract``."""

import subprocess  # nosec B404
import sys

from sheridan.diffract import __version__


def test_python_m_prints_the_version() -> None:
    """``python -m sheridan.diffract --version`` prints the version and exits 0."""
    proc = subprocess.run(  # nosec B603
        [sys.executable, "-m", "sheridan.diffract", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == f"diffract {__version__}"
