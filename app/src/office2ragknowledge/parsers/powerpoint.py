"""PowerPoint パーサ (REQ-F-037, 041〜047)。

**スライド本体のみを走査し、スライドマスター・レイアウトを走査しない**
(REQ-F-046)。これにより会社名・ページ番号等の定型文言が自動的に除外される。

プレースホルダ (タイトル・本文) は本文として扱い、図形テキストブロックには
含めない (REQ-F-037: 二重出力の防止)。
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from lxml import etree

from ..models import (
    Block,
    ConvertOptions,
    Document,
    DocumentFormat,
    DocumentMeta,
    ExtractedImage,
    Image,
    InlineRun,
    ListBlock,
    ListItem,
    ShapeParagraph,
    ShapeText,
    SlideBreak,
    Table,
    TableCell,
    TableRow,
    make_run,
)
from ..ooxml.charts import extract_chart, find_chart_rel_ids
from ..ooxml.images import ImageCollector
from ..ooxml.shapes import PPTX_DIALECT, ShapeTextExtractor
from ..ooxml.smartart import extract_smartart, find_smartart_rel_ids
from ..ooxml.xml_utils import NS, qn
from ..ooxml.zip_reader import SafeZipReader
from .base import parse_iso, read_core_properties

__all__ = ["PowerPointParser"]

_PRESENTATION = "ppt/presentation.xml"
_SLIDE_NUM = re.compile(r"slide(\d+)\.xml$")

#: 本文として扱うプレースホルダの種別。図形テキストには含めない (REQ-F-037)。
_BODY_PLACEHOLDERS = frozenset({"title", "ctrTitle", "subTitle", "body", "", "obj"})


class PowerPointParser:
    """``.pptx`` / ``.pptm`` を中間表現に変換する。"""

    def parse(
        self,
        reader: SafeZipReader,
        filename: str,
        options: ConvertOptions,
        converted_at: datetime,
    ) -> Document:
        props = read_core_properties(reader)
        # Windows のパス区切りも扱えるよう Path を用いる (posixpath は "\\" を分割しない)
        title = props.get("title") or Path(filename).stem

        blocks: list[Block] = []
        warnings: list[str] = []
        images: list[ExtractedImage] = []
        slide_parts = self._resolve_slide_parts(reader)
        number = 0

        for part, hidden in slide_parts:
            if hidden and not options.include_hidden:
                continue
            number += 1
            slide_blocks, slide_images = self._parse_slide(reader, part, number, options, hidden)
            blocks.extend(slide_blocks)
            images.extend(slide_images)

        meta = DocumentMeta(
            source_file=Path(filename).name,
            source_path=filename,
            source_format=DocumentFormat.PPTX,
            source_size_bytes=0,
            source_sha256="",
            converter="office2ragknowledge",
            converted_at=converted_at,
            title=title,
            author=props.get("author"),
            created_at=parse_iso(props.get("created")),
            modified_at=parse_iso(props.get("modified")),
            warnings=tuple(warnings),
        )
        return Document(
            format=DocumentFormat.PPTX,
            title=title,
            meta=meta,
            blocks=tuple(blocks),
            warnings=tuple(warnings),
            images=tuple(images),
        )

    @staticmethod
    def _resolve_slide_parts(reader: SafeZipReader) -> list[tuple[str, bool]]:
        """スライドのパートを表示順に解決する。``_rels`` 経由で対応付ける。"""
        if not reader.has(_PRESENTATION):
            return []
        root = reader.read_xml(_PRESENTATION)
        rels = reader.resolve_rels(_PRESENTATION)
        result: list[tuple[str, bool]] = []
        sld_id_lst = root.find(qn("p:sldIdLst"))
        if sld_id_lst is None:
            return []
        for sld_id in sld_id_lst.findall(qn("p:sldId")):
            rel_id = sld_id.get(f"{{{NS['r']}}}id")
            if not rel_id or rel_id not in rels:
                continue
            part = rels[rel_id]
            hidden = False
            if reader.has(part):
                slide_root = reader.read_xml(part)
                hidden = slide_root.get("show") == "0"
            result.append((part, hidden))
        return result

    def _parse_slide(
        self,
        reader: SafeZipReader,
        part: str,
        number: int,
        options: ConvertOptions,
        hidden: bool,
    ) -> tuple[list[Block], tuple[ExtractedImage, ...]]:
        root = reader.read_xml(part)
        sp_tree = root.find(qn("p:cSld"))
        if sp_tree is not None:
            sp_tree = sp_tree.find(qn("p:spTree"))
        if sp_tree is None:
            return [], ()

        images = ImageCollector(reader, part, options.images)
        title_text: str | None = None
        body_lists: list[ListBlock] = []
        tables: list[Table] = []
        shapes: list[ShapeText] = []
        image_blocks: list[Image] = []

        for shape_el in sp_tree:
            if not isinstance(shape_el.tag, str):
                continue
            ph_type = self._placeholder_type(shape_el)
            if ph_type is not None and ph_type in ("title", "ctrTitle"):
                title_text = self._text_of(shape_el) or None
                continue
            if ph_type is not None:
                # 本文プレースホルダはリストとして扱う (REQ-F-042)
                items = self._list_items(shape_el)
                if items:
                    body_lists.append(ListBlock(items=tuple(items)))
                continue
            table = self._table_of(shape_el)
            if table is not None:
                tables.append(table)
                continue
            if options.shapes:
                # プレースホルダ以外の図形のみ (REQ-F-037)
                found, _ = ShapeTextExtractor(PPTX_DIALECT).extract(shape_el)
                shapes.extend(found)
                for rel_id in find_smartart_rel_ids(shape_el):
                    smart = extract_smartart(reader, part, rel_id)
                    if smart is not None:
                        shapes.append(smart)
                for rel_id in find_chart_rel_ids(shape_el):
                    chart = extract_chart(reader, part, rel_id)
                    if chart is not None:
                        shapes.append(chart)
            image_blocks.extend(images.collect(shape_el))

        notes = self._notes_of(reader, part) if options.notes else ()
        label = title_text
        if hidden and label:
            label = f"{label} (非表示)"
        elif hidden:
            label = "(非表示)"

        blocks: list[Block] = [SlideBreak(slide_number=number, slide_title=label, notes=notes)]
        blocks.extend(body_lists)
        blocks.extend(tables)
        blocks.extend(image_blocks)
        blocks.extend(shapes)
        return blocks, images.images

    @staticmethod
    def _placeholder_type(shape_el: etree._Element) -> str | None:
        """プレースホルダの種別を返す。プレースホルダでなければ ``None``。"""
        for ph in shape_el.iter(qn("p:ph")):
            return str(ph.get("type", "body"))
        return None

    @staticmethod
    def _text_of(shape_el: etree._Element) -> str:
        return "".join(node.text or "" for node in shape_el.iter(qn("a:t"))).strip()

    @staticmethod
    def _list_items(shape_el: etree._Element) -> list[ListItem]:
        items: list[ListItem] = []
        for para in shape_el.iter(qn("a:p")):
            text = "".join(node.text or "" for node in para.iter(qn("a:t")))
            run = make_run(text)
            if run is None:
                continue
            level = 0
            ppr = para.find(qn("a:pPr"))
            if ppr is not None:
                value = ppr.get("lvl")
                if value and value.isdigit():
                    level = int(value)
            items.append(ListItem(runs=(run,), level=level))
        return items

    @staticmethod
    def _table_of(shape_el: etree._Element) -> Table | None:
        for tbl in shape_el.iter(qn("a:tbl")):
            rows: list[TableRow] = []
            for tr in tbl.findall(qn("a:tr")):
                cells: list[TableCell] = []
                for tc in tr.findall(qn("a:tc")):
                    text = "".join(node.text or "" for node in tc.iter(qn("a:t")))
                    runs = (InlineRun(text=text),) if text else ()
                    span = 1
                    grid_span = tc.get("gridSpan")
                    if grid_span and grid_span.isdigit():
                        span = max(1, int(grid_span))
                    cells.append(TableCell(runs=runs))
                    for _ in range(span - 1):
                        cells.append(TableCell(runs=runs, from_merge=True))
                if cells:
                    rows.append(TableRow(cells=tuple(cells), is_header=not rows))
            if rows:
                width = max(len(r.cells) for r in rows)
                return Table(
                    rows=tuple(
                        TableRow(
                            cells=r.cells + tuple(TableCell() for _ in range(width - len(r.cells))),
                            is_header=r.is_header,
                        )
                        for r in rows
                    ),
                    has_header=True,
                )
        return None

    @staticmethod
    def _notes_of(reader: SafeZipReader, slide_part: str) -> tuple[ShapeParagraph, ...]:
        """発表者ノートを読む (REQ-F-044)。"""
        types = reader.rel_type_map(slide_part)
        targets = reader.resolve_rels(slide_part)
        for rel_id, rel_type in types.items():
            if not rel_type.endswith("/notesSlide") or rel_id not in targets:
                continue
            part = targets[rel_id]
            if not reader.has(part):
                continue
            try:
                root = reader.read_xml(part)
            except Exception:  # noqa: BLE001 - ノートの欠落は変換を止めない
                continue
            paragraphs: list[ShapeParagraph] = []
            for shape_el in root.iter(qn("p:sp")):
                ph_type = None
                for ph in shape_el.iter(qn("p:ph")):
                    ph_type = ph.get("type", "body")
                    break
                if ph_type != "body":
                    continue
                for para in shape_el.iter(qn("a:p")):
                    text = "".join(node.text or "" for node in para.iter(qn("a:t")))
                    run = make_run(text)
                    if run is not None:
                        paragraphs.append(ShapeParagraph(runs=(run,)))
            if paragraphs:
                return tuple(paragraphs)
        return ()
