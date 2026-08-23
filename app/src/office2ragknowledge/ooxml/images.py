"""画像の代替テキストとバイナリの収集 (REQ-F-048, 049, 069, 070)。

**OCR は行わない** (REQ-F-070)。画像バイナリを解析せず、代替テキストと参照のみを
扱う。``images=NONE`` のときはバイナリを読まない (メモリ節約)。

出力ファイル名は ``{連番:04d}.{拡張子}`` とする。元の埋め込み名を使わないのは
冪等性のためである (P002 §5.11)。
"""

from __future__ import annotations

import posixpath

from lxml import etree

from ..models import ExtractedImage, Image, ImageMode
from .xml_utils import NS, qn
from .zip_reader import SafeZipReader

__all__ = ["ALLOWED_EXTENSIONS", "ImageCollector"]

#: 出力を許可する拡張子。外れるものは ``bin`` として扱う (P003 §4.2)。
ALLOWED_EXTENSIONS = frozenset(
    {"png", "jpg", "jpeg", "gif", "bmp", "tiff", "tif", "emf", "wmf", "svg"}
)


class ImageCollector:
    """文書内の画像を出現順に収集する。"""

    def __init__(self, reader: SafeZipReader, part_name: str, mode: ImageMode) -> None:
        self._reader = reader
        self._part_name = part_name
        self._mode = mode
        self._rels = reader.resolve_rels(part_name)
        self._index = 0
        self._seen: dict[str, ExtractedImage] = {}

    @property
    def images(self) -> tuple[ExtractedImage, ...]:
        """収集した画像バイナリ。``images=NONE`` のときは空。"""
        return tuple(self._seen.values())

    @property
    def count(self) -> int:
        """出現した画像の数 (重複参照を除く)。"""
        return self._index

    def collect(self, el: etree._Element) -> list[Image]:
        """要素配下の画像を ``Image`` ブロックにして返す。"""
        result: list[Image] = []
        for blip in el.iter(qn("a:blip")):
            rel_id = blip.get(f"{{{NS['r']}}}embed")
            if not rel_id:
                continue
            target = self._rels.get(rel_id)
            if not target:
                continue
            self._index += 1
            alt = self._alt_text(el, self._index)
            extension = _normalize_extension(target)
            if self._mode is ImageMode.EXTRACT and target not in self._seen:
                try:
                    data = self._reader.read(target)
                except Exception:  # noqa: BLE001 - 画像の欠落は変換を止めない
                    data = b""
                if data:
                    self._seen[target] = ExtractedImage(
                        media_ref=target,
                        data=data,
                        extension=extension,
                        index=self._index,
                    )
            result.append(
                Image(
                    alt_text=alt,
                    media_ref=target,
                    extension=extension,
                    index=self._index,
                )
            )
        return result

    @staticmethod
    def _alt_text(el: etree._Element, index: int) -> str:
        """代替テキストを得る。無ければ ``図{連番}`` (REQ-F-048)。"""
        for tag in ("wp:docPr", "xdr:cNvPr", "p:cNvPr", "a:cNvPr"):
            try:
                qualified = qn(tag)
            except KeyError:  # pragma: no cover
                continue
            for node in el.iter(qualified):
                descr = node.get("descr")
                if descr and descr.strip():
                    return str(descr).strip()
                name = node.get("name")
                if name and name.strip():
                    return str(name).strip()
        return f"図{index}"


def _normalize_extension(target: str) -> str:
    ext = posixpath.splitext(target)[1].lstrip(".").lower()
    return ext if ext in ALLOWED_EXTENSIONS else "bin"
