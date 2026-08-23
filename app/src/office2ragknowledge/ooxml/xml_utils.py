"""安全な XML パースと OOXML の名前空間 (P003 §4.1)。

**アプリ内の XML 解析はすべて本モジュールの ``parse_xml`` を経由する。**
各モジュールが ``lxml.etree.fromstring`` を直接呼ぶと、XXE の防御が素通りになる
(REQ-NF-007)。
"""

from __future__ import annotations

from lxml import etree

from ..errors import CorruptedFileError

__all__ = ["NS", "iter_text", "local_name", "parse_xml", "qn", "safe_parser"]

#: OOXML の名前空間。モジュールごとに定義すると綴り違いによる
#: 「要素が見つからない」不具合が起きるため、ここに集約する。
NS: dict[str, str] = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    "wpg": "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "dgm": "http://schemas.openxmlformats.org/drawingml/2006/diagram",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "v": "urn:schemas-microsoft-com:vml",
}


def qn(name: str) -> str:
    """``"w:p"`` のような接頭辞付きのタグ名を ``"{URI}p"`` に変換する。"""
    prefix, _, tag = name.partition(":")
    if not tag:
        return name
    uri = NS.get(prefix)
    if uri is None:
        raise KeyError(f"未知の名前空間接頭辞です: {prefix!r}")
    return f"{{{uri}}}{tag}"


def safe_parser() -> etree.XMLParser:
    """XXE と外部参照を無効化した XML パーサを返す (REQ-NF-007, REQ-NF-010)。

    - ``resolve_entities=False``: 実体参照を展開しない (XXE / 十億の笑いの防御)
    - ``no_network=True``: 外部 DTD・スキーマを取得しない
    - ``load_dtd=False``: DTD を読み込まない
    - ``huge_tree=False``: 深い入れ子・巨大ノードの制限を保つ
    - ``recover=False``: 壊れた XML を黙って修復しない
    """
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        dtd_validation=False,
        huge_tree=False,
        recover=False,
    )


def parse_xml(data: bytes) -> etree._Element:
    """バイト列を安全に解析する。壊れていれば ``CorruptedFileError``。"""
    try:
        return etree.fromstring(data, parser=safe_parser())
    except etree.XMLSyntaxError as exc:
        raise CorruptedFileError("ファイルが破損しているため読み取れません", hint="") from exc


def local_name(el: etree._Element) -> str:
    """名前空間を除いたタグ名を返す。"""
    tag = el.tag
    if not isinstance(tag, str):
        return ""
    return tag.rpartition("}")[2]


def iter_text(el: etree._Element, tag: str) -> str:
    """``el`` 配下の指定タグのテキストを、出現順に連結する。

    Args:
        el: 走査の起点
        tag: ``"w:t"`` のような接頭辞付きタグ名
    """
    return "".join(node.text or "" for node in el.iter(qn(tag)))
