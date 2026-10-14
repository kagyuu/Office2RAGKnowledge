"""テスト用の PDF をバイト列として直接組み立てるヘルパ (P006 §3.4。※CR-001)。

PDF 生成ライブラリはタグ付き PDF の構造を細かく制御できず、外部ツールは環境に
依存するため、PDF の構文を直接書き出す。フォントは Type0 (Identity-H) +
``ToUnicode`` とし、日本語を含む任意の文字を埋め込みフォント無しで抽出できる
ようにする (文字コード = UTF-16BE の値。BMP の文字のみ)。

使い方::

    pages = [Page(items=[Text(50, 750, "見出し", 18, mcid=0), Text(50, 700, "本文", 12, mcid=1)])]
    tree = Elem("Document", [Elem("H1", [(0, 0)]), Elem("P", [(0, 1)])])
    data = build_pdf(pages, tree, title="題名")

座標 ``y`` は PDF の座標系 (ページ下端が 0) で与える。
"""

from __future__ import annotations

import io
import zlib
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "Elem",
    "Page",
    "Text",
    "build_pdf",
    "encrypt_pdf",
    "flate_bomb_pdf",
    "write_pdf",
]


@dataclass
class Text:
    """ページ上の1つの文字列。"""

    x: float
    y: float
    text: str
    size: float = 12
    mcid: int | None = None
    """構造要素から参照されるマーク付きコンテンツの ID。"""

    artifact: str | None = None
    """``"Header"`` / ``"Footer"`` で Pagination の Artifact、``""`` でその他の Artifact。"""

    in_form: bool = False
    """真なら Form XObject の中に描き、ページの内容からは ``Do`` で呼ぶ (※CR-003)。"""


@dataclass
class Page:
    """1ページ。"""

    items: list[Text] = field(default_factory=list)
    rects: list[tuple[float, float, float, float]] = field(default_factory=list)
    """枠線 (x, y, 幅, 高さ)。PDF 座標系。"""

    width: float = 595
    height: float = 842
    image: bool = False
    """1x1 の画像を1つ描く (文字を持たないスキャンページの模擬)。"""


@dataclass
class Elem:
    """構造要素。``kids`` は子要素または ``(ページ番号0起点, MCID)``。"""

    tag: str
    kids: list[Elem | tuple[int, int]] = field(default_factory=list)
    alt: str | None = None
    extra: str = ""
    """辞書に追加するエントリ (例: ``" /A << /O /List /ListNumbering /Decimal >>"``)。"""


def _code_hex(s: str) -> str:
    return "<" + s.encode("utf-16-be").hex().upper() + ">"


def _text_string(s: str) -> str:
    return "<FEFF" + s.encode("utf-16-be").hex().upper() + ">"


def _stream(data: bytes, compress: bool, extra: str = "") -> bytes:
    if compress:
        data = zlib.compress(data, 9)
        extra += " /Filter /FlateDecode"
    return b"<< /Length %d%s >>\nstream\n" % (len(data), extra.encode()) + data + b"\nendstream"


def build_pdf(
    pages: list[Page],
    struct: Elem | None = None,
    *,
    title: str | None = None,
    author: str | None = None,
    mcr: bool = False,
    compress: bool = False,
    role_map: dict[str, str] | None = None,
    extra_objects: list[bytes] | None = None,
) -> bytes:
    """PDF を組み立てる。

    Args:
        pages: ページの並び
        struct: 構造ツリーのルート要素。``None`` ならタグなし PDF
        mcr: 構造要素から MCID を MCR 辞書で参照する (既定は整数 + 要素の ``/Pg``)
        compress: 内容ストリームを Flate で圧縮する
        role_map: ``RoleMap`` (独自タグ → 標準タグ)
        extra_objects: 追加の間接オブジェクト (本体のバイト列)。参照されない
    """
    objs: list[bytes] = []

    def add(body: bytes | str) -> int:
        objs.append(body.encode("latin-1") if isinstance(body, str) else body)
        return len(objs)

    codes = sorted({ord(c) for p in pages for t in p.items for c in t.text} | {0x20})
    cmap_body = "\n".join(f"<{c:04X}> <{c:04X}>" for c in codes)
    cmap = (
        "/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
        "/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n"
        "1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n"
        f"{len(codes)} beginbfchar\n{cmap_body}\nendbfchar\n"
        "endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n"
    ).encode()
    tounicode = add(_stream(cmap, False))
    desc = add(
        "<< /Type /FontDescriptor /FontName /TestFont /Flags 32 /FontBBox [0 -200 1000 900]"
        " /ItalicAngle 0 /Ascent 900 /Descent -200 /CapHeight 700 /StemV 80 >>"
    )
    cid = add(
        "<< /Type /Font /Subtype /CIDFontType2 /BaseFont /TestFont /CIDSystemInfo"
        f" << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> /FontDescriptor {desc} 0 R"
        " /DW 1000 /CIDToGIDMap /Identity >>"
    )
    font = add(
        "<< /Type /Font /Subtype /Type0 /BaseFont /TestFont /Encoding /Identity-H"
        f" /DescendantFonts [{cid} 0 R] /ToUnicode {tounicode} 0 R >>"
    )
    image = add(
        _stream(
            b"\x80",
            False,
            " /Type /XObject /Subtype /Image /Width 1 /Height 1"
            " /ColorSpace /DeviceGray /BitsPerComponent 8",
        )
    )

    pages_id = add("")
    page_ids: list[int] = []
    form_count = 0
    for idx, page in enumerate(pages):
        ops: list[str] = []
        forms: list[str] = []
        for x, y, w, h in page.rects:
            ops.append(f"{x} {y} {w} {h} re S")
        if page.image:
            ops.append(f"q {page.width - 100} 0 0 {page.height - 100} 50 50 cm /Im1 Do Q")
        for t in page.items:
            if t.artifact is not None:
                if t.artifact in ("Header", "Footer"):
                    ops.append(f"/Artifact << /Type /Pagination /Subtype /{t.artifact} >> BDC")
                else:
                    ops.append("/Artifact BMC")
            elif t.mcid is not None:
                ops.append(f"/Span << /MCID {t.mcid} >> BDC")
            show = f"BT /F1 {t.size} Tf {t.x} {t.y} Td {_code_hex(t.text)} Tj ET"
            if t.in_form:
                form_count += 1
                form_id = add(
                    _stream(
                        show.encode(),
                        compress,
                        f" /Type /XObject /Subtype /Form /BBox [0 0 {page.width} {page.height}]"
                        f" /Resources << /Font << /F1 {font} 0 R >> >>",
                    )
                )
                forms.append(f"/Fm{form_count} {form_id} 0 R")
                ops.append(f"/Fm{form_count} Do")
            else:
                ops.append(show)
            if t.artifact is not None or t.mcid is not None:
                ops.append("EMC")
        content_id = add(_stream("\n".join(ops).encode(), compress))
        struct_parents = f" /StructParents {idx}" if struct is not None else ""
        page_ids.append(
            add(
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {page.width} {page.height}]"
                f" /Resources << /Font << /F1 {font} 0 R >>"
                f" /XObject << /Im1 {image} 0 R {' '.join(forms)} >> >>"
                f" /Contents {content_id} 0 R{struct_parents} >>"
            )
        )
    objs[pages_id - 1] = (
        f"<< /Type /Pages /Kids [{' '.join(f'{i} 0 R' for i in page_ids)}]"
        f" /Count {len(page_ids)} >>"
    ).encode()

    catalog_extra = ""
    if struct is not None:
        root_id = add("")
        parent_tree: dict[int, dict[int, int]] = {}

        def emit(elem: Elem, parent: int) -> int:
            me = add("")
            refs: list[str] = []
            page_ref = ""
            # 整数の MCID は要素の /Pg のページを指す (PDF 仕様)。/Pg は最初の MCID のページとし、
            # 別のページの MCID は MCR 辞書で書く (※CR-003 で仕様どおりに修正)
            first_page = next((k[0] for k in elem.kids if not isinstance(k, Elem)), None)
            for kid in elem.kids:
                if isinstance(kid, Elem):
                    refs.append(f"{emit(kid, me)} 0 R")
                    continue
                page_index, mcid = kid
                if mcr or page_index != first_page:
                    refs.append(f"<< /Type /MCR /Pg {page_ids[page_index]} 0 R /MCID {mcid} >>")
                else:
                    refs.append(str(mcid))
                    page_ref = f" /Pg {page_ids[page_index]} 0 R"
                parent_tree.setdefault(page_index, {})[mcid] = me
            alt = f" /Alt {_text_string(elem.alt)}" if elem.alt else ""
            objs[me - 1] = (
                f"<< /Type /StructElem /S /{elem.tag} /P {parent} 0 R{page_ref}"
                f" /K [{' '.join(refs)}]{alt}{elem.extra} >>"
            ).encode()
            return me

        doc_id = emit(struct, root_id)
        nums = []
        for page_index in sorted(parent_tree):
            mapping = parent_tree[page_index]
            arr = " ".join(
                f"{mapping[m]} 0 R" if m in mapping else "null" for m in range(max(mapping) + 1)
            )
            nums.append(f"{page_index} [{arr}]")
        roles = ""
        if role_map:
            roles = " /RoleMap << " + " ".join(f"/{k} /{v}" for k, v in role_map.items()) + " >>"
        objs[root_id - 1] = (
            f"<< /Type /StructTreeRoot /K {doc_id} 0 R"
            f" /ParentTree << /Nums [{' '.join(nums)}] >>{roles} >>"
        ).encode()
        catalog_extra = f" /StructTreeRoot {root_id} 0 R /MarkInfo << /Marked true >>"
    for body in extra_objects or []:
        add(body)
    catalog = add(f"<< /Type /Catalog /Pages {pages_id} 0 R{catalog_extra} >>")
    info_parts = []
    if title:
        info_parts.append(f"/Title {_text_string(title)}")
    if author:
        info_parts.append(f"/Author {_text_string(author)}")
    info_parts.append("/CreationDate (D:20260401090000+09'00')")
    info = add(f"<< {' '.join(info_parts)} >>")

    out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objs) + 1} /Root {catalog} 0 R /Info {info} 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n"
    ).encode()
    return bytes(out)


def write_pdf(path: Path, pages: list[Page], struct: Elem | None = None, **kwargs: object) -> Path:
    """``build_pdf`` の結果をファイルに書く。"""
    path.write_bytes(build_pdf(pages, struct, **kwargs))  # type: ignore[arg-type]
    return path


def encrypt_pdf(
    data: bytes, *, user: str = "", owner: str = "owner", copy_allowed: bool = True
) -> bytes:
    """pypdf で暗号化する。``user`` が空なら所有者パスワードのみ (開くのにパスワード不要)。

    ``/P`` (権限) は仕様どおりの値を用いる (0 は仕様外。ArchitectureHandbook §4-12)。
    """
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(data)))
    permissions = -3904 if not copy_allowed else -4  # -3904: 印刷・コピー等を禁止
    writer.encrypt(
        user_password=user, owner_password=owner, algorithm="AES-128", permissions_flag=permissions
    )
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def flate_bomb_pdf(inflated_size: int) -> bytes:
    """``inflated_size`` バイトに展開される Flate ストリームを持つ PDF を返す。"""
    raw = zlib.compress(b"0" * inflated_size, 9)
    bomb = b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(raw) + raw + b"\nendstream"
    return build_pdf([Page(items=[Text(50, 750, "bomb")])], extra_objects=[bomb])
