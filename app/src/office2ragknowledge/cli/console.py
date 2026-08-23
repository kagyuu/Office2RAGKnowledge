"""端末表示 (SCR-01〜07)。

**進捗とログは標準エラー、結果サマリと ``--stdout`` の Markdown は標準出力**
に出す (REQ-NF-013)。標準出力に他のものを混ぜると、パイプ処理が壊れる。
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from rich.console import Console
from rich.table import Table

from ..errors import Office2RagError, catalog_entry
from ..models import BatchResult, DocumentInfo

__all__ = [
    "err_console",
    "out_console",
    "print_error",
    "print_inspect",
    "print_inspect_json",
    "print_summary",
    "print_version",
]

# file を固定せず、書き込み時に現在の sys.stdout / sys.stderr を解決させる。
# import 時のストリームを掴むと、リダイレクトやテストの捕捉が効かなくなる。
out_console = Console(soft_wrap=True)
err_console = Console(stderr=True, soft_wrap=True)


def print_version(version: str) -> None:
    """SCR-02 バージョン画面。障害報告時の切り分けのため依存版も出す。"""
    import platform

    out_console.print(f"office2rag {version} (office2ragknowledge)")
    parts = [f"Python {platform.python_version()}"]
    for name, module in (
        ("lxml", "lxml.etree"),
        ("python-docx", "docx"),
        ("openpyxl", "openpyxl"),
        ("python-pptx", "pptx"),
    ):
        try:
            import importlib

            mod = importlib.import_module(module)
            ver = getattr(mod, "__version__", None) or getattr(mod, "LXML_VERSION", "?")
            if isinstance(ver, tuple):
                ver = ".".join(str(v) for v in ver)
            parts.append(f"{name} {ver}")
        except Exception:  # noqa: BLE001 - 版が取れなくても致命的でない
            parts.append(f"{name} ?")
    out_console.print(" / ".join(parts))


def print_error(exc: Office2RagError, *, verbose: bool) -> None:
    """SCR-06 エラー画面。スタックトレースは ``--verbose`` 時のみ。"""
    kind, hint = catalog_entry(exc.code)
    err_console.print(f"[bold red]エラー[/bold red]: {exc.message}")
    if exc.path is not None:
        err_console.print(f"  パス: {exc.path}")
    if exc.hint or hint:
        err_console.print(f"  対処: {exc.hint or hint}")
    if verbose:
        err_console.print_exception()


def print_summary(
    result: BatchResult,
    out_dir: Path | None,
    *,
    quiet: bool,
    to_stderr: bool = False,
) -> None:
    """SCR-04 変換結果サマリ画面。"""
    console = err_console if to_stderr else out_console
    success = len(result.succeeded)
    skipped = len(result.skipped)
    failed = len(result.failures)
    console.print(
        f"変換結果: 成功 {success} 件 / スキップ {skipped} 件 / 失敗 {failed} 件"
        f"  (所要 {result.elapsed_seconds:.1f} 秒)"
    )
    if quiet:
        return

    # 入力件数と出力ファイル数は一致しない (Excel の二重出力。REQ-F-094)
    excel_inputs = [p for p in result.succeeded if p.suffix.lower() in (".xlsx", ".xlsm")]
    note = ""
    if excel_inputs:
        note = f"  (Excel {len(excel_inputs)} 件から {_excel_outputs(result)} ファイルを生成)"
    console.print(f"出力ファイル: {len(result.written_files)} 件{note}")
    if out_dir is not None:
        console.print(f"出力先: {out_dir.resolve()}")

    if result.failures:
        console.print()
        console.print("失敗したファイル:")
        table = Table(show_lines=False)
        table.add_column("ファイル", overflow="ellipsis")
        table.add_column("種別")
        table.add_column("理由", overflow="ellipsis")
        for failure in result.failures:
            kind, _ = catalog_entry(failure.code)
            table.add_row(failure.path.name, kind, failure.message)
        console.print(table)

    if result.warnings:
        console.print()
        console.print(f"警告 ({len(result.warnings)} 件):")
        seen: set[tuple[str, str]] = set()
        for path, message in result.warnings:
            key = (path.name, message)
            if key in seen:
                continue
            seen.add(key)
            console.print(f"  - {path.name}: {message}")


def _excel_outputs(result: BatchResult) -> int:
    stems = {p.stem for p in result.succeeded if p.suffix.lower() in (".xlsx", ".xlsm")}
    return sum(1 for p in result.written_files if p.name.split(".")[0] in stems)


def print_inspect(infos: Sequence[DocumentInfo]) -> None:
    """SCR-05 構造確認画面。Excel のみ「領域」「数式」列に値が入る。"""
    table = Table()
    columns = (
        "ファイル",
        "形式",
        "サイズ",
        "保護",
        "単位",
        "表",
        "図形",
        "領域",
        "数式",
        "推定字",
    )
    for name in columns:
        table.add_column(name)
    for info in infos:
        is_excel = info.format is not None and str(info.format) == "xlsx"
        table.add_row(
            info.path.name,
            str(info.format) if info.format else "-",
            _human_size(info.size_bytes),
            "あり" if info.password_protected else "なし",
            str(info.unit_count) if info.status == "ok" else "-",
            str(info.table_count) if info.status == "ok" else "-",
            f"{info.shape_count} ({info.shape_with_text_count})" if info.status == "ok" else "-",
            str(info.table_region_count)
            if is_excel and info.table_region_count is not None
            else "-",
            str(info.formula_without_cache_count)
            if is_excel and info.formula_without_cache_count is not None
            else "-",
            f"{info.estimated_chars:,}" if info.status == "ok" else "-",
        )
    out_console.print(table)
    out_console.print()
    out_console.print("単位: Excel=シート数 / PowerPoint=スライド数 / Word=段落数")
    out_console.print("図形: 図形の総数 (うち括弧内はテキストを持つ図形の数)")
    out_console.print("領域: Excel で検出された表領域の数")
    out_console.print("数式: Excel で計算結果を持たない数式セルの数")


def print_inspect_json(infos: Sequence[DocumentInfo]) -> None:
    """``--json`` 指定時。RAG パイプラインが処理量を見積もる用途を想定する。"""
    payload = [
        {
            "path": str(info.path),
            "format": str(info.format) if info.format else None,
            "size_bytes": info.size_bytes,
            "status": info.status,
            "password_protected": info.password_protected,
            "unit_count": info.unit_count,
            "unit_label": info.unit_label,
            "table_count": info.table_count,
            "shape_count": info.shape_count,
            "shape_with_text_count": info.shape_with_text_count,
            "image_count": info.image_count,
            "estimated_chars": info.estimated_chars,
            "table_region_count": info.table_region_count,
            "formula_without_cache_count": info.formula_without_cache_count,
        }
        for info in infos
    ]
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _human_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.0f} KB"
    return f"{size} B"
