"""PDF を開き、ライブラリ非依存の型に変換する (P003 §4.4, §7A.2。※CR-001・CR-003)。

**PDF ライブラリ (pdfminer.six) を import してよいのはこのモジュールだけである**
(ADR-015)。※CR-003 で PyMuPDF (AGPL-3.0) から pdfminer.six (MIT) に差し替えた。
ライブラリを差し替えるときは、同じ ``PdfSource`` を返す ``open_pdf`` を書けばよい。

守るべき規則 (ArchitectureHandbook §4-9・§4-15〜4-17):

* 構造要素の経路は、親の ``/K`` 配列内の位置 (MCID の整数・MCR・OBJR も位置を
  占める) の列。文字には、その MCID が属する要素の経路と ``/K`` 内の位置を付ける。
* Artifact の内側の文字・構造ツリーから参照されない文字は ``path=None``。
* ライブラリの例外を外に漏らさない (``CorruptedFileError`` に変換する)。
* ライブラリのログと警告を利用者の出力に混ぜない (REQ-NF-014)。
"""

from __future__ import annotations

import io
import logging
import re
import warnings
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from importlib import metadata
from typing import Any

from pdfminer import utils as _pdf_utils
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LTChar, LTCurve, LTFigure, LTImage, LTLine, LTPage, LTRect
from pdfminer.pdfdocument import PDFDocument, PDFPasswordIncorrect
from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser
from pdfminer.pdftypes import PDFObjRef, PDFStream, resolve1
from pdfminer.psparser import PSLiteral

from ..errors import CorruptedFileError, Office2RagError, PasswordProtectedError
from ..ooxml.xml_utils import parse_xml
from .drawings import cluster_rects
from .model import PdfChar, PdfMetadata, PdfPage, PdfSource, Rect, StructInfo, StructPath
from .safety import check_inflated_sizes

__all__ = ["library_version", "open_pdf", "parse_pdf_date"]

logger = logging.getLogger(__name__)

# pdfminer.six は logging と warnings で警告を出す (本文の断片を含みうる)。ルート
# ロガーにハンドラが無い環境では標準エラーに出るため、伝播を止める (Handbook §4-16)。
_library_logger = logging.getLogger("pdfminer")
_library_logger.addHandler(logging.NullHandler())
_library_logger.propagate = False

#: 構造ツリーを辿る深さの上限 (細工された深い入れ子への備え)。
_MAX_DEPTH = 64

#: RoleMap を辿る回数の上限 (循環への備え)。
_MAX_ROLE_HOPS = 8

#: PDF 1.7 / 2.0 の標準構造タグ。RoleMap はこれに到達するまで辿る。
_STANDARD_TAGS = frozenset(
    {
        "Document", "DocumentFragment", "Part", "Art", "Sect", "Div", "BlockQuote",
        "Caption", "TOC", "TOCI", "Index", "NonStruct", "Private", "Aside",
        "P", "H", "H1", "H2", "H3", "H4", "H5", "H6", "Title", "FENote", "Sub",
        "L", "LI", "Lbl", "LBody", "Table", "TR", "TH", "TD", "THead", "TBody", "TFoot",
        "Span", "Quote", "Note", "Reference", "BibEntry", "Code", "Link", "Annot",
        "Ruby", "RB", "RT", "RP", "Warichu", "WT", "WP", "Em", "Strong",
        "Figure", "Formula", "Form", "Artifact",
    }
)  # fmt: skip

#: Unicode に対応しない文字 (``(cid:N)``) の置き換え先 (Handbook §4-17)。
_REPLACEMENT = "�"
_CID = re.compile(r"^\(cid:\d+\)$")

McidKey = tuple[int, int]
"""(ページのオブジェクト番号, MCID)。"""


def library_version() -> str:
    """PDF ライブラリの名前と版 (バージョン画面用)。"""
    try:
        version = metadata.version("pdfminer.six")
    except metadata.PackageNotFoundError:  # pragma: no cover - 導入されていれば必ずある
        version = "?"
    return f"pdfminer.six {version}"


def open_pdf(data: bytes) -> PdfSource:
    """PDF のバイト列を開いて ``PdfSource`` を返す (P003 §4.4 の手順1〜6)。

    Raises:
        PasswordProtectedError: 開くためのパスワードが設定されている (E-005)
        CorruptedFileError: PDF として読めない、またはページが無い (E-007)
        FileTooLargeError: 圧縮ストリームの展開後サイズが上限を超える (E-008)
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            return _read_document(data)
        except Office2RagError:
            raise
        except PDFPasswordIncorrect as exc:
            raise PasswordProtectedError("パスワードで保護されたファイルは変換できません") from exc
        except Exception as exc:  # noqa: BLE001 - ライブラリの例外を外に漏らさない
            raise CorruptedFileError("ファイルが破損しているため読み取れません") from exc


def _read_document(data: bytes) -> PdfSource:
    doc: Any = PDFDocument(PDFParser(io.BytesIO(data)), password="")
    pages: list[Any] = list(PDFPage.create_pages(doc))
    if not pages:
        raise CorruptedFileError("ファイルが破損しているため読み取れません")
    check_inflated_sizes(_flate_streams(doc))

    tree = _StructTree()
    try:
        tree.read(doc)
    except Exception:  # noqa: BLE001 - 構造ツリーが読めなくても、構造なしとして続ける
        logger.debug("構造ツリーを読み取れませんでした。構造なしとして変換します")
        tree = _StructTree()

    rsrc = PDFResourceManager()
    device = _MarkedContentDevice(rsrc)
    interpreter = PDFPageInterpreter(rsrc, device)
    out_pages = []
    for number, page in enumerate(pages, start=1):
        interpreter.process_page(page)
        out_pages.append(_convert_page(device.get_result(), number, int(page.pageid), tree))

    logger.debug("PDF を読み取りました (ページ数: %d)", len(out_pages))
    return PdfSource(
        pages=tuple(out_pages),
        struct=tree.infos,
        has_struct_tree=tree.present,
        metadata=_read_metadata(doc),
        copy_restricted=not bool(doc.is_extractable),
    )


def _flate_streams(doc: Any) -> Iterator[bytes]:
    """最初のフィルタが FlateDecode のストリームを、復号済み・未展開で返す。

    オブジェクトストリームの中のオブジェクト (ストリームを持てない) は読まない。
    読むと、そのオブジェクトストリームが上限なしで展開されるため。
    """
    seen: set[int] = set()
    for xref in doc.xrefs:
        for objid in xref.get_objids():
            if objid in seen:
                continue
            seen.add(objid)
            try:
                strmid, _index, _genno = xref.get_pos(objid)
                if strmid is not None:
                    continue
                obj = doc.getobj(objid)
            except Exception:  # noqa: BLE001 - 壊れたオブジェクトは描画時に扱う
                continue
            if not isinstance(obj, PDFStream):
                continue
            filters = obj.get_filters()
            if not filters or getattr(filters[0][0], "name", None) not in ("FlateDecode", "Fl"):
                continue
            raw = obj.rawdata
            if raw is None:
                continue
            if obj.decipher is not None and obj.objid is not None and obj.genno is not None:
                raw = obj.decipher(obj.objid, obj.genno, raw, obj.attrs)
            yield bytes(raw)


# ---------------------------------------------------------------------------
# 構造ツリー
# ---------------------------------------------------------------------------


def _name(obj: Any) -> str | None:
    obj = resolve1(obj)
    if isinstance(obj, PSLiteral):
        return str(obj.name)
    return None


def _text(obj: Any) -> str | None:
    obj = resolve1(obj)
    if isinstance(obj, bytes):
        return str(_pdf_utils.decode_text(obj))
    if isinstance(obj, str):
        return obj
    return None


@dataclass
class _StructTree:
    """構造ツリーを辿った結果 (P003 §7A.2 の変換手順1)。"""

    present: bool = False
    infos: dict[StructPath, StructInfo] = field(default_factory=dict)
    mcids: dict[McidKey, tuple[StructPath, int]] = field(default_factory=dict)
    """(ページのオブジェクト番号, MCID) → (要素の経路, ``/K`` 内の位置)。"""

    role_map: dict[str, Any] = field(default_factory=dict)
    seen: set[int] = field(default_factory=set)

    def read(self, doc: Any) -> None:
        root = resolve1(doc.catalog.get("StructTreeRoot"))
        if not isinstance(root, dict):
            return
        self.present = True
        role_map = resolve1(root.get("RoleMap"))
        self.role_map = role_map if isinstance(role_map, dict) else {}
        self._visit(root, None, None, 0)

    def _visit(
        self, elem: dict[str, Any], path: StructPath | None, page: int | None, depth: int
    ) -> None:
        """要素の ``/K`` を辿る。``path`` が None ならルート (StructTreeRoot)。"""
        if depth >= _MAX_DEPTH:
            return
        pg = elem.get("Pg")
        if isinstance(pg, PDFObjRef):
            page = int(pg.objid)
        kids_obj = elem.get("K")
        kids_resolved = resolve1(kids_obj)
        kids = kids_resolved if isinstance(kids_resolved, list) else [kids_obj]
        for index, kid in enumerate(kids):
            if isinstance(kid, PDFObjRef):
                if kid.objid in self.seen:
                    continue
                self.seen.add(int(kid.objid))
            value = resolve1(kid)
            if isinstance(value, int) and not isinstance(value, bool):
                if path is not None and page is not None:
                    self.mcids.setdefault((page, value), (path, index))
                continue
            if not isinstance(value, dict):
                continue
            kind = _name(value.get("Type"))
            if kind == "MCR":
                mcid = resolve1(value.get("MCID"))
                mcr_pg = value.get("Pg")
                mcr_page = int(mcr_pg.objid) if isinstance(mcr_pg, PDFObjRef) else page
                if path is not None and isinstance(mcid, int) and mcr_page is not None:
                    self.mcids.setdefault((mcr_page, mcid), (path, index))
                continue
            if kind == "OBJR":
                continue
            tag = _name(value.get("S"))
            if tag is None:
                continue
            child = (index,) if path is None else (*path, index)
            self.infos[child] = self._info(value, tag)
            self._visit(value, child, page, depth + 1)

    def _resolve_role(self, tag: str) -> str:
        current = tag
        for _ in range(_MAX_ROLE_HOPS):
            if current in _STANDARD_TAGS:
                return current
            mapped = _name(self.role_map.get(current))
            if mapped is None:
                return current
            current = mapped
        return current

    def _info(self, elem: dict[str, Any], raw_tag: str) -> StructInfo:
        alt = (_text(elem.get("Alt")) or "").strip()
        numbering: str | None = None
        col_span = 1
        row_span = 1
        for attrs in _attribute_dicts(elem.get("A")):
            value = _name(attrs.get("ListNumbering"))
            if value is not None:
                numbering = value
            span = resolve1(attrs.get("ColSpan"))
            if isinstance(span, int):
                col_span = max(1, span)
            span = resolve1(attrs.get("RowSpan"))
            if isinstance(span, int):
                row_span = max(1, span)
        return StructInfo(
            tag=self._resolve_role(raw_tag),
            alt=alt or None,
            list_numbering=numbering,
            col_span=min(col_span, 1000),
            row_span=min(row_span, 1000),
        )


def _attribute_dicts(obj: Any) -> list[dict[str, Any]]:
    """``/A`` は辞書、または辞書 (と改訂番号の整数) の配列でありうる。"""
    resolved = resolve1(obj)
    if isinstance(resolved, dict):
        return [resolved]
    if isinstance(resolved, list):
        return [item for item in (resolve1(x) for x in resolved) if isinstance(item, dict)]
    return []


# ---------------------------------------------------------------------------
# ページ (P003 §7A.2 の変換手順2〜5)
# ---------------------------------------------------------------------------


class _MarkedContentDevice(PDFPageAggregator):
    """マーク付きコンテンツの入れ子を追い、各文字に (MCID, Artifact か) を付ける。

    基底クラスは ``_stack`` を Form XObject の入れ子に使うため、別の名前で持つ。
    """

    def __init__(self, rsrcmgr: Any) -> None:
        super().__init__(rsrcmgr, laparams=None)
        self._marked: list[tuple[bool, int | None]] = []

    def begin_page(self, page: Any, ctm: Any) -> None:
        self._marked = []
        super().begin_page(page, ctm)

    def begin_tag(self, tag: Any, props: Any = None) -> None:
        name = tag.name if isinstance(tag, PSLiteral) else str(tag)
        mcid = None
        if isinstance(props, dict):
            value = resolve1(props.get("MCID"))
            if isinstance(value, int):
                mcid = value
        self._marked.append((name == "Artifact", mcid))

    def end_tag(self) -> None:
        if self._marked:
            self._marked.pop()

    def do_tag(self, tag: Any, props: Any = None) -> None:
        return

    def render_char(self, *args: Any, **kwargs: Any) -> float:
        adv: float = super().render_char(*args, **kwargs)
        item = self.cur_item._objs[-1]
        setattr(item, "o2r_artifact", any(flag for flag, _ in self._marked))  # noqa: B010
        mcid = next((m for _, m in reversed(self._marked) if m is not None), None)
        setattr(item, "o2r_mcid", mcid)  # noqa: B010
        return adv


def _iter_objects(container: Any) -> Iterator[Any]:
    for obj in container:
        yield obj
        if isinstance(obj, LTFigure):
            yield from _iter_objects(obj)


def _convert_page(layout: LTPage, number: int, pageid: int, tree: _StructTree) -> PdfPage:
    px0, py0, px1, py1 = layout.bbox
    chars: list[PdfChar] = []
    rects: list[Rect] = []
    images = 0
    for obj in _iter_objects(layout):
        if isinstance(obj, LTChar):
            raw = obj.get_text()
            text = _REPLACEMENT if _CID.match(raw) else raw
            if not text:
                continue
            path: StructPath | None = None
            kid_index: int | None = None
            mcid = getattr(obj, "o2r_mcid", None)
            if not getattr(obj, "o2r_artifact", False) and mcid is not None:
                found = tree.mcids.get((pageid, mcid))
                if found is not None:
                    path, kid_index = found
            chars.append(
                PdfChar(
                    text=text,
                    x0=float(obj.x0 - px0),
                    top=float(py1 - obj.y1),
                    x1=float(obj.x1 - px0),
                    bottom=float(py1 - obj.y0),
                    size=float(obj.size),
                    path=path,
                    kid_index=kid_index,
                )
            )
        elif isinstance(obj, (LTRect, LTLine, LTCurve)):
            rects.append(
                (float(obj.x0 - px0), float(py1 - obj.y1), float(obj.x1 - px0), float(py1 - obj.y0))
            )
        elif isinstance(obj, LTImage):
            images += 1
    return PdfPage(
        number=number,
        width=float(px1 - px0),
        height=float(py1 - py0),
        chars=tuple(chars),
        segments=((0, len(chars)),) if chars else (),
        figure_rects=tuple(cluster_rects(rects)),
        image_count=images,
    )


# ---------------------------------------------------------------------------
# メタデータ
# ---------------------------------------------------------------------------

_PDF_DATE = re.compile(
    r"^(?:D:)?(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?"
    r"(?:([Zz])|([+\-])(\d{2})'?(\d{2})?'?)?$"
)


def parse_pdf_date(value: str | None) -> datetime | None:
    """PDF の日付文字列 ``D:YYYYMMDDHHmmSS+HH'mm'`` を解析する。

    省略された要素は既定値 (月日は1、時刻は0) で補う。タイムゾーンが無ければ
    ``tzinfo`` を持たない。解析できなければ ``None``。
    """
    if not value:
        return None
    match = _PDF_DATE.match(value.strip())
    if match is None:
        return None
    year, month, day, hour, minute, second, zulu, sign, tz_h, tz_m = match.groups()
    tz: timezone | None = None
    if zulu:
        tz = UTC
    elif sign:
        offset = timedelta(hours=int(tz_h), minutes=int(tz_m or 0))
        tz = timezone(offset if sign == "+" else -offset)
    try:
        return datetime(
            int(year),
            int(month or 1),
            int(day or 1),
            int(hour or 0),
            int(minute or 0),
            int(second or 0),
            tzinfo=tz,
        )
    except ValueError:
        return None


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def _clean(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


_XMP_NS = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "xmp": "http://ns.adobe.com/xap/1.0/",
}


def _read_xmp(doc: Any) -> dict[str, str]:
    """XMP から title / creator / 日時を読む。読めなければ空の辞書。"""
    try:
        stream = resolve1(doc.catalog.get("Metadata"))
        if not isinstance(stream, PDFStream):
            return {}
        root = parse_xml(stream.get_data())
    except Exception:  # noqa: BLE001 - メタデータの欠落は変換を止めない
        return {}
    result: dict[str, str] = {}
    for key, xpath in (
        ("title", ".//dc:title//rdf:li"),
        ("author", ".//dc:creator//rdf:li"),
        ("created", ".//xmp:CreateDate"),
        ("modified", ".//xmp:ModifyDate"),
    ):
        found = root.findall(xpath, _XMP_NS)
        if found and found[0].text and found[0].text.strip():
            result[key] = found[0].text.strip()
    return result


def _read_metadata(doc: Any) -> PdfMetadata:
    info: dict[str, Any] = {}
    try:
        for entry in doc.info or []:
            if isinstance(entry, dict):
                info.update(entry)
    except Exception:  # noqa: BLE001 - メタデータの欠落は変換を止めない
        info = {}
    title = _clean(_text(info.get("Title")))
    author = _clean(_text(info.get("Author")))
    created = parse_pdf_date(_clean(_text(info.get("CreationDate"))))
    modified = parse_pdf_date(_clean(_text(info.get("ModDate"))))
    if title is None or author is None or created is None or modified is None:
        xmp = _read_xmp(doc)
        title = title or _clean(xmp.get("title"))
        author = author or _clean(xmp.get("author"))
        created = created or _parse_iso(xmp.get("created"))
        modified = modified or _parse_iso(xmp.get("modified"))
    return PdfMetadata(title=title, author=author, created_at=created, modified_at=modified)
