"""CLI オプションの検証 (P002 §4 の V-01〜V-52)。

**検証はすべて変換処理の開始前に行う。** 違反があれば1件も変換せずに終了する
(部分的に処理してから落ちることを避ける)。

**先に検出した違反で終了する** (複数違反をまとめて報告しない)。検証段階が進む
ほど前段の成功を前提とするため、まとめて報告すると誤解を招く出力になる。

**既定値は ``load_config`` が返す ``Config`` が持ち、CLI 層は持たない。**
CLI のオプションはすべて既定 ``None`` であり、``None`` でないものだけが設定
ファイルの値を上書きする。これにより優先順位「コマンドライン引数 > 設定ファイル
> 既定値」(REQ-F-098) が成立する (P003 §8.5)。
"""

from __future__ import annotations

from dataclasses import replace
from enum import Enum
from pathlib import Path
from typing import Literal, TypeVar

from ..config import load_config, validate_grid_separator, validate_int_range
from ..detect import LEGACY_EXTENSIONS, SUPPORTED_EXTENSIONS
from ..errors import ConfigError, Office2RagError, UnsupportedFormatError
from ..models import (
    Config,
    DocumentFormat,
    ExcelModes,
    ImageMode,
    LogOptions,
    OnExists,
    ShapeStyle,
)

__all__ = ["ValidationError", "build_config", "resolve_targets"]

_EnumT = TypeVar("_EnumT", bound=Enum)


class ValidationError(Office2RagError):
    """CLI の入力検証に失敗した (実行前異常)。"""

    default_code = "E-013"


def _fail(code: str, message: str, *, path: Path | None = None) -> ValidationError:
    return ValidationError(message, code=code, path=path)


def _enum_or_fail(value: str, enum_cls: type[_EnumT], option: str) -> _EnumT:
    try:
        return enum_cls(value)
    except ValueError as exc:
        choices = ", ".join(str(m.value) for m in enum_cls)
        raise _fail(
            "E-013", f"{option} の値 '{value}' は不正です (指定できる値: {choices})"
        ) from exc


def build_config(  # noqa: PLR0913 - CLI のオプションを1箇所で検証する
    *,
    inputs: list[Path],
    output: Path | None,
    recursive: bool,
    on_exists: str | None,
    use_stdout: bool,
    excel_modes: str | None,
    grid_separator: str | None,
    table_regions: bool | None,
    max_table_regions: int | None,
    formulas: bool | None,
    max_rows: int | None,
    images: str | None,
    shapes: bool | None,
    shape_style: str | None,
    include_hidden: bool | None,
    notes: bool | None,
    headers_footers: bool | None,
    comments: bool | None,
    jobs: int | None,
    config_path: Path | None,
    quiet: bool,
    verbose: bool,
    log_file: Path | None,
    log_format: str | None,
    front_matter: bool | None,
) -> tuple[Config, list[str]]:
    """CLI 引数と設定ファイルから ``Config`` を組み立てる。

    **``None`` は「利用者が指定しなかった」ことを意味する。** その項目は設定
    ファイルの値 (無ければ既定値) がそのまま残る。

    Returns:
        (設定, 警告の並び)

    Raises:
        ValidationError: 検証に失敗した場合
    """
    warnings: list[str] = []

    # ---- (1) 型・列挙値・範囲 ----
    modes = _enum_or_fail(excel_modes, ExcelModes, "--excel-modes") if excel_modes else None
    image_mode = _enum_or_fail(images, ImageMode, "--images") if images else None
    style = _enum_or_fail(shape_style, ShapeStyle, "--shape-style") if shape_style else None
    exists = _enum_or_fail(on_exists, OnExists, "--on-exists") if on_exists else None

    log_fmt: Literal["text", "json"] | None = None
    if log_format is not None:
        if log_format not in ("text", "json"):
            raise _fail("E-013", f"--log-format の値 '{log_format}' は不正です")
        log_fmt = "json" if log_format == "json" else "text"

    if grid_separator is not None:
        try:
            validate_grid_separator(grid_separator)
        except ConfigError as exc:
            raise _fail("E-018", exc.message) from exc
    if max_table_regions is not None:
        try:
            validate_int_range(max_table_regions, 1, 10_000, "--max-table-regions")
        except ConfigError as exc:
            raise _fail("E-019", exc.message) from exc
    if max_rows is not None:
        try:
            validate_int_range(max_rows, 0, 1_048_576, "--max-rows")
        except ConfigError as exc:
            raise _fail("E-015", exc.message) from exc
    if jobs is not None:
        try:
            validate_int_range(jobs, 1, 64, "--jobs")
        except ConfigError as exc:
            raise _fail("E-016", exc.message) from exc

    # ---- (2) 排他指定 ----
    if quiet and verbose:
        raise _fail("E-012", "--quiet と --verbose は同時に指定できません")
    if use_stdout and output is not None:
        raise _fail("E-012", "--stdout と --output は同時に指定できません")

    # ---- 設定ファイルを読み、明示指定されたものだけを上書きする ----
    try:
        base = load_config(config_path)
    except ConfigError as exc:
        raise _fail("E-006", exc.message, path=exc.path) from exc

    excel = base.convert.excel
    if modes is not None:
        excel = replace(excel, modes=modes)
    if grid_separator is not None:
        excel = replace(excel, grid_separator=grid_separator)
    if table_regions is not None:
        excel = replace(excel, table_regions=table_regions)
    if max_table_regions is not None:
        excel = replace(excel, max_table_regions=max_table_regions)
    if formulas is not None:
        excel = replace(excel, formulas=formulas)
    if max_rows is not None:
        excel = replace(excel, max_rows=max_rows)

    convert = replace(base.convert, excel=excel)
    if image_mode is not None:
        convert = replace(convert, images=image_mode)
    if style is not None:
        convert = replace(convert, shape_style=style)
    if shapes is not None:
        convert = replace(convert, shapes=shapes)
    if notes is not None:
        convert = replace(convert, notes=notes)
    if include_hidden is not None:
        convert = replace(convert, include_hidden=include_hidden)
    if headers_footers is not None:
        convert = replace(convert, headers_footers=headers_footers)
    if comments is not None:
        convert = replace(convert, comments=comments)
    if front_matter is not None:
        convert = replace(convert, front_matter=front_matter)

    batch = replace(base.batch, convert=convert)
    if recursive:
        # -r は「再帰する」ことだけを意味する慣用のフラグであり否定形を持たない。
        # 未指定 (False) は設定ファイルの値を尊重する。
        batch = replace(batch, recursive=True)
    if exists is not None:
        batch = replace(batch, on_exists=exists)
    if jobs is not None:
        batch = replace(batch, jobs=jobs)
    if output is not None:
        batch = replace(batch, output_dir=output)

    level: Literal["quiet", "info", "verbose"] = base.log.level
    if quiet:
        level = "quiet"
    elif verbose:
        level = "verbose"
    log = LogOptions(
        level=level,
        format=log_fmt if log_fmt is not None else base.log.format,
        file=log_file if log_file is not None else base.log.file,
    )

    # ---- 意味を持たない組み合わせは警告のみ (エラーにしない) ----
    if excel.modes is ExcelModes.GRID and excel.formulas:
        warnings.append("--formulas は方眼紙モードでは無視されます")
    if recursive and not any(p.is_dir() for p in inputs):
        warnings.append("-r が指定されましたが、ディレクトリ入力がないため無視しました")

    return Config(convert=convert, batch=batch, log=log), warnings


def resolve_targets(
    inputs: list[Path], *, recursive: bool, use_stdout: bool, modes: ExcelModes
) -> tuple[list[Path], list[tuple[Path, str]]]:
    """入力パスを検証して対象ファイルを確定する。

    Returns:
        (変換対象のファイル, スキップしたファイルと理由)

    **スキップ情報も返す。** ``convert_batch`` へ引き継いで結果サマリに計上する
    ためである。ここで捨てると、利用者が対象外のファイルの存在に気づけない
    (REQ-F-094)。

    Raises:
        ValidationError: 検証に失敗した場合
    """
    # ---- (3) パスの存在・権限 ----
    if not inputs:
        raise _fail("E-010", "入力パスを指定してください")
    for path in inputs:
        if not path.exists():
            raise _fail("E-001", "入力パスが見つかりません", path=path)
        if path.is_file() and not _readable(path):
            raise _fail("E-003", "入力ファイルを読み取れません", path=path)

    # ---- (4) 入力探索と対象件数 ----
    from ..batch import scan_inputs

    targets, skipped = scan_inputs(inputs, recursive=recursive)
    if not targets:
        legacy = [p for p in inputs if p.suffix.lower() in LEGACY_EXTENSIONS]
        if legacy:
            raise UnsupportedFormatError(f"{legacy[0].suffix} は非対応の形式です", path=legacy[0])
        raise _fail("E-011", "変換対象のファイルが見つかりませんでした")

    # ---- (5) --stdout の件数条件と Excel モード条件 ----
    if use_stdout:
        if len(targets) != 1:
            raise _fail(
                "E-014",
                f"--stdout は変換対象が1件のときのみ使用できます (対象: {len(targets)} 件)",
            )
        only = targets[0]
        if (
            SUPPORTED_EXTENSIONS.get(only.suffix.lower()) is DocumentFormat.XLSX
            and modes is ExcelModes.BOTH
        ):
            raise _fail(
                "E-017",
                "Excel を --stdout で出力する場合は --excel-modes で単一のモードを指定してください",
                path=only,
            )
    return targets, skipped


def _readable(path: Path) -> bool:
    try:
        with path.open("rb"):
            return True
    except OSError:
        return False
