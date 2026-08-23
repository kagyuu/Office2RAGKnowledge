"""Excel の2モードで共通するレンダリング処理 (P003 §9.4)。

シート見出し・空シートの扱い・打ち切り注記・図形ブロックは両モードで共通である。
共通部分を二重に書くと、片方だけ修正されて出力が食い違う不具合が生じやすい。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import ConvertOptions, Document, Sheet
from .shapes import render_shape_blocks

__all__ = ["ExcelRendererBase", "normalize_blank_lines"]


def normalize_blank_lines(text: str) -> str:
    """連続する空行を1つに畳み、末尾を改行1つで終える。"""
    lines = text.split("\n")
    out: list[str] = []
    previous_blank = True  # 先頭の空行を落とすため True から始める
    for line in lines:
        blank = not line.strip()
        if blank and previous_blank:
            continue
        out.append(line.rstrip())
        previous_blank = blank
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out) + "\n" if out else ""


class ExcelRendererBase(ABC):
    """Excel レンダラの基底。本文の生成のみをサブクラスが実装する。"""

    def render(
        self, document: Document, options: ConvertOptions
    ) -> tuple[str, dict[str, int], tuple[str, ...]]:
        """(本文, stats, 警告) を返す。"""
        parts: list[str] = [f"# {document.title}", ""]
        warnings: list[str] = []
        sheets = [b for b in document.blocks if isinstance(b, Sheet)]
        shapes_with_text = 0
        images = 0

        for sheet in sheets:
            parts.append(f"## {sheet.name}")
            parts.append("")
            if sheet.is_empty:
                parts.append("(空のシートです)")
                parts.append("")
            else:
                body = self._render_sheet_body(sheet, options)
                if body:
                    parts.append(body)
                    parts.append("")
            if sheet.truncated_at is not None:
                parts.append(
                    f"> ※ このシートは {sheet.truncated_at} 行で打ち切りました "
                    f"(全 {sheet.total_rows} 行)"
                )
                parts.append("")
            shape_block = self._render_shapes(sheet, options)
            if shape_block:
                parts.append(shape_block)
                parts.append("")
            shapes_with_text += len(sheet.shapes)

        stats = self._build_stats(sheets, shapes_with_text, images)
        return normalize_blank_lines("\n".join(parts)), stats, tuple(warnings)

    @abstractmethod
    def _render_sheet_body(self, sheet: Sheet, options: ConvertOptions) -> str:
        """シート本文を生成する。モードごとに異なる唯一の部分。"""

    @abstractmethod
    def _build_stats(
        self, sheets: list[Sheet], shapes_with_text: int, images: int
    ) -> dict[str, int]:
        """front matter の ``stats`` を組み立てる。"""

    def _render_shapes(self, sheet: Sheet, options: ConvertOptions) -> str:
        """図形テキストブロックを生成する。

        **両モードとも、シートの章の末尾に同じ内容を出力する** (REQ-F-035)。
        この実装が基底クラスにあることで、両モードの出力が食い違わない。
        """
        if not sheet.shapes:
            return ""
        return render_shape_blocks(sheet.shapes, options.shape_style)
