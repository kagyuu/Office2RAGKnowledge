"""グラフのラベル抽出 (REQ-F-047)。

**タイトル・系列名・カテゴリ名のみ**を抽出する。数値データ (``c:val``) は
読まない。RAG の検索単位としては系列名・カテゴリ名までで十分に索けるうえ、
数値まで含めると出力量が肥大するため (ArchitectureHandbook §9-5)。
"""

from __future__ import annotations

from lxml import etree

from ..models import ShapeParagraph, ShapeText, make_run
from .xml_utils import NS, qn
from .zip_reader import SafeZipReader

__all__ = ["extract_chart", "find_chart_rel_ids"]


def extract_chart(reader: SafeZipReader, part_name: str, rel_id: str) -> ShapeText | None:
    """グラフのタイトル・系列名・カテゴリ名を抽出する。

    Returns:
        いずれかが取得できた場合は ``ShapeText``、すべて空なら ``None`` (INV-05)。
    """
    rels = reader.resolve_rels(part_name)
    chart_part = rels.get(rel_id)
    if not chart_part or not reader.has(chart_part):
        return None
    try:
        root = reader.read_xml(chart_part)
    except Exception:  # noqa: BLE001 - グラフの欠落は変換を止めない
        return None

    title = _extract_title(root)
    series = _extract_series_names(root)
    categories = _extract_categories(root)

    paragraphs: list[ShapeParagraph] = []
    for text in (
        title,
        f"系列: {', '.join(series)}" if series else "",
        f"カテゴリ: {', '.join(categories)}" if categories else "",
    ):
        run = make_run(text)
        if run is not None:
            paragraphs.append(ShapeParagraph(runs=(run,)))
    if not paragraphs:
        return None
    return ShapeText(shape_kind="グラフ", paragraphs=tuple(paragraphs))


def _extract_title(root: etree._Element) -> str:
    for title in root.iter(qn("c:title")):
        return "".join(node.text or "" for node in title.iter(qn("a:t"))).strip()
    return ""


def _extract_series_names(root: etree._Element) -> list[str]:
    names: list[str] = []
    for ser in root.iter(qn("c:ser")):
        for tx in ser.iter(qn("c:tx")):
            text = "".join(node.text or "" for node in tx.iter(qn("c:v"))).strip()
            if text:
                names.append(text)
            break
    return names


def _extract_categories(root: etree._Element) -> list[str]:
    """**最初の系列** の ``c:cat`` からカテゴリ名を得る。

    カテゴリは系列間で共通であるため、2つ目以降の系列は見ない。
    """
    for ser in root.iter(qn("c:ser")):
        for cat in ser.iter(qn("c:cat")):
            values = [
                (node.text or "").strip()
                for node in cat.iter(qn("c:v"))
                if (node.text or "").strip()
            ]
            if values:
                return values
        return []
    return []


def find_chart_rel_ids(root: etree._Element) -> list[str]:
    """要素配下の ``c:chart/@r:id`` を列挙する。"""
    result: list[str] = []
    for chart in root.iter(qn("c:chart")):
        value = chart.get(f"{{{NS['r']}}}id")
        if value:
            result.append(value)
    return result
