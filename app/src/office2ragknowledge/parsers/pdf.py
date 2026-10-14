"""PDF パーサ (P003 §7A。※CR-001・CR-002)。

タグ付き PDF は構造木を見出し・リスト・表・段落・図に写す (構造ツリーの順序が
読み順。REQ-F-115・REQ-F-127)。タグなし PDF は構造を推定せず、レイアウトから
段落と図を組み立てる (ADR-013・ADR-014)。

PDF は ZIP ではないため、``Parser`` プロトコル (``SafeZipReader`` を受け取る) とは
別の入口 ``parse(data, ...)`` を持つ (P003 §8.1)。
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator, Sequence
from datetime import datetime
from pathlib import Path

from ..models import (
    Block,
    ConvertOptions,
    Document,
    DocumentFormat,
    DocumentMeta,
    Heading,
    Image,
    ImageMode,
    InlineRun,
    ListBlock,
    ListItem,
    Paragraph,
    ShapeParagraph,
    ShapeText,
    Table,
    TableCell,
    TableRow,
    make_run,
)
from ..pdf.backend import open_pdf
from ..pdf.layout import layout_document
from ..pdf.model import PdfChar, PdfSource
from ..pdf.structure import StructNode, TextRun, build_tree, classify
from ..pdf.text import group_lines, line_text, text_of

__all__ = ["PdfParser"]

logger = logging.getLogger(__name__)

_HEADING_LEVELS = {f"H{n}": n for n in range(1, 7)} | {"Title": 1}
_LIST_TAGS = frozenset({"L", "TOC"})
_ITEM_TAGS = frozenset({"LI", "TOCI"})
_PARAGRAPH_TAGS = frozenset({"P", "Caption", "Note", "Code", "Quote", "BibEntry", "FENote"})
_INLINE_TAGS = frozenset(
    {"Span", "Link", "Em", "Strong", "Reference", "Lbl", "Annot", "Sub",
     "Ruby", "RB", "RT", "RP", "Warichu", "WT", "WP"}
)  # fmt: skip
_TABLE_SECTIONS = frozenset({"THead", "TBody", "TFoot"})
_CELL_TAGS = frozenset({"TH", "TD"})
_FIGURE_KINDS = {"Figure": "図", "Formula": "数式"}
_ORDERED_NUMBERING = frozenset({"Decimal", "UpperRoman", "LowerRoman", "UpperAlpha", "LowerAlpha"})
_UNORDERED_NUMBERING = frozenset({"None", "Disc", "Circle", "Square"})
_ORDERED_LABEL = re.compile(r"^\(?([0-9]+|[a-zA-Z]|[ivxlcdmIVXLCDM]+)[.)]")


def _runs(text: str) -> tuple[InlineRun, ...]:
    run = make_run(text)
    return (run,) if run is not None else ()


def _iter_chars(node: StructNode) -> Iterator[PdfChar]:
    """要素の内側の文字を出現順に返す (Artifact の要素は除く)。"""
    if node.tag == "Artifact":
        return
    for item in node.items:
        if isinstance(item, TextRun):
            yield from item.chars
        else:
            yield from _iter_chars(item)


def _node_text(node: StructNode, *, exclude: frozenset[str] = frozenset()) -> str:
    chars: list[PdfChar] = []

    def collect(n: StructNode) -> None:
        for item in n.items:
            if isinstance(item, TextRun):
                chars.extend(item.chars)
            elif item.tag not in exclude and item.tag != "Artifact":
                collect(item)

    collect(node)
    return text_of(chars)


def _page_ranges(numbers: Sequence[int]) -> str:
    """``[3, 5, 6, 7]`` → ``"3, 5-7"``。"""
    parts: list[str] = []
    start = prev = numbers[0]
    for n in numbers[1:]:
        if n == prev + 1:
            prev = n
            continue
        parts.append(f"{start}-{prev}" if prev > start else str(start))
        start = prev = n
    parts.append(f"{start}-{prev}" if prev > start else str(start))
    return ", ".join(parts)


class _TaggedBuilder:
    """構造木を中間表現のブロックに写す (P003 §7A.4)。"""

    def __init__(self, options: ConvertOptions) -> None:
        self.options = options
        self.blocks: list[Block] = []
        self.image_index = 0

    def build(self, roots: Sequence[StructNode]) -> list[Block]:
        for root in roots:
            self._node(root, sect_depth=0)
        return self.blocks

    # --- 振り分け ---------------------------------------------------------

    def _node(self, node: StructNode, sect_depth: int) -> None:
        tag = node.tag
        if tag == "Artifact":
            return
        if tag in _HEADING_LEVELS or tag == "H":
            level = _HEADING_LEVELS.get(tag, min(sect_depth + 1, 6))
            text = _node_text(node)
            if text:
                self.blocks.append(Heading(level=level, runs=_runs(text)))
        elif tag in _LIST_TAGS:
            items: list[ListItem] = []
            self._list_items(node, 0, items)
            if items:
                self.blocks.append(ListBlock(items=tuple(items)))
        elif tag == "Table":
            self._table(node)
        elif tag in _FIGURE_KINDS:
            self._figure(node)
        elif tag in _PARAGRAPH_TAGS or tag in _INLINE_TAGS:
            self._paragraph(_node_text(node))
        elif self._is_leaf(node):
            self._paragraph(_node_text(node))
        else:
            depth = sect_depth + 1 if tag == "Sect" else sect_depth
            self._container(node, depth)

    @staticmethod
    def _is_leaf(node: StructNode) -> bool:
        """子要素がインラインだけ (またはテキストだけ) の要素か。"""
        return all(isinstance(i, TextRun) or i.tag in _INLINE_TAGS for i in node.items)

    def _container(self, node: StructNode, sect_depth: int) -> None:
        """まとまり。直接のテキストとインライン子要素の連続は1つの段落にする。"""
        pending: list[PdfChar] = []
        for item in node.items:
            if isinstance(item, TextRun):
                pending.extend(item.chars)
            elif item.tag in _INLINE_TAGS:
                pending.extend(_iter_chars(item))
            else:
                self._paragraph(text_of(pending))
                pending = []
                self._node(item, sect_depth)
        self._paragraph(text_of(pending))

    def _paragraph(self, text: str) -> None:
        if text:
            self.blocks.append(Paragraph(runs=_runs(text)))

    # --- リスト (P003 §7A.4, §7A.4.1) ---------------------------------------

    @staticmethod
    def _is_ordered(node: StructNode) -> bool:
        numbering = node.info.list_numbering
        if numbering in _ORDERED_NUMBERING:
            return True
        if numbering in _UNORDERED_NUMBERING:
            return False
        for item in node.items:
            if isinstance(item, StructNode) and item.tag in _ITEM_TAGS:
                for child in item.items:
                    if isinstance(child, StructNode) and child.tag == "Lbl":
                        return bool(_ORDERED_LABEL.match(_node_text(child)))
                return False
        return False

    def _list_items(self, node: StructNode, level: int, out: list[ListItem]) -> None:
        ordered = self._is_ordered(node)
        for item in node.items:
            if isinstance(item, TextRun):
                text = text_of(item.chars)
                if text:
                    out.append(ListItem(runs=_runs(text), level=level, ordered=ordered))
            elif item.tag in _LIST_TAGS:
                self._list_items(item, level + 1, out)
            elif item.tag in _ITEM_TAGS:
                self._list_item(item, level, ordered, out)

    def _list_item(self, item: StructNode, level: int, ordered: bool, out: list[ListItem]) -> None:
        excluded = _LIST_TAGS | {"Lbl"}
        body = next((c for c in item.items if isinstance(c, StructNode) and c.tag == "LBody"), None)
        text = _node_text(body if body is not None else item, exclude=excluded)
        if text:
            out.append(ListItem(runs=_runs(text), level=min(level, 8), ordered=ordered))
        for nested in self._nested_lists(item):
            self._list_items(nested, level + 1, out)

    @staticmethod
    def _nested_lists(node: StructNode) -> Iterator[StructNode]:
        """項目の内側にある (さらに内側のリストに含まれない) リストを返す。"""
        for child in node.items:
            if isinstance(child, StructNode):
                if child.tag in _LIST_TAGS:
                    yield child
                else:
                    yield from _TaggedBuilder._nested_lists(child)

    # --- 表 ---------------------------------------------------------------

    @staticmethod
    def _rows(node: StructNode, in_head: bool = False) -> Iterator[tuple[StructNode, bool]]:
        for child in node.items:
            if not isinstance(child, StructNode) or child.tag == "Table":
                continue
            if child.tag == "TR":
                yield child, in_head
            elif child.tag in _TABLE_SECTIONS:
                yield from _TaggedBuilder._rows(child, in_head or child.tag == "THead")

    def _table(self, node: StructNode) -> None:
        rows = list(self._rows(node))
        if not rows:
            self._paragraph(_node_text(node))
            return
        grid: dict[tuple[int, int], tuple[str, bool]] = {}
        header_flags: list[bool] = []
        for r, (tr, in_head) in enumerate(rows):
            cells = [c for c in tr.items if isinstance(c, StructNode) and c.tag in _CELL_TAGS]
            header_flags.append(in_head or (bool(cells) and all(c.tag == "TH" for c in cells)))
            col = 0
            for cell in cells:
                while (r, col) in grid:
                    col += 1
                text = _node_text(cell)
                for dr in range(cell.info.row_span):
                    for dc in range(cell.info.col_span):
                        if r + dr < len(rows):
                            grid.setdefault((r + dr, col + dc), (text, (dr, dc) != (0, 0)))
                col += cell.info.col_span
        n_cols = max((c for _, c in grid), default=-1) + 1
        if n_cols == 0:
            return
        table_rows = []
        for r in range(len(rows)):
            cells_out = []
            for c in range(n_cols):
                text, from_merge = grid.get((r, c), ("", False))
                cells_out.append(TableCell(runs=_runs(text), from_merge=from_merge))
            table_rows.append(
                TableRow(cells=tuple(cells_out), is_header=r == 0 and header_flags[0])
            )
        self.blocks.append(Table(rows=tuple(table_rows), has_header=header_flags[0]))

    # --- 図 ---------------------------------------------------------------

    def _figure(self, node: StructNode) -> None:
        if node.info.alt:
            self.image_index += 1
            self.blocks.append(
                Image(alt_text=node.info.alt, media_ref="", extension="png", index=self.image_index)
            )
        if not self.options.shapes:
            return
        lines = [line_text(line) for line in group_lines(list(_iter_chars(node)))]
        paragraphs = tuple(ShapeParagraph(runs=_runs(t)) for t in lines if t)
        if paragraphs:
            self.blocks.append(ShapeText(shape_kind=_FIGURE_KINDS[node.tag], paragraphs=paragraphs))


class PdfParser:
    """PDF の中間表現を作る。"""

    def parse(
        self, data: bytes, filename: str, options: ConvertOptions, converted_at: datetime
    ) -> Document:
        """PDF を解析して ``Document`` を返す。

        Raises:
            PasswordProtectedError / CorruptedFileError / FileTooLargeError
        """
        source = open_pdf(data)
        tagged, fell_back = classify(source)
        warnings: list[str] = []
        if fell_back:
            warnings.append(
                "論理構造 (タグ) が本文の一部しか覆っていないため、タグなし PDF として変換しました"
            )

        blocks: list[Block]
        if tagged:
            blocks = _TaggedBuilder(options).build(build_tree(source))
            removed = _outside_line_count(source)
            multi_column = 0
        else:
            result = layout_document(
                source, shapes=options.shapes, headers_footers=options.headers_footers
            )
            blocks = []
            for block in result.blocks:
                if block.kind == "figure":
                    paragraphs = tuple(ShapeParagraph(runs=_runs(t)) for t in block.lines if t)
                    if paragraphs:
                        blocks.append(ShapeText(shape_kind="図", paragraphs=paragraphs))
                elif block.text:
                    blocks.append(Paragraph(runs=_runs(block.text)))
            removed = result.headers_footers_removed
            multi_column = result.multi_column_pages

        warnings.extend(_text_warnings(source))
        if source.copy_restricted:
            warnings.append(
                "この PDF にはテキストのコピーを制限する権限設定がありますが、変換しました"
            )
        if options.images is ImageMode.EXTRACT and any(isinstance(b, Image) for b in blocks):
            warnings.append("PDF の画像は書き出しません (代替テキストのみを出力しました)")

        title = source.metadata.title or Path(filename).stem
        meta = DocumentMeta(
            source_file=Path(filename).name,
            source_path=filename,
            source_format=DocumentFormat.PDF,
            source_size_bytes=len(data),
            source_sha256="",
            converter="office2ragknowledge",
            converted_at=converted_at,
            title=title,
            author=source.metadata.author,
            created_at=source.metadata.created_at,
            modified_at=source.metadata.modified_at,
            stats={
                "pages": len(source.pages),
                "headers_footers_removed": removed,
                "multi_column_pages": multi_column,
            },
            warnings=tuple(warnings),
            pdf_structure="tagged" if tagged else "untagged",
        )
        logger.debug(
            "PDF を解析しました (ページ数: %d, ブロック数: %d, 警告数: %d)",
            len(source.pages),
            len(blocks),
            len(warnings),
        )
        return Document(
            format=DocumentFormat.PDF,
            title=title,
            meta=meta,
            blocks=tuple(blocks),
            warnings=tuple(warnings),
        )


def _outside_line_count(source: PdfSource) -> int:
    """構造の外の文字 (Artifact 等) の行数 (P003 §7A.4)。"""
    count = 0
    for page in source.pages:
        outside = [c for c in page.chars if c.path is None and not c.text.isspace()]
        count += len(group_lines(outside))
    return count


def _text_warnings(source: PdfSource) -> list[str]:
    """テキストを抽出できなかったことの警告 (REQ-F-119)。OCR は行わない。"""
    has_text = [any(not c.text.isspace() for c in page.chars) for page in source.pages]
    if not any(has_text):
        return ["テキストを抽出できませんでした (スキャン画像の可能性があります。OCR は行いません)"]
    empty = [
        page.number
        for page, text in zip(source.pages, has_text, strict=True)
        if not text and page.image_count > 0
    ]
    if not empty:
        return []
    return [
        f"ページ {_page_ranges(empty)} からテキストを抽出できませんでした"
        " (画像のみのページの可能性があります。OCR は行いません)"
    ]
