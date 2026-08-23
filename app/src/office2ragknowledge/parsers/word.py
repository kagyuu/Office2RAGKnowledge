"""Word パーサ (REQ-F-011〜020, 036)。

**python-docx の公開 API では図形テキストが取得できない** (P003 §1.3 で実測。
``document.paragraphs`` はテキストボックスを空文字として落とす)。そのため
本文の走査は lxml で行い、``ShapeTextExtractor`` を併用する。
"""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from lxml import etree

from ..models import (
    Block,
    ConvertOptions,
    Document,
    DocumentFormat,
    DocumentMeta,
    Footnote,
    Heading,
    Image,
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
from ..ooxml.charts import extract_chart, find_chart_rel_ids
from ..ooxml.images import ImageCollector
from ..ooxml.shapes import WORD_DIALECT, ShapeTextExtractor
from ..ooxml.smartart import extract_smartart, find_smartart_rel_ids
from ..ooxml.xml_utils import NS, local_name, qn
from ..ooxml.zip_reader import SafeZipReader
from .base import parse_iso, read_core_properties

__all__ = ["WordParser"]

_HEADING_RE = re.compile(r"^(?:Heading|見出し)\s*(\d+)$", re.IGNORECASE)
_MONO_FONTS = ("mono", "courier", "consolas", "ＭＳ ゴシック")
_MAIN_PART = "word/document.xml"


class WordParser:
    """``.docx`` / ``.docm`` を中間表現に変換する。"""

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

        root = reader.read_xml(_MAIN_PART)
        body = root.find(qn("w:body"))
        rels = reader.resolve_rels(_MAIN_PART)
        self._rels = rels
        self._reader = reader
        self._options = options
        self._images = ImageCollector(reader, _MAIN_PART, options.images)
        self._extractor = ShapeTextExtractor(WORD_DIALECT)
        self._styles = self._read_style_names(reader)
        self._numbering_kinds = self._read_numbering_kinds(reader)

        blocks: list[Block] = []
        warnings: list[str] = []
        footnotes: list[Footnote] = []
        self._footnote_ids: list[str] = []
        unanchored = 0

        if body is not None:
            blocks, unanchored = self._walk_body(body)

        footnotes = self._read_footnotes(reader)
        blocks.extend(footnotes)

        if unanchored:
            warnings.append(
                f"アンカー位置を特定できない図形が {unanchored} 件あり、文書末尾にまとめました"
            )

        meta = DocumentMeta(
            source_file=Path(filename).name,
            source_path=filename,
            source_format=DocumentFormat.DOCX,
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
            format=DocumentFormat.DOCX,
            title=title,
            meta=meta,
            blocks=tuple(blocks),
            warnings=tuple(warnings),
            images=self._images.images,
        )

    # -- 本文の走査 ------------------------------------------------------

    def _walk_body(self, body: etree._Element) -> tuple[list[Block], int]:
        blocks: list[Block] = []
        pending_list: list[ListItem] = []
        unanchored = 0

        def flush_list() -> None:
            nonlocal pending_list
            if pending_list:
                blocks.append(ListBlock(items=tuple(pending_list)))
                pending_list = []

        for child in body:
            if not isinstance(child.tag, str):
                continue
            name = local_name(child)
            if name == "p":
                item = self._as_list_item(child)
                if item is not None:
                    pending_list.append(item)
                else:
                    flush_list()
                    para = self._as_paragraph(child)
                    if para is not None:
                        blocks.append(para)
                # 図形はアンカーされた段落の直後に置く (REQ-F-036)
                shapes = self._shapes_in(child)
                if shapes:
                    flush_list()
                    blocks.extend(shapes)
                images = self._images_in(child)
                if images:
                    flush_list()
                    blocks.extend(images)
            elif name == "tbl":
                flush_list()
                table = self._as_table(child)
                if table is not None:
                    blocks.append(table)
            elif name == "sectPr":
                continue  # 改ページ・セクション区切りは出力しない (REQ-F-020)
        flush_list()
        return blocks, unanchored

    def _runs_of(self, para: etree._Element) -> tuple[InlineRun, ...]:
        """段落の run を取り出す。変更履歴と図形の扱いに注意 (REQ-F-018)。"""
        runs: list[InlineRun] = []
        for node in para.iter():
            if not isinstance(node.tag, str):
                continue
            if local_name(node) != "r":
                continue
            if self._is_deleted(node):
                continue  # w:del 配下は出力しない (変更を反映した後の状態)
            if self._inside_textbox(node, para):
                continue  # 図形内のテキストは ShapeText 側で扱う
            text = self._run_text(node)
            if not text:
                continue
            run = make_run(
                text,
                bold=self._has_prop(node, "w:b"),
                italic=self._has_prop(node, "w:i"),
                strike=self._has_prop(node, "w:strike"),
                code=self._is_monospace(node),
                link_url=self._link_of(node, para),
            )
            if run is not None:
                runs.append(run)
        return tuple(runs)

    @staticmethod
    def _run_text(run: etree._Element) -> str:
        """run の本文テキストを取り出す。

        **図形 (drawing / pict / AlternateContent) の内側では打ち切る。**
        図形を包む外側の run をそのまま ``iter(w:t)`` で走査すると、
        テキストボックス内の文字列を本文として拾ってしまい、さらに
        ``mc:Choice`` と ``mc:Fallback`` の両方を含むため二重になる。
        図形内のテキストは ``ShapeText`` 側が担当する。
        """
        parts: list[str] = []

        def walk(el: etree._Element) -> None:
            for child in el:
                if not isinstance(child.tag, str):
                    continue
                name = local_name(child)
                if name in ("drawing", "pict", "AlternateContent", "txbxContent", "object"):
                    continue  # 図形の内側へ入らない
                if name == "t":
                    parts.append(child.text or "")
                    continue
                walk(child)

        walk(run)
        return "".join(parts)

    @staticmethod
    def _is_deleted(node: etree._Element) -> bool:
        parent = node.getparent()
        while parent is not None:
            if local_name(parent) == "del":
                return True
            parent = parent.getparent()
        return False

    @staticmethod
    def _inside_textbox(node: etree._Element, stop: etree._Element) -> bool:
        parent = node.getparent()
        while parent is not None and parent is not stop:
            if local_name(parent) in ("txbxContent", "txbx", "pict", "AlternateContent"):
                return True
            parent = parent.getparent()
        return False

    @staticmethod
    def _has_prop(node: etree._Element, tag: str) -> bool:
        rpr = node.find(qn("w:rPr"))
        if rpr is None:
            return False
        el = rpr.find(qn(tag))
        if el is None:
            return False
        return el.get(f"{{{NS['w']}}}val") not in ("0", "false")

    @staticmethod
    def _is_monospace(node: etree._Element) -> bool:
        rpr = node.find(qn("w:rPr"))
        if rpr is None:
            return False
        fonts = rpr.find(qn("w:rFonts"))
        if fonts is None:
            return False
        name = (fonts.get(f"{{{NS['w']}}}ascii") or "").lower()
        return any(token in name for token in _MONO_FONTS)

    def _link_of(self, node: etree._Element, stop: etree._Element) -> str | None:
        parent = node.getparent()
        while parent is not None and parent is not stop.getparent():
            if local_name(parent) == "hyperlink":
                rel_id = parent.get(f"{{{NS['r']}}}id")
                if rel_id:
                    return self._rels.get(rel_id)
                return None
            parent = parent.getparent()
        return None

    def _style_of(self, para: etree._Element) -> str:
        ppr = para.find(qn("w:pPr"))
        if ppr is None:
            return ""
        style = ppr.find(qn("w:pStyle"))
        if style is None:
            return ""
        style_id = style.get(f"{{{NS['w']}}}val") or ""
        return self._styles.get(style_id, style_id)

    def _as_paragraph(self, para: etree._Element) -> Block | None:
        runs = self._runs_of(para)
        if not runs:
            return None
        style = self._style_of(para)
        m = _HEADING_RE.match(style)
        if m is not None:
            # 文書タイトルが # を占めるため1段繰り下げる (P002 §5.9)
            level = min(int(m.group(1)) + 1, 6)
            return Heading(level=level, runs=runs)
        return Paragraph(runs=runs)

    def _as_list_item(self, para: etree._Element) -> ListItem | None:
        """リスト項目なら ``ListItem`` を返す。

        ``w:numPr`` を持つ場合に加え、**スタイル名がリストを示す場合**も対象とする。
        python-docx の ``List Bullet`` のようなスタイルベースのリストは ``w:numPr``
        を持たないことがあるため、両方を見ないと箇条書きが段落に落ちる。
        """
        ppr = para.find(qn("w:pPr"))
        style = self._style_of(para)
        style_ordered = "List Number" in style or "リスト段落 (番号" in style
        style_bullet = "List Bullet" in style or "List Paragraph" in style
        numpr = ppr.find(qn("w:numPr")) if ppr is not None else None
        if numpr is None and not (style_ordered or style_bullet):
            return None

        runs = self._runs_of(para)
        if not runs:
            return None

        level = 0
        ordered = style_ordered
        if numpr is not None:
            ilvl = numpr.find(qn("w:ilvl"))
            if ilvl is not None:
                try:
                    level = int(ilvl.get(f"{{{NS['w']}}}val") or "0")
                except ValueError:
                    level = 0
            numid_el = numpr.find(qn("w:numId"))
            if numid_el is not None:
                num_id = numid_el.get(f"{{{NS['w']}}}val") or ""
                ordered = ordered or self._numbering_kinds.get(num_id, False)
        # スタイル名の末尾の数字が階層を表すことがある (List Bullet 2 など)
        m = re.search(r"(\d+)$", style)
        if m is not None and level == 0:
            level = max(0, int(m.group(1)) - 1)
        return ListItem(runs=runs, level=level, ordered=ordered)

    def _as_table(self, tbl: etree._Element) -> Table | None:
        rows: list[TableRow] = []
        for tr in tbl.findall(qn("w:tr")):
            cells: list[TableCell] = []
            for tc in tr.findall(qn("w:tc")):
                runs: list[InlineRun] = []
                for para in tc.findall(qn("w:p")):
                    runs.extend(self._runs_of(para))
                span = self._grid_span(tc)
                cells.append(TableCell(runs=tuple(runs)))
                # 結合セルは値を複製して矩形を保つ (REQ-F-013)
                for _ in range(span - 1):
                    cells.append(TableCell(runs=tuple(runs), from_merge=True))
            if cells:
                rows.append(TableRow(cells=tuple(cells), is_header=not rows))
        if not rows:
            return None
        width = max(len(r.cells) for r in rows)
        padded = tuple(
            TableRow(
                cells=r.cells + tuple(TableCell() for _ in range(width - len(r.cells))),
                is_header=r.is_header,
            )
            for r in rows
        )
        return Table(rows=padded, has_header=True)

    @staticmethod
    def _grid_span(tc: etree._Element) -> int:
        tc_pr = tc.find(qn("w:tcPr"))
        if tc_pr is None:
            return 1
        span = tc_pr.find(qn("w:gridSpan"))
        if span is None:
            return 1
        try:
            return max(1, int(span.get(f"{{{NS['w']}}}val") or "1"))
        except ValueError:
            return 1

    # -- 図形・画像 ------------------------------------------------------

    def _shapes_in(self, para: etree._Element) -> list[ShapeText]:
        if not self._options.shapes:
            return []
        shapes, _ = self._extractor.extract(para)
        result = list(shapes)
        for rel_id in find_smartart_rel_ids(para):
            smart = extract_smartart(self._reader, _MAIN_PART, rel_id)
            if smart is not None:
                result.append(smart)
        for rel_id in find_chart_rel_ids(para):
            chart = extract_chart(self._reader, _MAIN_PART, rel_id)
            if chart is not None:
                result.append(chart)
        return result

    def _images_in(self, para: etree._Element) -> list[Image]:
        return self._images.collect(para)

    # -- 補助パート ------------------------------------------------------

    @staticmethod
    def _read_style_names(reader: SafeZipReader) -> dict[str, str]:
        """スタイルID → スタイル名の対応を読む。"""
        part = "word/styles.xml"
        if not reader.has(part):
            return {}
        try:
            root = reader.read_xml(part)
        except Exception:  # noqa: BLE001 - スタイルの欠落は変換を止めない
            return {}
        result: dict[str, str] = {}
        for style in root.iter(qn("w:style")):
            style_id = style.get(f"{{{NS['w']}}}styleId")
            name_el = style.find(qn("w:name"))
            if style_id and name_el is not None:
                value = name_el.get(f"{{{NS['w']}}}val")
                if value:
                    result[style_id] = value
        return result

    @staticmethod
    def _read_numbering_kinds(reader: SafeZipReader) -> dict[str, bool]:
        """numId → 番号付きか (bullet でないか) の対応を読む。"""
        part = "word/numbering.xml"
        if not reader.has(part):
            return {}
        try:
            root = reader.read_xml(part)
        except Exception:  # noqa: BLE001
            return {}
        abstract_kind: dict[str, bool] = {}
        for abstract in root.iter(qn("w:abstractNum")):
            aid = abstract.get(f"{{{NS['w']}}}abstractNumId") or ""
            ordered = False
            for fmt in abstract.iter(qn("w:numFmt")):
                value = fmt.get(f"{{{NS['w']}}}val") or ""
                if value and value != "bullet":
                    ordered = True
                break
            abstract_kind[aid] = ordered
        result: dict[str, bool] = {}
        for num in root.iter(qn("w:num")):
            num_id = num.get(f"{{{NS['w']}}}numId") or ""
            ref = num.find(qn("w:abstractNumId"))
            if ref is None:
                continue
            aid = ref.get(f"{{{NS['w']}}}val") or ""
            result[num_id] = abstract_kind.get(aid, False)
        return result

    def _read_footnotes(self, reader: SafeZipReader) -> list[Footnote]:
        """脚注・文末脚注の本文を読む (REQ-F-016)。"""
        result: list[Footnote] = []
        for part, tag in (
            ("word/footnotes.xml", "w:footnote"),
            ("word/endnotes.xml", "w:endnote"),
        ):
            if not reader.has(part):
                continue
            try:
                root = reader.read_xml(part)
            except Exception:  # noqa: BLE001
                continue
            for note in root.iter(qn(tag)):
                note_id = note.get(f"{{{NS['w']}}}id") or ""
                note_type = note.get(f"{{{NS['w']}}}type")
                if note_type in ("separator", "continuationSeparator"):
                    continue
                if note_id in ("0", "-1"):
                    continue
                runs: list[InlineRun] = []
                for para in note.iter(qn("w:p")):
                    runs.extend(self._runs_of(para))
                if runs:
                    result.append(Footnote(marker=note_id, runs=tuple(runs)))
        return result


def make_shape_paragraphs(texts: list[str]) -> tuple[ShapeParagraph, ...]:
    """テキストの並びから ``ShapeParagraph`` を作る (ヘッダー・フッター用)。"""
    paragraphs = []
    for text in texts:
        run = make_run(text)
        if run is not None:
            paragraphs.append(ShapeParagraph(runs=(run,)))
    return tuple(paragraphs)


def with_anchor(shape: ShapeText, anchor: str | None) -> ShapeText:
    """アンカーを設定した複製を返す。"""
    return replace(shape, anchor=anchor)
