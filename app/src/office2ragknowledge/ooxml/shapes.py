"""オートシェープ内テキストの抽出 (中核機能 / REQ-F-031〜033, 039, 040)。

3形式 (Word / Excel / PowerPoint) で共有する。形式差は ``ShapeDialect`` として
注入する。形式ごとに書くと、同じ不具合を3回修正することになるため。

**最重要**: ``mc:AlternateContent`` は ``mc:Choice`` のみを辿る (ADR-003)。
Word のテキストボックスは ``mc:Choice`` (新形式) と ``mc:Fallback`` (旧 VML) の
**両方に同じ内容**を持つため、素朴に ``.//w:txbxContent`` を全件拾うと
**すべての図形テキストが2回出力される** (P003 §1.3 で実測)。
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from lxml import etree

from ..models import (
    InlineRun,
    ShapeParagraph,
    ShapeText,
    Table,
    TableCell,
    TableRow,
    make_run,
)
from .xml_utils import NS, local_name, qn

__all__ = [
    "EXCEL_DIALECT",
    "MAX_GROUP_DEPTH",
    "PPTX_DIALECT",
    "WORD_DIALECT",
    "ShapeDialect",
    "ShapeTextExtractor",
    "classify_shape",
]

MAX_GROUP_DEPTH = 50
"""グループの再帰の上限。壊れたファイルによる無限再帰を防ぐ安全弁。"""


@dataclass(frozen=True, slots=True)
class ShapeDialect:
    """形式ごとの要素名の違い (P003 §6.1)。"""

    shape_tag: str
    group_tag: str
    text_body_tag: str
    paragraph_tag: str
    text_tag: str
    connector_tag: str = ""
    graphic_frame_tag: str = ""


WORD_DIALECT = ShapeDialect(
    shape_tag="wps:wsp",
    group_tag="wpg:wgp",
    text_body_tag="w:txbxContent",
    paragraph_tag="w:p",
    text_tag="w:t",
)

EXCEL_DIALECT = ShapeDialect(
    shape_tag="xdr:sp",
    group_tag="xdr:grpSp",
    text_body_tag="xdr:txBody",
    paragraph_tag="a:p",
    text_tag="a:t",
    connector_tag="xdr:cxnSp",
    graphic_frame_tag="xdr:graphicFrame",
)

PPTX_DIALECT = ShapeDialect(
    shape_tag="p:sp",
    group_tag="p:grpSp",
    text_body_tag="p:txBody",
    paragraph_tag="a:p",
    text_tag="a:t",
    connector_tag="p:cxnSp",
    graphic_frame_tag="p:graphicFrame",
)

#: プリセット名 → 日本語の種別名 (P002 §5.8)。
_PRESET_EXACT: dict[str, str] = {
    "rect": "四角形",
    "roundRect": "四角形",
    "ellipse": "円・楕円",
    "triangle": "三角形",
    "rtTriangle": "三角形",
}


def classify_shape(el: etree._Element, dialect: ShapeDialect) -> str:
    """図形の種別を日本語名で返す (P002 §5.8)。

    網羅的に分類せず、頻出のものを分類して残りは総称「図形」に落とす。
    未分類でもテキストの取りこぼしは生じない。
    """
    if dialect.connector_tag and local_name(el) == dialect.connector_tag.split(":")[1]:
        return "線・コネクタ"

    # テキストボックス属性を持つか
    for body_pr in el.iter(qn("a:bodyPr")):
        del body_pr
        break
    for nv_pr in el.iter(qn("wps:cNvSpPr")):
        if nv_pr.get("txBox") == "1":
            return "テキストボックス"
    for nv_pr in el.iter(qn("a:cNvSpPr")):
        if nv_pr.get("txBox") == "1":
            return "テキストボックス"
    for nv_pr in el.iter(qn("p:cNvSpPr")):
        if nv_pr.get("txBox") == "1":
            return "テキストボックス"

    preset = ""
    for geom in el.iter(qn("a:prstGeom")):
        preset = geom.get("prst", "")
        break
    if not preset:
        return "図形"
    if preset in _PRESET_EXACT:
        return _PRESET_EXACT[preset]
    if "Callout" in preset:
        return "吹き出し"
    if "Arrow" in preset:
        return "矢印"
    if "Rect" in preset:
        return "四角形"
    return "図形"


def _shape_name(el: etree._Element) -> str | None:
    """``cNvPr`` の ``name`` 属性を返す。"""
    for tag in ("wps:cNvPr", "xdr:cNvPr", "p:cNvPr", "a:cNvPr"):
        try:
            qualified = qn(tag)
        except KeyError:  # pragma: no cover - 名前空間は定義済み
            continue
        for node in el.iter(qualified):
            name = node.get("name")
            if name:
                return str(name)
    return None


class ShapeTextExtractor:
    """図形テキストを抽出する。3形式で共有する。"""

    def __init__(self, dialect: ShapeDialect) -> None:
        self.dialect = dialect
        self._shape_local = dialect.shape_tag.split(":")[1]
        self._group_local = dialect.group_tag.split(":")[1]
        self._body_local = dialect.text_body_tag.split(":")[1]
        self._connector_local = dialect.connector_tag.split(":")[1] if dialect.connector_tag else ""

    def extract(
        self, root: etree._Element, *, group_path: tuple[str, ...] = ()
    ) -> tuple[list[ShapeText], int]:
        """図形テキストを抽出する。

        Returns:
            (ShapeText の並び, 走査した図形の総数)

        **図形の総数はテキストの有無によらず数える。** INV-05 によりテキストの
        無い図形は ``ShapeText`` を作らないため、``inspect`` の「図形」列
        (総数と、うちテキストあり数) を出すには別途カウンタが要る (P003 §8.3)。
        """
        results: list[ShapeText] = []
        # 渡された要素そのものが図形である場合 (PowerPoint のように、呼び出し元が
        # 図形単位で走査する場合) にも対応する。子だけを見ると取りこぼす。
        if local_name(root) in (self._shape_local, self._connector_local or "\0"):
            shape = self._build_shape(root, group_path)
            if shape is not None:
                results.append(shape)
            return results, 1
        count = self._walk(root, group_path, 0, results)
        return results, count

    def _walk(
        self,
        el: etree._Element,
        group_path: tuple[str, ...],
        depth: int,
        out: list[ShapeText],
    ) -> int:
        if depth > MAX_GROUP_DEPTH:
            return 0
        count = 0
        for child in el:
            if not isinstance(child.tag, str):
                continue  # コメント・処理命令
            name = local_name(child)

            if name == "AlternateContent" and child.tag.startswith(f"{{{NS['mc']}}}"):
                target = self._select_alternate(child)
                if target is not None:
                    count += self._walk(target, group_path, depth, out)
                continue

            if name == self._group_local:
                group_name = _shape_name(child) or ""
                nested = group_path + ((group_name,) if group_name else ())
                count += self._walk(child, nested, depth + 1, out)
                continue

            if name == self._shape_local or (
                self._connector_local and name == self._connector_local
            ):
                count += 1
                shape = self._build_shape(child, group_path)
                if shape is not None:
                    out.append(shape)
                continue

            count += self._walk(child, group_path, depth, out)
        return count

    @staticmethod
    def _select_alternate(el: etree._Element) -> etree._Element | None:
        """``mc:AlternateContent`` から辿るべき子を選ぶ (ADR-003)。

        ``mc:Choice`` が1つ以上あれば **最初の (または解釈できる) Choice のみ**
        を辿る。無い場合に限り ``mc:Fallback`` を辿る。**両方を辿ってはならない。**
        """
        choices = el.findall(f"{{{NS['mc']}}}Choice")
        if choices:
            for choice in choices:
                requires = choice.get("Requires", "")
                if any(token in requires.split() for token in ("wps", "wpg")):
                    return choice
            return choices[0]
        return el.find(f"{{{NS['mc']}}}Fallback")

    def _build_shape(self, el: etree._Element, group_path: tuple[str, ...]) -> ShapeText | None:
        paragraphs = self._extract_paragraphs(el)
        tables = self._extract_tables(el)
        # INV-05: テキストを持たない図形はブロック化しない
        if not paragraphs and not tables:
            return None
        return ShapeText(
            shape_kind=classify_shape(el, self.dialect),
            shape_name=_shape_name(el),
            anchor=None,  # 形式ごとに呼び出し元が設定する
            group_path=group_path,
            paragraphs=tuple(paragraphs),
            tables=tuple(tables),
        )

    def _extract_paragraphs(self, el: etree._Element) -> list[ShapeParagraph]:
        body_tag = qn(self.dialect.text_body_tag)
        para_tag = qn(self.dialect.paragraph_tag)
        text_tag = qn(self.dialect.text_tag)
        paragraphs: list[ShapeParagraph] = []
        for body in el.iter(body_tag):
            for para in body.iter(para_tag):
                text = "".join(node.text or "" for node in para.iter(text_tag))
                run = make_run(text)
                if run is None:
                    continue  # 空段落は含めない
                paragraphs.append(ShapeParagraph(runs=(run,), level=_paragraph_level(para)))
        return paragraphs

    def _extract_tables(self, el: etree._Element) -> list[Table]:
        """図形内の DrawingML の表を抽出する (REQ-F-039)。"""
        tables: list[Table] = []
        for tbl in el.iter(qn("a:tbl")):
            rows: list[TableRow] = []
            for i, tr in enumerate(tbl.iter(qn("a:tr"))):
                cells: list[TableCell] = []
                for tc in tr.iter(qn("a:tc")):
                    text = "".join(node.text or "" for node in tc.iter(qn("a:t")))
                    runs = (InlineRun(text=text),) if text else ()
                    cells.append(TableCell(runs=runs))
                if cells:
                    rows.append(TableRow(cells=tuple(cells), is_header=i == 0))
            if rows:
                width = max(len(r.cells) for r in rows)
                padded = tuple(
                    TableRow(
                        cells=r.cells + tuple(TableCell() for _ in range(width - len(r.cells))),
                        is_header=r.is_header,
                    )
                    for r in rows
                )
                tables.append(Table(rows=padded, has_header=True))
        return tables


def _paragraph_level(para: etree._Element) -> int:
    """段落の箇条書き階層を返す。取得できなければ 0。"""
    for ppr in para.iter(qn("a:pPr")):
        level = ppr.get("lvl")
        if level and level.isdigit():
            return int(level)
        break
    return 0


def with_anchor(shape: ShapeText, anchor: str | None) -> ShapeText:
    """アンカーを設定した複製を返す (形式別パーサが使う)。"""
    return replace(shape, anchor=anchor)
