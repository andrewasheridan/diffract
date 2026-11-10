"""Tests for sheridan.diffract.config."""

import dataclasses
import re
from pathlib import Path

import pytest

from sheridan.diffract.config import DiffractConfig, load_config
from sheridan.diffract.exceptions import DiffractError


class TestDiffractConfig:
    """Tests for the DiffractConfig dataclass."""

    def test_defaults_to_none(self) -> None:
        """DiffractConfig with no arguments must have src=None."""
        cfg = DiffractConfig()
        assert cfg.src is None

    def test_explicit_src(self) -> None:
        """DiffractConfig must keep a src value that you give."""
        cfg = DiffractConfig(src="python/src")
        assert cfg.src == "python/src"

    def test_is_frozen(self) -> None:
        """You must not change a DiffractConfig (a frozen dataclass)."""
        cfg = DiffractConfig(src="lib")
        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.src = "other"  # type: ignore[misc]


class TestLoadConfig:
    """Tests for load_config()."""

    def test_returns_empty_config_when_no_files(self, tmp_path: Path) -> None:
        """load_config must give src=None if no configuration file exists."""
        result = load_config(tmp_path)
        assert result == DiffractConfig()
        assert result.src is None

    def test_reads_src_from_diffract_toml(self, tmp_path: Path) -> None:
        """load_config must read src from diffract.toml if the file exists."""
        (tmp_path / "diffract.toml").write_text('src = "python/src"\n', encoding="utf-8")
        result = load_config(tmp_path)
        assert result.src == "python/src"

    def test_diffract_toml_without_src_returns_none(self, tmp_path: Path) -> None:
        """load_config must give src=None if diffract.toml has no src key."""
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
        """load_config must give src=None if pyproject.toml has no [tool.diffract] table."""
        (tmp_path / "pyproject.toml").write_text(
            "[tool.other]\nkey = 1\n",
            encoding="utf-8",
        )
        result = load_config(tmp_path)
        assert result.src is None

    def test_pyproject_toml_tool_diffract_without_src_returns_none(self, tmp_path: Path) -> None:
        """load_config must give src=None if [tool.diffract] has no src key."""
        (tmp_path / "pyproject.toml").write_text(
            "[tool.diffract]\nother_key = true\n",
            encoding="utf-8",
        )
        result = load_config(tmp_path)
        assert result.src is None

    def test_diffract_toml_takes_priority_over_pyproject_toml(self, tmp_path: Path) -> None:
        """load_config must use diffract.toml, not pyproject.toml, if the two files exist."""
        (tmp_path / "diffract.toml").write_text('src = "from-diffract-toml"\n', encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text(
            '[tool.diffract]\nsrc = "from-pyproject"\n',
            encoding="utf-8",
        )
        result = load_config(tmp_path)
        assert result.src == "from-diffract-toml"

    def test_pyproject_toml_no_tool_section_returns_none(self, tmp_path: Path) -> None:
        """load_config must give src=None if pyproject.toml has no [tool] table."""
        (tmp_path / "pyproject.toml").write_text(
            "[build-system]\nrequires = []\n",
            encoding="utf-8",
        )
        result = load_config(tmp_path)
        assert result.src is None

    def test_non_string_src_in_diffract_toml_raises(self, tmp_path: Path) -> None:
        """load_config must raise DiffractError that names diffract.toml if src is not a string."""
        config_file = tmp_path / "diffract.toml"
        config_file.write_text("src = 3\n", encoding="utf-8")
        with pytest.raises(DiffractError, match=re.escape(str(config_file))):
            load_config(tmp_path)

    def test_tool_diffract_not_a_table_raises(self, tmp_path: Path) -> None:
        """load_config must raise DiffractError that names pyproject.toml if tool.diffract is not a table."""
        config_file = tmp_path / "pyproject.toml"
        config_file.write_text('[tool]\ndiffract = "x"\n', encoding="utf-8")
        with pytest.raises(DiffractError, match=re.escape(str(config_file))):
            load_config(tmp_path)

    def test_tool_not_a_table_raises(self, tmp_path: Path) -> None:
        """load_config must raise DiffractError that names pyproject.toml if tool is not a table."""
        config_file = tmp_path / "pyproject.toml"
        config_file.write_text('tool = "x"\n', encoding="utf-8")
        with pytest.raises(DiffractError, match=re.escape(str(config_file))):
            load_config(tmp_path)


class TestTestsSetting:
    """Tests for the ``tests`` setting. It works the same as ``src``."""

    def test_defaults_to_none(self, tmp_path: Path) -> None:
        assert load_config(tmp_path).tests is None

    def test_reads_tests_from_diffract_toml(self, tmp_path: Path) -> None:
        (tmp_path / "diffract.toml").write_text('src = "src"\ntests = "src/pkg/tests"\n', encoding="utf-8")
        result = load_config(tmp_path)
        assert result.src == "src"
        assert result.tests == "src/pkg/tests"

    def test_reads_tests_from_pyproject_toml(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[tool.diffract]\ntests = "test"\n', encoding="utf-8")
        result = load_config(tmp_path)
        assert result.src is None
        assert result.tests == "test"

    def test_diffract_toml_takes_priority_over_pyproject_toml(self, tmp_path: Path) -> None:
        (tmp_path / "diffract.toml").write_text('tests = "from-diffract-toml"\n', encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text('[tool.diffract]\ntests = "from-pyproject"\n', encoding="utf-8")
        assert load_config(tmp_path).tests == "from-diffract-toml"

    @pytest.mark.parametrize("file_text", ["tests = 3\n", "tests = ['a']\n"])
    def test_non_string_tests_raises(self, tmp_path: Path, file_text: str) -> None:
        (tmp_path / "diffract.toml").write_text(file_text, encoding="utf-8")
        with pytest.raises(DiffractError, match="'tests' must be a string"):
            load_config(tmp_path)
