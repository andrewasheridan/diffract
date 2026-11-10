"""Tests for sheridan.diffract.config."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from sheridan.diffract.config import DiffractConfig, load_config


class TestDiffractConfig:
    """Tests for the DiffractConfig dataclass."""

    def test_defaults_to_none(self) -> None:
        """DiffractConfig with no args must have src=None."""
        cfg = DiffractConfig()
        assert cfg.src is None

    def test_explicit_src(self) -> None:
        """DiffractConfig must store an explicit src value."""
        cfg = DiffractConfig(src="python/src")
        assert cfg.src == "python/src"

    def test_is_frozen(self) -> None:
        """DiffractConfig must be immutable (frozen dataclass)."""
        cfg = DiffractConfig(src="lib")
        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.src = "other"  # type: ignore[misc]


class TestLoadConfig:
    """Tests for load_config()."""

    def test_returns_empty_config_when_no_files(self, tmp_path: Path) -> None:
        """load_config must return a DiffractConfig with src=None when no config files exist."""
        result = load_config(tmp_path)
        assert result == DiffractConfig()
        assert result.src is None

    def test_reads_src_from_diffract_toml(self, tmp_path: Path) -> None:
        """load_config must read src from diffract.toml when present."""
        (tmp_path / "diffract.toml").write_text('src = "python/src"\n', encoding="utf-8")
        result = load_config(tmp_path)
        assert result.src == "python/src"

    def test_diffract_toml_without_src_returns_none(self, tmp_path: Path) -> None:
        """load_config must return src=None if diffract.toml exists but has no src key."""
        (tmp_path / "diffract.toml").write_text("[other]\nkey = 1\n", encoding="utf-8")
        result = load_config(tmp_path)
        assert result.src is None

    def test_reads_src_from_pyproject_toml(self, tmp_path: Path) -> None:
        """load_config must read src from [tool.diffract] in pyproject.toml."""
        (tmp_path / "pyproject.toml").write_text(
            '[tool.diffract]\nsrc = "lib"\n',
            encoding="utf-8",
        )
        result = load_config(tmp_path)
        assert result.src == "lib"

    def test_pyproject_toml_without_tool_diffract_returns_none(self, tmp_path: Path) -> None:
        """load_config must return src=None if pyproject.toml has no [tool.diffract] section."""
        (tmp_path / "pyproject.toml").write_text(
            "[tool.other]\nkey = 1\n",
            encoding="utf-8",
        )
        result = load_config(tmp_path)
        assert result.src is None

    def test_pyproject_toml_tool_diffract_without_src_returns_none(self, tmp_path: Path) -> None:
        """load_config must return src=None if [tool.diffract] exists but has no src key."""
        (tmp_path / "pyproject.toml").write_text(
            "[tool.diffract]\nother_key = true\n",
            encoding="utf-8",
        )
        result = load_config(tmp_path)
        assert result.src is None

    def test_diffract_toml_takes_priority_over_pyproject_toml(self, tmp_path: Path) -> None:
        """load_config must prefer diffract.toml over pyproject.toml when both are present."""
        (tmp_path / "diffract.toml").write_text('src = "from-diffract-toml"\n', encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text(
            '[tool.diffract]\nsrc = "from-pyproject"\n',
            encoding="utf-8",
        )
        result = load_config(tmp_path)
        assert result.src == "from-diffract-toml"

    def test_pyproject_toml_no_tool_section_returns_none(self, tmp_path: Path) -> None:
        """load_config must return src=None if pyproject.toml has no [tool] section at all."""
        (tmp_path / "pyproject.toml").write_text(
            "[build-system]\nrequires = []\n",
            encoding="utf-8",
        )
        result = load_config(tmp_path)
        assert result.src is None
