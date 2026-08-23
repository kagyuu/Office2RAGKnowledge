"""中間表現から Markdown を生成する層。``models/`` のみに依存する。

**Excel は1つの中間表現から2つのレンダラが動く** (要求③)。入力の解析は
``parsers/`` で1回だけ行われ、この層はファイルに触れない (REQ-F-068)。
"""

from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from ..models import (
    ConvertOptions,
    Document,
    DocumentFormat,
    ExcelModes,
    MarkdownOutput,
    OutputMode,
)
from .frontmatter import render_front_matter

__all__ = ["render_document"]

#: 出力モード → ファイル名サフィックス。
#: **モードの指定によらず固定する** (P002 §5.2、§1 論点6)。単一モード指定時に
#: 無印 ``.md`` へ変えると、同じブックを異なる設定で変換したときに出力名が揺れ、
#: RAG 側が「同じ文書の再取り込みか、別文書か」を判定できなくなる。
_SUFFIX: dict[OutputMode, str] = {
    OutputMode.TABLE: ".table.md",
    OutputMode.GRID: ".grid.md",
}


def render_document(document: Document, options: ConvertOptions) -> tuple[MarkdownOutput, ...]:
    """中間表現から1〜2件の Markdown 出力を生成する。

    Excel かつ ``modes=BOTH`` のとき2件 (順序は table, grid で固定)、
    それ以外は1件を返す。
    """
    if document.format is DocumentFormat.XLSX:
        return _render_excel(document, options)
    return (_render_single(document, options, None),)


def _render_excel(document: Document, options: ConvertOptions) -> tuple[MarkdownOutput, ...]:
    modes: list[OutputMode] = []
    if options.excel.modes in (ExcelModes.BOTH, ExcelModes.TABLE):
        modes.append(OutputMode.TABLE)
    if options.excel.modes in (ExcelModes.BOTH, ExcelModes.GRID):
        modes.append(OutputMode.GRID)

    outputs: list[MarkdownOutput] = []
    for mode in modes:
        # 同じ Document を2つのレンダラに渡す。Document を複製しない。
        outputs.append(_render_single(document, options, mode))
    return tuple(outputs)


def _render_single(
    document: Document, options: ConvertOptions, mode: OutputMode | None
) -> MarkdownOutput:
    renderer = _make_renderer(document.format, mode)
    body, stats, warnings = renderer.render(document, options)

    all_warnings = tuple(document.warnings) + tuple(warnings)
    if mode is not OutputMode.TABLE:
        # 表領域の上限超過は表計算モードにのみ関係する警告である (P002 §9.3)
        all_warnings = tuple(w for w in all_warnings if "表領域が" not in w)

    meta = replace(document.meta, stats=stats, warnings=all_warnings)
    text = body
    if options.front_matter:
        text = render_front_matter(meta, mode) + "\n" + body
    return MarkdownOutput(
        markdown=text,
        meta=meta,
        mode=mode,
        filename_suffix=_SUFFIX.get(mode, ".md") if mode is not None else ".md",
        warnings=all_warnings,
    )


class Renderer(Protocol):
    """レンダラのプロトコル。(本文, stats, 警告) を返す。"""

    def render(
        self, document: Document, options: ConvertOptions
    ) -> tuple[str, dict[str, int], tuple[str, ...]]: ...


def _make_renderer(fmt: DocumentFormat, mode: OutputMode | None) -> Renderer:
    if fmt is DocumentFormat.XLSX:
        if mode is OutputMode.GRID:
            from .excel_grid import ExcelGridRenderer

            return ExcelGridRenderer()
        from .excel_table import ExcelTableRenderer

        return ExcelTableRenderer()
    from .markdown import MarkdownRenderer

    return MarkdownRenderer()
