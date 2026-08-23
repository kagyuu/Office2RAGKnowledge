"""U004-T4 の単体テスト: 画像の代替テキストとバイナリ収集。

**OCR は行わない** (REQ-F-070)。画像バイナリを解析しない。
"""

from __future__ import annotations

from pathlib import Path

from office2ragknowledge.models import ImageMode
from office2ragknowledge.ooxml.images import ALLOWED_EXTENSIONS, ImageCollector
from office2ragknowledge.ooxml.xml_utils import NS, parse_xml
from office2ragknowledge.ooxml.zip_reader import SafeZipReader
from tests.helpers.make_office import zip_from_mapping

A, R, WP, REL = NS["a"], NS["r"], NS["wp"], NS["rel"]

RELS = f"""<?xml version="1.0"?>
<Relationships xmlns="{REL}">
  <Relationship Id="rId1" Type="http://x/image" Target="media/image1.png"/>
  <Relationship Id="rId2" Type="http://x/image" Target="media/image2.xyz"/>
</Relationships>"""


def drawing(rel_id: str = "rId1", *, descr: str | None = None, name: str | None = None) -> object:
    attrs = ""
    if descr is not None:
        attrs += f' descr="{descr}"'
    if name is not None:
        attrs += f' name="{name}"'
    xml = (
        f'<w:drawing xmlns:w="{NS["w"]}" xmlns:a="{A}" xmlns:r="{R}" xmlns:wp="{WP}">'
        f"<wp:inline><wp:docPr{attrs}/>"
        f'<a:graphic><a:graphicData><a:blip r:embed="{rel_id}"/>'
        "</a:graphicData></a:graphic></wp:inline></w:drawing>"
    )
    return parse_xml(xml.encode())


def make_pkg(tmp_path: Path) -> Path:
    return zip_from_mapping(
        tmp_path / "pkg.zip",
        {
            "word/document.xml": "<doc/>",
            "word/_rels/document.xml.rels": RELS,
            "word/media/image1.png": b"\x89PNG\r\n\x1a\n" + b"\x00" * 50,
            "word/media/image2.xyz": b"binary",
        },
    )


def collector(
    tmp_path: Path, mode: ImageMode = ImageMode.NONE
) -> tuple[ImageCollector, SafeZipReader]:
    reader = SafeZipReader(make_pkg(tmp_path))
    return ImageCollector(reader, "word/document.xml", mode), reader


# ケース1: descr が代替テキストになる
def test_descr_is_alt_text(tmp_path: Path) -> None:
    c, r = collector(tmp_path)
    images = c.collect(drawing(descr="組織図"))  # type: ignore[arg-type]
    r.close()
    assert images[0].alt_text == "組織図"


# ケース2: descr が無ければ name
def test_name_fallback(tmp_path: Path) -> None:
    c, r = collector(tmp_path)
    images = c.collect(drawing(name="図表1"))  # type: ignore[arg-type]
    r.close()
    assert images[0].alt_text == "図表1"


# ケース3: どちらも無ければ 図N
def test_index_fallback(tmp_path: Path) -> None:
    c, r = collector(tmp_path)
    images = c.collect(drawing())  # type: ignore[arg-type]
    r.close()
    assert images[0].alt_text == "図1"


# ケース4: NONE でバイナリを収集しない
def test_none_mode_does_not_read_binary(tmp_path: Path) -> None:
    c, r = collector(tmp_path, ImageMode.NONE)
    c.collect(drawing(descr="図"))  # type: ignore[arg-type]
    r.close()
    assert c.images == ()


# ケース5: EXTRACT でバイナリを収集する
def test_extract_mode_reads_binary(tmp_path: Path) -> None:
    c, r = collector(tmp_path, ImageMode.EXTRACT)
    c.collect(drawing(descr="図"))  # type: ignore[arg-type]
    r.close()
    assert len(c.images) == 1
    assert c.images[0].data.startswith(b"\x89PNG")
    assert c.images[0].extension == "png"


# ケース6: 許可外の拡張子は bin
def test_unknown_extension_becomes_bin(tmp_path: Path) -> None:
    c, r = collector(tmp_path, ImageMode.EXTRACT)
    images = c.collect(drawing("rId2", descr="謎"))  # type: ignore[arg-type]
    r.close()
    assert images[0].extension == "bin"
    assert "xyz" not in ALLOWED_EXTENSIONS


# ケース7: 同じ画像を2回参照しても ExtractedImage は1件
def test_duplicate_reference_is_collected_once(tmp_path: Path) -> None:
    c, r = collector(tmp_path, ImageMode.EXTRACT)
    c.collect(drawing(descr="1回目"))  # type: ignore[arg-type]
    c.collect(drawing(descr="2回目"))  # type: ignore[arg-type]
    r.close()
    assert len(c.images) == 1


# ケース8: 連番が出現順で、2回の実行で同じ (冪等性)
def test_index_is_stable(tmp_path: Path) -> None:
    results = []
    for _ in range(2):
        c, r = collector(tmp_path, ImageMode.EXTRACT)
        a = c.collect(drawing(descr="A"))  # type: ignore[arg-type]
        b = c.collect(drawing("rId2", descr="B"))  # type: ignore[arg-type]
        r.close()
        results.append([(i.alt_text, i.index) for i in a + b])
    assert results[0] == results[1]
    assert results[0] == [("A", 1), ("B", 2)]
