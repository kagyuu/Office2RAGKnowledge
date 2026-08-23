"""SmartArt のテキスト抽出 (REQ-F-034)。

SmartArt は ``diagrams/data*.xml`` (データモデル) と ``diagrams/drawing*.xml``
(描画結果) の **両方に同じテキスト** を持つ。

**データモデル側のみを読む** (ADR-006)。データモデルはノードの親子関係を保持して
おり箇条書きの階層を再現できるが、描画結果側は階層が失われている。両方を読むと
二重出力になる。
"""

from __future__ import annotations

from lxml import etree

from ..models import ShapeParagraph, ShapeText, make_run
from .xml_utils import NS, qn
from .zip_reader import SafeZipReader

__all__ = ["extract_smartart"]


def extract_smartart(reader: SafeZipReader, part_name: str, rel_id: str) -> ShapeText | None:
    """SmartArt のデータモデルからテキストを抽出する。

    Args:
        reader: ZIP リーダー
        part_name: グラフィックフレームを含むパート (関係の解決に使う)
        rel_id: ``dgm:relIds`` の ``r:dm`` 属性の値

    Returns:
        テキストを持つ場合は ``ShapeText``、無ければ ``None`` (INV-05)。

    階層が組み立てられない場合は、すべて ``level=0`` のフラットな並びに落とす。
    例外を送出しない (ArchitectureHandbook §9-4)。
    """
    rels = reader.resolve_rels(part_name)
    data_part = rels.get(rel_id)
    if not data_part or not reader.has(data_part):
        return None
    try:
        root = reader.read_xml(data_part)
    except Exception:  # noqa: BLE001 - SmartArt の欠落は変換を止めない
        return None

    nodes = _collect_nodes(root)
    if not nodes:
        return None
    depths = _compute_depths(root, nodes)

    paragraphs: list[ShapeParagraph] = []
    for node_id, text in nodes:
        run = make_run(text)
        if run is None:
            continue
        paragraphs.append(ShapeParagraph(runs=(run,), level=depths.get(node_id, 0)))
    if not paragraphs:
        return None
    return ShapeText(shape_kind="SmartArt", paragraphs=tuple(paragraphs))


def _collect_nodes(root: etree._Element) -> list[tuple[str, str]]:
    """``dgm:pt`` のうち実データのノードを、出現順に ``(id, テキスト)`` で返す。

    ``type="pres"`` は表示専用のため除外する。
    """
    result: list[tuple[str, str]] = []
    pt_tag, t_tag, a_t = qn("dgm:pt"), qn("dgm:t"), qn("a:t")
    for pt in root.iter(pt_tag):
        pt_type = pt.get("type", "node")
        if pt_type not in ("node", "asst"):
            continue
        model_id = pt.get("modelId")
        if model_id is None:
            continue
        text = ""
        for t_el in pt.iter(t_tag):
            text = "".join(node.text or "" for node in t_el.iter(a_t))
            break
        result.append((model_id, text))
    return result


def _compute_depths(root: etree._Element, nodes: list[tuple[str, str]]) -> dict[str, int]:
    """``dgm:cxnLst`` の ``parOf`` 接続から各ノードの深さを求める。

    接続が取れない場合はすべて 0 を返す (フラットな箇条書きに落とす)。
    """
    ids = {node_id for node_id, _ in nodes}
    parent: dict[str, str] = {}
    for cxn in root.iter(qn("dgm:cxn")):
        if cxn.get("type") != "parOf":
            continue
        src = cxn.get("srcId")
        dst = cxn.get("destId")
        if src in ids and dst in ids and dst is not None and src is not None:
            parent[dst] = src

    if not parent:
        return {node_id: 0 for node_id, _ in nodes}

    depths: dict[str, int] = {}

    def depth_of(node_id: str, seen: frozenset[str] = frozenset()) -> int:
        if node_id in depths:
            return depths[node_id]
        if node_id in seen:  # 循環参照の防御
            return 0
        p = parent.get(node_id)
        value = 0 if p is None else depth_of(p, seen | {node_id}) + 1
        depths[node_id] = value
        return value

    for node_id, _ in nodes:
        depth_of(node_id)
    return depths


def find_smartart_rel_ids(root: etree._Element) -> list[str]:
    """要素配下の ``dgm:relIds/@r:dm`` を列挙する。"""
    result: list[str] = []
    for rel in root.iter(qn("dgm:relIds")):
        value = rel.get(f"{{{NS['r']}}}dm")
        if value:
            result.append(value)
    return result
