"""U004-T2 の単体テスト: PowerPoint パーサ。"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from office2ragknowledge.models import (
    ConvertOptions,
    DocumentFormat,
    ShapeText,
    SlideBreak,
)
from office2ragknowledge.ooxml.zip_reader import SafeZipReader
from office2ragknowledge.parsers.powerpoint import PowerPointParser
from tests.helpers.make_office import make_pptx

NOW = datetime(2026, 8, 24, 10, 0, 0, tzinfo=UTC)


def parse(path: Path, options: ConvertOptions | None = None):  # type: ignore[no-untyped-def]
    with SafeZipReader(path) as reader:
        return PowerPointParser().parse(reader, path.name, options or ConvertOptions(), NOW)


def slides_of(doc) -> list[SlideBreak]:  # type: ignore[no-untyped-def]
    return [b for b in doc.blocks if isinstance(b, SlideBreak)]


def all_text(doc) -> str:  # type: ignore[no-untyped-def]
    parts = []
    for block in doc.blocks:
        if isinstance(block, SlideBreak):
            parts.append(block.slide_title or "")
            parts.extend("".join(r.text for r in p.runs) for p in block.notes)
        elif isinstance(block, ShapeText):
            parts.extend("".join(r.text for r in p.runs) for p in block.paragraphs)
    return "\n".join(parts)


# ケース1: スライドごとに SlideBreak、番号は1起点
def test_slide_breaks_and_numbering(tmp_path: Path) -> None:
    path = make_pptx(
        tmp_path / "a.pptx",
        [("表紙", ["本文"], None), ("2枚目", [], None), ("3枚目", [], None)],
    )
    slides = slides_of(parse(path))
    assert [s.slide_number for s in slides] == [1, 2, 3]


# ケース2: タイトルが slide_title に入る
def test_slide_title(tmp_path: Path) -> None:
    path = make_pptx(tmp_path / "a.pptx", [("事業計画", [], None)])
    assert slides_of(parse(path))[0].slide_title == "事業計画"


# ケース3: タイトルが無ければ None
def test_no_title(tmp_path: Path) -> None:
    path = make_pptx(tmp_path / "a.pptx", [(None, ["本文のみ"], None)])
    assert slides_of(parse(path))[0].slide_title is None


# ケース6: notes=True でノートが入る
def test_notes_are_extracted(tmp_path: Path) -> None:
    path = make_pptx(tmp_path / "a.pptx", [("表紙", [], "補足説明です")])
    notes = slides_of(parse(path))[0].notes
    assert len(notes) >= 1
    assert "補足説明です" in "".join(r.text for p in notes for r in p.runs)


# ケース7: notes=False でノートが空
def test_notes_disabled(tmp_path: Path) -> None:
    path = make_pptx(tmp_path / "a.pptx", [("表紙", [], "補足説明です")])
    doc = parse(path, ConvertOptions(notes=False))
    assert slides_of(doc)[0].notes == ()


# ケース8: ノートが無いスライドで空タプル
def test_no_notes_slide(tmp_path: Path) -> None:
    path = make_pptx(tmp_path / "a.pptx", [("表紙", [], None)])
    assert slides_of(parse(path))[0].notes == ()


# ケース9: プレースホルダ以外の図形が ShapeText になる
def test_non_placeholder_shapes(tmp_path: Path) -> None:
    path = make_pptx(tmp_path / "a.pptx", [("表紙", ["図形の本文"], None)])
    doc = parse(path)
    shapes = [b for b in doc.blocks if isinstance(b, ShapeText)]
    assert len(shapes) >= 1
    assert "図形の本文" in all_text(doc)


# ケース10: タイトルプレースホルダが図形として二重出力されない (REQ-F-037)
def test_title_placeholder_is_not_duplicated(tmp_path: Path) -> None:
    path = make_pptx(tmp_path / "a.pptx", [("重複しないタイトル", [], None)])
    doc = parse(path)
    assert all_text(doc).count("重複しないタイトル") == 1
    shapes = [b for b in doc.blocks if isinstance(b, ShapeText)]
    shape_text = " ".join("".join(r.text for r in p.runs) for s in shapes for p in s.paragraphs)
    assert "重複しないタイトル" not in shape_text


# ケース11: レイアウト由来の図形が含まれない (REQ-F-046)
def test_layout_shapes_are_excluded(tmp_path: Path) -> None:
    """スライド本体のみを走査するため、マスター/レイアウトの文言は出ない。"""
    path = make_pptx(tmp_path / "a.pptx", [("タイトル", [], None)])
    doc = parse(path)
    text = all_text(doc)
    # 既定テンプレートのレイアウトにはプレースホルダのみで実文言は無いが、
    # 走査対象がスライド本体に限られていることを型で確認する
    assert "Click to edit" not in text
    assert "マスター" not in text


# ケース14: shapes=False で図形を抽出しない
def test_shapes_disabled(tmp_path: Path) -> None:
    path = make_pptx(tmp_path / "a.pptx", [("表紙", ["図形の本文"], None)])
    doc = parse(path, ConvertOptions(shapes=False))
    assert not any(isinstance(b, ShapeText) for b in doc.blocks)


def test_format_is_pptx(tmp_path: Path) -> None:
    path = make_pptx(tmp_path / "a.pptx", [("表紙", [], None)])
    assert parse(path).format is DocumentFormat.PPTX


def test_converted_at_is_injected(tmp_path: Path) -> None:
    path = make_pptx(tmp_path / "a.pptx", [("表紙", [], None)])
    assert parse(path).meta.converted_at == NOW


def test_slide_order_follows_presentation(tmp_path: Path) -> None:
    """スライドの順序は presentation.xml の並びに従う (_rels で解決)。"""
    path = make_pptx(tmp_path / "a.pptx", [("一枚目", [], None), ("二枚目", [], None)])
    titles = [s.slide_title for s in slides_of(parse(path))]
    assert titles == ["一枚目", "二枚目"]
