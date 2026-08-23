"""パーサの共通プロトコルと補助 (P003 §2.2)。"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from ..models import ConvertOptions, Document
from ..ooxml.xml_utils import NS
from ..ooxml.zip_reader import SafeZipReader

__all__ = ["Parser", "parse_iso", "read_core_properties"]


class Parser(Protocol):
    """形式別パーサのプロトコル。中間表現を返す。

    ``converted_at`` は **呼び出し元が渡す**。パーサ内部で ``datetime.now()`` を
    呼ばない (単体テストで時刻を固定するため。REQ-NF-018)。
    """

    def parse(
        self,
        reader: SafeZipReader,
        filename: str,
        options: ConvertOptions,
        converted_at: datetime,
    ) -> Document:
        """文書を解析して ``Document`` を返す。"""
        ...


def read_core_properties(reader: SafeZipReader) -> dict[str, str]:
    """``docProps/core.xml`` からタイトル・作成者・日時を読む。

    存在しない場合や読めない場合は空の辞書を返す (致命的でないため)。
    """
    part = "docProps/core.xml"
    if not reader.has(part):
        return {}
    try:
        root = reader.read_xml(part)
    except Exception:  # noqa: BLE001 - メタデータの欠落は変換を止めない
        return {}
    fields = {
        "title": f"{{{NS['dc']}}}title",
        "author": f"{{{NS['dc']}}}creator",
        "created": f"{{{NS['dcterms']}}}created",
        "modified": f"{{{NS['dcterms']}}}modified",
    }
    result: dict[str, str] = {}
    for key, tag in fields.items():
        node = root.find(tag)
        if node is not None and node.text:
            result[key] = node.text.strip()
    return result


def parse_iso(value: str | None) -> datetime | None:
    """ISO 8601 の文字列を datetime にする。解析できなければ None。"""
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None
