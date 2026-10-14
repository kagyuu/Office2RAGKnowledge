"""Word / PowerPoint の Markdown レンダラ (P002 §5.9, §5.10)。

``blocks`` の順序をそのまま出力順とする (INV-04)。例外は ``Footnote`` と
``anchor is None`` の ``ShapeText`` のみで、これらは文書末尾へ移送する。
"""

from __future__ import annotations

from ..models import (
    Block,
    ConvertOptions,
    Document,
    DocumentFormat,
    Footnote,
    Heading,
    Image,
    ImageMode,
    InlineRun,
    ListBlock,
    Paragraph,
    ShapeText,
    SlideBreak,
    Table,
)
from .escape import escape_cell, escape_line
from .excel_base import normalize_blank_lines
from .shapes import render_shape_blocks

__all__ = ["MarkdownRenderer", "render_runs"]


def render_runs(runs: tuple[InlineRun, ...]) -> str:
    """run の並びを Markdown の装飾付きテキストにする。

    テキスト自体は ``escape_line`` の対象だが、装飾記号はエスケープしない。
    """
    parts: list[str] = []
    for run in runs:
        text = escape_line(run.text)
        if run.code:
            text = f"`{text}`"
        if run.bold:
            text = f"**{text}**"
        if run.italic:
            text = f"*{text}*"
        if run.strike:
            text = f"~~{text}~~"
        if run.link_url:
            text = f"[{text}]({run.link_url})"
        parts.append(text)
    return "".join(parts)


class MarkdownRenderer:
    """Word / PowerPoint 共通のレンダラ。"""

    def render(
        self, document: Document, options: ConvertOptions
    ) -> tuple[str, dict[str, int], tuple[str, ...]]:
        parts: list[str] = [f"# {document.title}", ""]
        footnotes: list[Footnote] = []
        floating: list[ShapeText] = []
        stem = document.meta.source_file.rsplit(".", 1)[0]

        counts = {"headings": 0, "paragraphs": 0, "tables": 0, "shapes": 0, "images": 0}
        slides = 0
        pending_notes: tuple[str, ...] = ()

        for block in document.blocks:
            match block:
                case Footnote():
                    footnotes.append(block)
                case ShapeText() if block.anchor is None and document.format is DocumentFormat.DOCX:
                    floating.append(block)
                case _:
                    rendered = self._render_block(block, options, stem, counts)
                    if isinstance(block, SlideBreak):
                        slides += 1
                        if pending_notes:
                            parts.extend(pending_notes)
                            parts.append("")
                        pending_notes = self._render_notes(block)
                    if rendered:
                        parts.append(rendered)
                        parts.append("")

        if pending_notes:
            parts.extend(pending_notes)
            parts.append("")

        if footnotes:
            parts.append("## 脚注")
            parts.append("")
            for note in footnotes:
                parts.append(f"[^{note.marker}]: {render_runs(note.runs)}")
            parts.append("")

        if floating:
            parts.append("## 図形テキスト (位置不明)")
            parts.append("")
            parts.append(render_shape_blocks(tuple(floating), options.shape_style))
            parts.append("")
            counts["shapes"] += len(floating)

        stats = self._build_stats(document, counts, slides)
        return normalize_blank_lines("\n".join(parts)), stats, ()

    def _render_block(
        self,
        block: Block,
        options: ConvertOptions,
        stem: str,
        counts: dict[str, int],
    ) -> str:
        match block:
            case Heading(level=level, runs=runs):
                counts["headings"] += 1
                return f"{'#' * min(max(level, 1), 6)} {render_runs(runs)}"
            case Paragraph(runs=runs):
                counts["paragraphs"] += 1
                return render_runs(runs)
            case ListBlock(items=items):
                lines = []
                for item in items:
                    indent = "  " * item.level
                    marker = "1." if item.ordered else "-"
                    lines.append(f"{indent}{marker} {render_runs(item.runs)}")
                return "\n".join(lines)
            case Table():
                counts["tables"] += 1
                return self._render_table(block)
            case ShapeText():
                counts["shapes"] += 1
                return render_shape_blocks((block,), options.shape_style)
            case Image():
                counts["images"] += 1
                return self._render_image(block, options, stem)
            case SlideBreak(slide_number=number, slide_title=title):
                if title:
                    return f"## スライド {number}: {title}"
                return f"## スライド {number}"
            case _:
                return ""

    @staticmethod
    def _render_table(table: Table) -> str:
        lines: list[str] = []
        for i, row in enumerate(table.rows):
            values = [escape_cell(render_runs(cell.runs)) for cell in row.cells]
            lines.append("| " + " | ".join(values) + " |")
            if i == 0:
                lines.append("| " + " | ".join("---" for _ in row.cells) + " |")
        return "\n".join(lines)

    @staticmethod
    def _render_image(image: Image, options: ConvertOptions, stem: str) -> str:
        alt = image.alt_text or f"図{image.index}"
        # media_ref が空の画像はバイナリを持たない (PDF。P002 §5.11)
        if options.images is ImageMode.EXTRACT and image.media_ref:
            target = f"./{stem}_assets/{image.index:04d}.{image.extension}"
        else:
            target = "画像は出力されていません"
        return f"![{alt}]({target})"

    @staticmethod
    def _render_notes(block: SlideBreak) -> tuple[str, ...]:
        if not block.notes:
            return ()
        lines = ["### ノート", ""]
        lines.extend(render_runs(p.runs) for p in block.notes)
        return tuple(lines)

    @staticmethod
    def _build_stats(document: Document, counts: dict[str, int], slides: int) -> dict[str, int]:
        if document.format is DocumentFormat.PDF:
            # キー順は P002 §5.3 に固定する。ページ数と補正の件数はパーサが渡す (※CR-001・CR-002)
            parsed = document.meta.stats
            return {
                "pages": int(parsed.get("pages", 0)),
                "paragraphs": counts["paragraphs"],
                "headings": counts["headings"],
                "tables": counts["tables"],
                "shapes_with_text": counts["shapes"],
                "images": counts["images"],
                "headers_footers_removed": int(parsed.get("headers_footers_removed", 0)),
                "multi_column_pages": int(parsed.get("multi_column_pages", 0)),
            }
        if document.format is DocumentFormat.PPTX:
            return {
                "slides": slides,
                "tables": counts["tables"],
                "shapes_with_text": counts["shapes"],
                "images": counts["images"],
            }
        return {
            "paragraphs": counts["paragraphs"],
            "headings": counts["headings"],
            "tables": counts["tables"],
            "shapes_with_text": counts["shapes"],
            "images": counts["images"],
        }
