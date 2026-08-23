"""設定ファイルの読み込みと値の検証 (API-07 / REQ-F-098)。

**未知のキーはエラーとする。** 綴り間違いが黙って無視されると、利用者は設定が
効いていると誤解するため。

検証関数は CLI 層 (``cli/options.py``) からも再利用する。同じ検証を二重に
実装しない。
"""

from __future__ import annotations

import tomllib
from dataclasses import replace
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

from .errors import ConfigError
from .models import (
    BatchOptions,
    Config,
    ConvertOptions,
    ExcelModes,
    ExcelOptions,
    ImageMode,
    LogOptions,
    OnExists,
    ShapeStyle,
)

__all__ = [
    "CONFIG_FILENAME",
    "MAX_GRID_SEPARATOR_LEN",
    "find_config_file",
    "load_config",
    "validate_enum",
    "validate_grid_separator",
    "validate_int_range",
]

CONFIG_FILENAME = "office2rag.toml"
MAX_GRID_SEPARATOR_LEN = 8

_CONVERT_KEYS = frozenset(
    {
        "output",
        "recursive",
        "on_exists",
        "images",
        "shapes",
        "shape_style",
        "include_hidden",
        "notes",
        "headers_footers",
        "comments",
        "jobs",
        "front_matter",
    }
)
_EXCEL_KEYS = frozenset(
    {"modes", "grid_separator", "table_regions", "max_table_regions", "formulas", "max_rows"}
)
_LOG_KEYS = frozenset({"level", "format", "file"})
_TABLES = {"convert": _CONVERT_KEYS, "excel": _EXCEL_KEYS, "log": _LOG_KEYS}


_EnumT = TypeVar("_EnumT", bound=Enum)


def validate_enum(value: Any, enum_cls: type[_EnumT], key: str) -> _EnumT:
    """列挙値を検証する。候補外なら ``ConfigError`` (E-013 相当)。

    PEP 695 の型パラメータ構文は Python 3.12 以降でしか使えないため、
    ``TypeVar`` を用いる (REQ-NF-017: 3.11 以上で動作すること)。
    """
    try:
        return enum_cls(value)
    except (ValueError, KeyError) as exc:
        choices = ", ".join(str(m.value) for m in enum_cls)
        raise ConfigError(
            f"{key} の値 '{value}' は不正です",
            hint=f"指定できる値: {choices}",
        ) from exc


def validate_int_range(value: Any, low: int, high: int, key: str) -> int:
    """整数の範囲を検証する。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{key} には整数を指定してください (指定値: {value!r})")
    if not (low <= value <= high):
        raise ConfigError(f"{key} は {low}〜{high} の範囲で指定してください (指定値: {value})")
    return value


def validate_grid_separator(value: Any, key: str = "--grid-separator") -> str:
    """方眼紙モードの区切り文字を検証する (V-21)。"""
    if not isinstance(value, str):
        raise ConfigError(f"{key} には文字列を指定してください")
    if "\n" in value or "\r" in value:
        raise ConfigError(
            f"{key} に改行文字は指定できません",
            hint="セルを連結する際に挟む短い文字列を指定してください (既定: なし)。",
        )
    if len(value) > MAX_GRID_SEPARATOR_LEN:
        raise ConfigError(
            f"{key} は {MAX_GRID_SEPARATOR_LEN} 文字以内で指定してください"
            f" (指定値: {len(value)} 文字)"
        )
    return value


def _require_bool(value: Any, key: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{key} には true または false を指定してください")
    return value


def find_config_file(start: Path | None = None) -> Path | None:
    """カレントから上位に向かって設定ファイルを探索する。"""
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        candidate = directory / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
    return None


def _check_unknown(data: dict[str, Any], path: Path) -> None:
    for table, keys in ((k, v) for k, v in data.items() if True):
        if table not in _TABLES:
            raise ConfigError(
                f"設定ファイルに未知のテーブル [{table}] が含まれています",
                path=path,
                hint=f"指定できるテーブル: {', '.join(sorted(_TABLES))}",
            )
        if not isinstance(keys, dict):
            raise ConfigError(f"設定ファイルの [{table}] はテーブルである必要があります", path=path)
        unknown = set(keys) - _TABLES[table]
        if unknown:
            name = sorted(unknown)[0]
            raise ConfigError(
                f"設定ファイルの {table}.{name} は未知のキーです",
                path=path,
                hint=f"[{table}] に指定できるキー: {', '.join(sorted(_TABLES[table]))}",
            )


def load_config(path: Path | str | None = None) -> Config:
    """設定ファイルと既定値をマージした設定を返す。

    ``path`` が ``None`` の場合はカレントから上位へ ``office2rag.toml`` を探索する。
    見つからなければ既定値のみの ``Config`` を返す。
    """
    if path is None:
        found = find_config_file()
        if found is None:
            return Config()
        config_path = found
    else:
        config_path = Path(path)
        if not config_path.is_file():
            raise ConfigError(
                f"設定ファイルが見つかりません: {config_path}",
                path=config_path,
                hint="パスの綴りと、ファイルが存在することを確認してください。",
            )

    try:
        with config_path.open("rb") as fp:
            data: dict[str, Any] = tomllib.load(fp)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(
            f"設定ファイルの構文が不正です: {exc}",
            path=config_path,
            hint="TOML の書式を確認してください。",
        ) from exc

    _check_unknown(data, config_path)

    convert_tbl: dict[str, Any] = data.get("convert", {})
    excel_tbl: dict[str, Any] = data.get("excel", {})
    log_tbl: dict[str, Any] = data.get("log", {})

    excel = ExcelOptions()
    if "modes" in excel_tbl:
        excel = replace(excel, modes=validate_enum(excel_tbl["modes"], ExcelModes, "excel.modes"))
    if "grid_separator" in excel_tbl:
        excel = replace(
            excel,
            grid_separator=validate_grid_separator(
                excel_tbl["grid_separator"], "excel.grid_separator"
            ),
        )
    if "table_regions" in excel_tbl:
        excel = replace(
            excel, table_regions=_require_bool(excel_tbl["table_regions"], "excel.table_regions")
        )
    if "max_table_regions" in excel_tbl:
        excel = replace(
            excel,
            max_table_regions=validate_int_range(
                excel_tbl["max_table_regions"], 1, 10_000, "excel.max_table_regions"
            ),
        )
    if "formulas" in excel_tbl:
        excel = replace(excel, formulas=_require_bool(excel_tbl["formulas"], "excel.formulas"))
    if "max_rows" in excel_tbl:
        excel = replace(
            excel,
            max_rows=validate_int_range(excel_tbl["max_rows"], 0, 1_048_576, "excel.max_rows"),
        )

    convert = ConvertOptions(excel=excel)
    if "images" in convert_tbl:
        convert = replace(
            convert, images=validate_enum(convert_tbl["images"], ImageMode, "convert.images")
        )
    if "shapes" in convert_tbl:
        convert = replace(convert, shapes=_require_bool(convert_tbl["shapes"], "convert.shapes"))
    if "shape_style" in convert_tbl:
        convert = replace(
            convert,
            shape_style=validate_enum(
                convert_tbl["shape_style"], ShapeStyle, "convert.shape_style"
            ),
        )
    # 動的なキー名で replace を呼ぶと型検査が通らないため、明示的に列挙する
    if "include_hidden" in convert_tbl:
        convert = replace(
            convert,
            include_hidden=_require_bool(convert_tbl["include_hidden"], "convert.include_hidden"),
        )
    if "notes" in convert_tbl:
        convert = replace(convert, notes=_require_bool(convert_tbl["notes"], "convert.notes"))
    if "headers_footers" in convert_tbl:
        convert = replace(
            convert,
            headers_footers=_require_bool(
                convert_tbl["headers_footers"], "convert.headers_footers"
            ),
        )
    if "comments" in convert_tbl:
        convert = replace(
            convert, comments=_require_bool(convert_tbl["comments"], "convert.comments")
        )
    if "front_matter" in convert_tbl:
        convert = replace(
            convert,
            front_matter=_require_bool(convert_tbl["front_matter"], "convert.front_matter"),
        )

    batch = BatchOptions(convert=convert)
    if "recursive" in convert_tbl:
        batch = replace(
            batch, recursive=_require_bool(convert_tbl["recursive"], "convert.recursive")
        )
    if "on_exists" in convert_tbl:
        batch = replace(
            batch, on_exists=validate_enum(convert_tbl["on_exists"], OnExists, "convert.on_exists")
        )
    if "jobs" in convert_tbl:
        batch = replace(batch, jobs=validate_int_range(convert_tbl["jobs"], 1, 64, "convert.jobs"))
    if "output" in convert_tbl:
        value = convert_tbl["output"]
        if not isinstance(value, str):
            raise ConfigError("convert.output にはパスの文字列を指定してください")
        batch = replace(batch, output_dir=Path(value))

    log = LogOptions()
    if "level" in log_tbl:
        level = log_tbl["level"]
        if level not in ("quiet", "info", "verbose"):
            raise ConfigError(
                f"log.level の値 '{level}' は不正です",
                hint="指定できる値: quiet, info, verbose",
            )
        log = replace(log, level=level)
    if "format" in log_tbl:
        fmt = log_tbl["format"]
        if fmt not in ("text", "json"):
            raise ConfigError(
                f"log.format の値 '{fmt}' は不正です", hint="指定できる値: text, json"
            )
        log = replace(log, format=fmt)
    if "file" in log_tbl:
        value = log_tbl["file"]
        if not isinstance(value, str):
            raise ConfigError("log.file にはパスの文字列を指定してください")
        log = replace(log, file=Path(value) if value else None)

    return Config(convert=convert, batch=batch, log=log)
