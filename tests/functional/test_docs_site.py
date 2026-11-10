"""Build the docs site and keep the navigation in step with the pages in ``docs/``."""

import shutil
import subprocess  # nosec B404
import sysconfig
import tomllib
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DOCS = _PROJECT_ROOT / "docs"
_ZENSICAL = Path(sysconfig.get_path("scripts")) / "zensical"

if not (_PROJECT_ROOT / "zensical.toml").is_file():
    pytest.skip("The sdist does not contain the docs site.", allow_module_level=True)


def _nav_pages(entries: list[dict[str, object]]) -> set[str]:
    """Get the page paths from the ``nav`` of ``zensical.toml``.

    Args:
        entries: The ``nav`` list, or the list of one nav section.

    Returns:
        The paths of all the pages, relative to ``docs/``.
    """
    pages: set[str] = set()

    for entry in entries:
        for value in entry.values():
            if isinstance(value, str):
                pages.add(value)
            elif isinstance(value, list):
                pages |= _nav_pages(value)

    return pages


_CONFIG = tomllib.loads((_PROJECT_ROOT / "zensical.toml").read_text(encoding="utf-8"))
_NAV_PAGES = _nav_pages(_CONFIG["project"]["nav"])
_DOCS_PAGES = sorted(path.relative_to(_DOCS).as_posix() for path in _DOCS.rglob("*.md"))


def test_index_includes_the_readme() -> None:
    """The home page must include the README, so that the two cannot differ."""
    index = _DOCS / "index.md"

    assert index.read_text(encoding="utf-8") == '--8<-- "README.md"\n'


@pytest.mark.parametrize("page", _DOCS_PAGES)
def test_page_is_in_the_nav(page: str) -> None:
    assert page in _NAV_PAGES, f"Add {page} to the nav in zensical.toml"


@pytest.mark.parametrize("page", sorted(_NAV_PAGES))
def test_nav_page_exists(page: str) -> None:
    assert (_DOCS / page).is_file(), f"Remove {page} from the nav in zensical.toml, or add docs/{page}"


def test_api_reference_uses_mkdocstrings() -> None:
    api_page = (_DOCS / "api" / "api.md").read_text(encoding="utf-8")

    assert "::: sheridan.diffract\n" in api_page


@pytest.mark.skipif(not _ZENSICAL.is_file(), reason="zensical is in the dev group, not in the test group")
def test_site_builds_in_strict_mode(tmp_path: Path) -> None:
    """Build a copy of the site. Strict mode makes a broken link or a missing snippet fail the build.

    The build uses a copy because zensical writes the site and a cache next to its
    configuration file, and it does not accept absolute paths in the configuration.
    """
    shutil.copy(_PROJECT_ROOT / "zensical.toml", tmp_path)
    shutil.copy(_PROJECT_ROOT / "README.md", tmp_path)
    shutil.copytree(_DOCS, tmp_path / "docs")
    shutil.copytree(_PROJECT_ROOT / "src", tmp_path / "src", ignore=shutil.ignore_patterns("__pycache__"))

    result = subprocess.run(  # nosec B603
        [str(_ZENSICAL), "build", "--strict"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "site" / "index.html").is_file()
    assert (tmp_path / "site" / "api" / "api" / "index.html").is_file()
