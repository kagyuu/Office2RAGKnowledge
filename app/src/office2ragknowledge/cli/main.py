"""CLI のエントリポイント (SCR-01〜07)。

**エントリポイントは ``if __name__ == "__main__":`` で保護する。** Windows の
``spawn`` でワーカーが再帰的に CLI を起動することを防ぐため (ADR-005)。

標準出力・標準エラーは UTF-8 に再設定する。Windows の既定コードページ (cp932)
では日本語が化けるため (P003 §12B)。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn

from .. import __version__
from ..batch import convert_batch
from ..convert import convert_file
from ..errors import Office2RagError
from ..inspection import inspect_file
from ..logging_setup import setup_logging
from ..models import ExcelModes
from . import console as ui
from .options import build_config, resolve_targets

__all__ = ["app", "main"]

EXCEL_PANEL = "Excel オプション"

app = typer.Typer(
    name="office2rag",
    help="Office 文書 (Word/Excel/PowerPoint) を RAG 向け Markdown に変換します。",
    no_args_is_help=False,
    add_completion=False,
)


def _configure_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", newline="\n")
            except (ValueError, OSError):  # pragma: no cover - 環境依存
                pass


@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    version: Annotated[
        bool, typer.Option("--version", help="バージョンを表示して終了します")
    ] = False,
) -> None:
    """Office 文書を RAG 向け Markdown に変換します。"""
    _configure_streams()
    if version:
        ui.print_version(__version__)
        raise typer.Exit(0)
    if ctx.invoked_subcommand is None:
        ui.out_console.print(ctx.get_help())
        raise typer.Exit(2)


@app.command(help="Office 文書を Markdown に変換します")
def convert(  # noqa: PLR0913 - CLI のオプションを受け取る境界
    inputs: Annotated[list[Path], typer.Argument(help="入力ファイルまたはディレクトリ")],
    output: Annotated[
        Path | None, typer.Option("-o", "--output", help="出力先ディレクトリ")
    ] = None,
    recursive: Annotated[
        bool, typer.Option("-r", "--recursive", help="ディレクトリを再帰探索します")
    ] = False,
    on_exists: Annotated[
        str | None,
        typer.Option("--on-exists", help="出力先に同名ファイルがある場合 (既定: skip)"),
    ] = None,
    to_stdout: Annotated[
        bool, typer.Option("--stdout", help="標準出力に書き出します (対象1件のみ)")
    ] = False,
    excel_modes: Annotated[
        str | None,
        typer.Option(
            "--excel-modes",
            help="生成する Markdown の種類 both/table/grid (既定: both)",
            rich_help_panel=EXCEL_PANEL,
        ),
    ] = None,
    grid_separator: Annotated[
        str | None,
        typer.Option(
            "--grid-separator",
            help="方眼紙モードで同一行のセルを連結する際の区切り文字 (既定: なし)",
            rich_help_panel=EXCEL_PANEL,
        ),
    ] = None,
    table_regions: Annotated[
        bool | None,
        typer.Option(
            "--table-regions/--no-table-regions",
            help="1シート内の複数の表を分割して検出します (既定: 有効)",
            rich_help_panel=EXCEL_PANEL,
        ),
    ] = None,
    max_table_regions: Annotated[
        int | None,
        typer.Option(
            "--max-table-regions",
            help="これを超える表領域が検出されたら分割しません (既定: 100)",
            rich_help_panel=EXCEL_PANEL,
        ),
    ] = None,
    formulas: Annotated[
        bool | None,
        typer.Option(
            "--formulas/--no-formulas",
            help="数式を値と併記します (表計算モードのみ有効。既定: 無効)",
            rich_help_panel=EXCEL_PANEL,
        ),
    ] = None,
    max_rows: Annotated[
        int | None,
        typer.Option(
            "--max-rows",
            help="1シートあたりの出力上限行数 (既定: 10000、0 で無制限)",
            rich_help_panel=EXCEL_PANEL,
        ),
    ] = None,
    images: Annotated[
        str | None,
        typer.Option("--images", help="画像バイナリの出力 none/extract (既定: none)"),
    ] = None,
    shapes: Annotated[
        bool | None,
        typer.Option("--shapes/--no-shapes", help="図形内テキストを抽出します (既定: 有効)"),
    ] = None,
    shape_style: Annotated[
        str | None,
        typer.Option("--shape-style", help="図形ブロックの体裁 quote/heading/plain (既定: quote)"),
    ] = None,
    include_hidden: Annotated[
        bool | None,
        typer.Option(
            "--include-hidden/--no-include-hidden",
            help="非表示の要素も含めます (既定: 含めない)",
        ),
    ] = None,
    notes: Annotated[
        bool | None,
        typer.Option("--notes/--no-notes", help="発表者ノートを出力します (既定: 有効)"),
    ] = None,
    headers_footers: Annotated[
        bool | None,
        typer.Option(
            "--headers-footers/--no-headers-footers",
            help="Word のヘッダー・フッターを出力します (既定: 出力しない)",
        ),
    ] = None,
    comments: Annotated[
        bool | None,
        typer.Option(
            "--comments/--no-comments",
            help="Word のコメントを出力します (既定: 出力しない)",
        ),
    ] = None,
    front_matter: Annotated[
        bool | None,
        typer.Option(
            "--front-matter/--no-front-matter", help="front matter の出力 (既定: 出力する)"
        ),
    ] = None,
    jobs: Annotated[
        int | None, typer.Option("-j", "--jobs", help="並列ワーカー数 (既定: CPU コア数)")
    ] = None,
    config: Annotated[
        Path | None, typer.Option("-c", "--config", help="設定ファイル (TOML)")
    ] = None,
    quiet: Annotated[bool, typer.Option("-q", "--quiet", help="進捗表示を抑止します")] = False,
    verbose: Annotated[bool, typer.Option("-v", "--verbose", help="詳細ログを出力します")] = False,
    log_file: Annotated[
        Path | None, typer.Option("--log-file", help="ログのファイル出力先")
    ] = None,
    log_format: Annotated[
        str | None, typer.Option("--log-format", help="ログ形式 text/json (既定: text)")
    ] = None,
) -> None:
    """Office 文書を Markdown に変換します。"""
    _configure_streams()
    try:
        cfg, warnings = build_config(
            inputs=list(inputs),
            output=output,
            recursive=recursive,
            on_exists=on_exists,
            use_stdout=to_stdout,
            excel_modes=excel_modes,
            grid_separator=grid_separator,
            table_regions=table_regions,
            max_table_regions=max_table_regions,
            formulas=formulas,
            max_rows=max_rows,
            images=images,
            shapes=shapes,
            shape_style=shape_style,
            include_hidden=include_hidden,
            notes=notes,
            headers_footers=headers_footers,
            comments=comments,
            jobs=jobs,
            config_path=config,
            quiet=quiet,
            verbose=verbose,
            log_file=log_file,
            log_format=log_format,
            front_matter=front_matter,
        )
        setup_logging(cfg.log.level, cfg.log.format, cfg.log.file)
        targets, skipped = resolve_targets(
            list(inputs),
            recursive=cfg.batch.recursive,
            use_stdout=to_stdout,
            modes=cfg.convert.excel.modes,
        )
    except Office2RagError as exc:
        ui.print_error(exc, verbose=verbose)
        raise typer.Exit(2) from exc

    for warning in warnings:
        ui.err_console.print(f"[yellow]警告[/yellow]: {warning}")

    if to_stdout:
        _run_stdout(targets[0], cfg, verbose=verbose)
        return

    _run_batch(targets, cfg, skipped, quiet=quiet, verbose=verbose)


def _run_stdout(target: Path, cfg: object, *, verbose: bool) -> None:
    """SCR-07 標準出力モード。標準出力に Markdown 以外を混ぜない。"""
    from ..models import Config

    assert isinstance(cfg, Config)
    try:
        result = convert_file(target, cfg.convert)
    except Office2RagError as exc:
        ui.print_error(exc, verbose=verbose)
        raise typer.Exit(1) from exc
    # モードは検証済みで単一に絞られている
    sys.stdout.write(result.outputs[0].markdown)
    raise typer.Exit(0)


def _run_batch(
    targets: list[Path],
    cfg: object,
    skipped: list[tuple[Path, str]],
    *,
    quiet: bool,
    verbose: bool,
) -> None:
    """SCR-03 進捗 → SCR-04 サマリ。"""
    from ..models import Config

    assert isinstance(cfg, Config)
    progress: Progress | None = None
    task_id = None
    if not quiet and ui.err_console.is_terminal:
        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("{task.fields[name]}"),
            console=ui.err_console,
        )
        progress.start()
        task_id = progress.add_task("変換中...", total=len(targets), name="")

    def on_progress(done: int, total: int, name: str) -> None:
        if progress is not None and task_id is not None:
            progress.update(task_id, completed=done, name=name)
        elif not quiet:
            ui.err_console.print(f"[{done}/{total}] {name}")

    try:
        result = convert_batch(targets, cfg.batch, on_progress, skipped)
    except Office2RagError as exc:
        if progress is not None:
            progress.stop()
        ui.print_error(exc, verbose=verbose)
        raise typer.Exit(2) from exc
    finally:
        if progress is not None:
            progress.stop()

    ui.print_summary(result, cfg.batch.output_dir, quiet=quiet)
    raise typer.Exit(result.exit_code)


@app.command(help="変換せずに文書の構造を表示します")
def inspect(
    inputs: Annotated[list[Path], typer.Argument(help="入力ファイルまたはディレクトリ")],
    recursive: Annotated[
        bool, typer.Option("-r", "--recursive", help="ディレクトリを再帰探索します")
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="JSON で出力します")] = False,
) -> None:
    """入力文書の構造 (シート/スライド数・図形数・表領域数) を表示します。"""
    _configure_streams()
    try:
        targets, _ = resolve_targets(
            list(inputs), recursive=recursive, use_stdout=False, modes=ExcelModes.BOTH
        )
    except Office2RagError as exc:
        ui.print_error(exc, verbose=False)
        raise typer.Exit(2) from exc

    infos = []
    for target in targets:
        try:
            infos.append(inspect_file(target))
        except OSError as exc:  # 読めないファイルは一覧を止めない
            ui.err_console.print(f"[yellow]警告[/yellow]: {target} を読めません: {exc}")

    if as_json:
        ui.print_inspect_json(infos)
    else:
        ui.print_inspect(infos)
    raise typer.Exit(0)


def main() -> None:
    """コンソールスクリプトのエントリポイント。"""
    app()


if __name__ == "__main__":
    # Windows の spawn でワーカーが CLI を再帰起動しないよう保護する
    main()
