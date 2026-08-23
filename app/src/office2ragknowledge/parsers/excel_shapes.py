"""Excel のシートと図形の対応付け (REQ-F-035)。

シートの ``_rels`` から drawing パートを解決し、アンカーからセル参照を求める。

**ファイル名の数値でシートと drawing を対応付けてはならない。** ``sheet1.xml``
の ``1`` はシートの並び順ではない (削除・並べ替えの履歴による)。誤ったシートに
図形が付く (P003 §7.6)。

**``xdr:from/xdr:col`` と ``xdr:row`` は0起点**である。A1 形式にするには +1 する。
"""

from __future__ import annotations

from dataclasses import replace

from lxml import etree

from ..models import ShapeText, col_to_letter
from ..ooxml.charts import extract_chart, find_chart_rel_ids
from ..ooxml.shapes import EXCEL_DIALECT, ShapeTextExtractor
from ..ooxml.smartart import extract_smartart, find_smartart_rel_ids
from ..ooxml.xml_utils import local_name, qn
from ..ooxml.zip_reader import SafeZipReader

__all__ = ["DRAWING_REL_TYPE", "extract_sheet_shapes", "resolve_drawing_part"]

DRAWING_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing"

_ANCHOR_TAGS = ("xdr:twoCellAnchor", "xdr:oneCellAnchor", "xdr:absoluteAnchor")


def resolve_drawing_part(reader: SafeZipReader, sheet_part: str) -> str | None:
    """シートのパートから drawing パートを ``_rels`` 経由で解決する。"""
    types = reader.rel_type_map(sheet_part)
    targets = reader.resolve_rels(sheet_part)
    for rel_id, rel_type in types.items():
        if rel_type.endswith("/drawing") and rel_id in targets:
            return targets[rel_id]
    return None


def _anchor_ref(anchor_el: etree._Element) -> str | None:
    """アンカー要素から A1 形式のセル参照を求める。

    ``xdr:absoluteAnchor`` はセル位置を持たないため ``None`` を返す。
    """
    if local_name(anchor_el) == "absoluteAnchor":
        return None
    from_el = anchor_el.find(qn("xdr:from"))
    if from_el is None:
        return None
    col_el = from_el.find(qn("xdr:col"))
    row_el = from_el.find(qn("xdr:row"))
    if col_el is None or row_el is None:
        return None
    try:
        # 0起点 → 1起点
        col = int((col_el.text or "0").strip()) + 1
        row = int((row_el.text or "0").strip()) + 1
    except ValueError:
        return None
    return f"{col_to_letter(col)}{row}"


def extract_sheet_shapes(
    reader: SafeZipReader, sheet_part: str
) -> tuple[tuple[ShapeText, ...], int]:
    """シートの図形テキストとその総数を返す。

    Returns:
        (ShapeText の並び, 図形の総数)。図形の総数はテキストの有無によらない。
    """
    drawing_part = resolve_drawing_part(reader, sheet_part)
    if drawing_part is None or not reader.has(drawing_part):
        return (), 0
    try:
        root = reader.read_xml(drawing_part)
    except Exception:  # noqa: BLE001 - 図形の欠落は変換を止めない
        return (), 0

    extractor = ShapeTextExtractor(EXCEL_DIALECT)
    shapes: list[ShapeText] = []
    total = 0

    for tag in _ANCHOR_TAGS:
        for anchor_el in root.iter(qn(tag)):
            ref = _anchor_ref(anchor_el)
            found, count = extractor.extract(anchor_el)
            total += count
            for shape in found:
                shapes.append(replace(shape, anchor=ref))

            # SmartArt とグラフはグラフィックフレーム経由で参照される
            for rel_id in find_smartart_rel_ids(anchor_el):
                total += 1
                smart = extract_smartart(reader, drawing_part, rel_id)
                if smart is not None:
                    shapes.append(replace(smart, anchor=ref))
            for rel_id in find_chart_rel_ids(anchor_el):
                total += 1
                chart = extract_chart(reader, drawing_part, rel_id)
                if chart is not None:
                    shapes.append(replace(chart, anchor=ref))

    return tuple(shapes), total
