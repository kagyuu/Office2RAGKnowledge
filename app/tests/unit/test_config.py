"""U001-T5 の単体テスト: 設定ファイルの読み込みと検証 (API-07)。"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from office2ragknowledge.config import load_config
from office2ragknowledge.errors import ConfigError
from office2ragknowledge.models import ExcelModes, ImageMode, OnExists


@contextmanager
def chdir(path: Path) -> Iterator[None]:
    old = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


def write_toml(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


# ケース1: 設定ファイルが無ければ既定値
def test_defaults_without_config(tmp_path: Path) -> None:
    with chdir(tmp_path):
        config = load_config()
    assert config.convert.excel.modes is ExcelModes.BOTH
    assert config.convert.shapes is True
    assert config.batch.on_exists is OnExists.SKIP


# ケース2: 各テーブルの値が反映される
def test_values_are_applied(tmp_path: Path) -> None:
    path = write_toml(
        tmp_path / "office2rag.toml",
        """
[convert]
recursive = true
on_exists = "overwrite"
images = "extract"
shapes = false

[excel]
modes = "grid"
grid_separator = " "
max_table_regions = 50
max_rows = 500

[log]
level = "verbose"
format = "json"
""",
    )
    config = load_config(path)
    assert config.batch.recursive is True
    assert config.batch.on_exists is OnExists.OVERWRITE
    assert config.convert.images is ImageMode.EXTRACT
    assert config.convert.shapes is False
    assert config.convert.excel.modes is ExcelModes.GRID
    assert config.convert.excel.grid_separator == " "
    assert config.convert.excel.max_table_regions == 50
    assert config.convert.excel.max_rows == 500
    assert config.log.level == "verbose"
    assert config.log.format == "json"


# ケース3: 未知のキーで ConfigError、メッセージにキー名を含む
def test_unknown_key_raises(tmp_path: Path) -> None:
    path = write_toml(tmp_path / "office2rag.toml", "[excel]\nunknown_key = 1\n")
    with pytest.raises(ConfigError) as exc:
        load_config(path)
    assert "unknown_key" in str(exc.value)


# ケース4: 未知のテーブルで ConfigError
def test_unknown_table_raises(tmp_path: Path) -> None:
    path = write_toml(tmp_path / "office2rag.toml", "[unknown]\nx = 1\n")
    with pytest.raises(ConfigError) as exc:
        load_config(path)
    assert "unknown" in str(exc.value)


# ケース5: TOML の構文エラー
def test_syntax_error_raises(tmp_path: Path) -> None:
    path = write_toml(tmp_path / "office2rag.toml", "[excel\nmodes = ")
    with pytest.raises(ConfigError):
        load_config(path)


# ケース6: 列挙値が候補外
def test_invalid_enum_raises(tmp_path: Path) -> None:
    path = write_toml(tmp_path / "office2rag.toml", '[excel]\nmodes = "invalid"\n')
    with pytest.raises(ConfigError) as exc:
        load_config(path)
    assert "modes" in str(exc.value)


# ケース7: max_table_regions = 0 は範囲外
def test_max_table_regions_zero_is_rejected(tmp_path: Path) -> None:
    path = write_toml(tmp_path / "office2rag.toml", "[excel]\nmax_table_regions = 0\n")
    with pytest.raises(ConfigError):
        load_config(path)


# ケース8: max_rows = 0 は受理される (無制限の意味)
def test_max_rows_zero_is_accepted(tmp_path: Path) -> None:
    path = write_toml(tmp_path / "office2rag.toml", "[excel]\nmax_rows = 0\n")
    config = load_config(path)
    assert config.convert.excel.max_rows == 0


# ケース9: grid_separator に改行を含む
def test_grid_separator_with_newline_is_rejected(tmp_path: Path) -> None:
    path = write_toml(tmp_path / "office2rag.toml", '[excel]\ngrid_separator = "a\\nb"\n')
    with pytest.raises(ConfigError) as exc:
        load_config(path)
    assert "改行" in str(exc.value)


# ケース10: grid_separator が9文字で上限超過
def test_grid_separator_too_long_is_rejected(tmp_path: Path) -> None:
    path = write_toml(tmp_path / "office2rag.toml", '[excel]\ngrid_separator = "123456789"\n')
    with pytest.raises(ConfigError):
        load_config(path)


# ケース11: 誤った階層のキー
def test_key_in_wrong_table_raises(tmp_path: Path) -> None:
    path = write_toml(tmp_path / "office2rag.toml", "[log]\njobs = 4\n")
    with pytest.raises(ConfigError):
        load_config(path)


# ケース12: 上位ディレクトリの設定ファイルが自動探索される
def test_config_is_found_in_parent(tmp_path: Path) -> None:
    write_toml(tmp_path / "office2rag.toml", '[excel]\nmodes = "table"\n')
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    with chdir(nested):
        config = load_config()
    assert config.convert.excel.modes is ExcelModes.TABLE


def test_missing_explicit_path_raises(tmp_path: Path) -> None:
    """明示指定したファイルが存在しなければエラー。"""
    with pytest.raises(ConfigError):
        load_config(tmp_path / "notfound.toml")


def test_bool_type_is_checked(tmp_path: Path) -> None:
    path = write_toml(tmp_path / "office2rag.toml", '[excel]\ntable_regions = "yes"\n')
    with pytest.raises(ConfigError):
        load_config(path)
