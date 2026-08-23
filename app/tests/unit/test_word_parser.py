"""U004-T1 の単体テスト: Word パーサ。"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from office2ragknowledge.models import (
    ConvertOptions,
    DocumentFormat,
    Footnote,
    Heading,
    ListBlock,
    Paragraph,
    ShapeText,
)
from office2ragknowledge.ooxml.zip_reader import SafeZipReader
from office2ragknowledge.parsers.word import WordParser
from tests.helpers.make_office import (
    docx_revision_xml,
    docx_textbox_xml,
    inject_docx_body_xml,
    make_docx,
)

NOW = datetime(2026, 8, 24, 10, 0, 0, tzinfo=UTC)


def parse(path: Path, options: ConvertOptions | None = None):  # type: ignore[no-untyped-def]
    with SafeZipReader(path) as reader:
        return WordParser().parse(reader, path.name, options or ConvertOptions(), NOW)


def texts_of(doc) -> str:  # type: ignore[no-untyped-def]
    out = []
    for block in doc.blocks:
        if isinstance(block, (Heading, Paragraph)):
            out.append("".join(r.text for r in block.runs))
        elif isinstance(block, ListBlock):
            out.extend("".join(r.text for r in i.runs) for i in block.items)
        elif isinstance(block, ShapeText):
            out.extend("".join(r.text for r in p.runs) for p in block.paragraphs)
    return "\n".join(out)


# ケース1: 見出し1が level=2 になる (1繰り下げ)
def test_heading_level_is_shifted(tmp_path: Path) -> None:
    doc = parse(make_docx(tmp_path / "a.docx", [("h1", "第1章")]))
    heading = next(b for b in doc.blocks if isinstance(b, Heading))
    assert heading.level == 2


# ケース2: 見出し5以上が 6 に丸められる
def test_deep_heading_is_clamped(tmp_path: Path) -> None:
    doc = parse(make_docx(tmp_path / "a.docx", [("h5", "深い見出し")]))
    heading = next(b for b in doc.blocks if isinstance(b, Heading))
    assert heading.level == 6


# ケース3/4: 箇条書きが ListBlock になり、連続するものがまとまる
def test_bullets_become_single_list_block(tmp_path: Path) -> None:
    doc = parse(
        make_docx(
            tmp_path / "a.docx",
            [("bullet", "項目A"), ("bullet", "項目B"), ("p", "本文")],
        )
    )
    lists = [b for b in doc.blocks if isinstance(b, ListBlock)]
    assert len(lists) == 1
    assert len(lists[0].items) == 2
    assert [i.runs[0].text for i in lists[0].items] == ["項目A", "項目B"]


# ケース5: 番号付きリストで ordered=True
def test_numbered_list(tmp_path: Path) -> None:
    doc = parse(make_docx(tmp_path / "a.docx", [("number", "手順1")]))
    lists = [b for b in doc.blocks if isinstance(b, ListBlock)]
    assert lists[0].items[0].ordered is True


# ケース10: 変更履歴 — 挿入は採用、削除は除外 (REQ-F-018)
def test_revisions_are_applied(tmp_path: Path) -> None:
    path = make_docx(tmp_path / "a.docx", [("p", "先頭")])
    inject_docx_body_xml(path, docx_revision_xml("追加された文", "削除された文"))
    text = texts_of(parse(path))
    assert "追加された文" in text
    assert "削除された文" not in text


# ケース15: 図形テキストがアンカー段落の直後に入る (REQ-F-036)
def test_shape_text_follows_anchor_paragraph(tmp_path: Path) -> None:
    path = make_docx(tmp_path / "a.docx", [("p", "本文1"), ("p", "本文2")])
    inject_docx_body_xml(path, docx_textbox_xml(["注意事項です"]))
    doc = parse(path)
    shapes = [b for b in doc.blocks if isinstance(b, ShapeText)]
    assert len(shapes) == 1
    assert shapes[0].paragraphs[0].runs[0].text == "注意事項です"


def test_shape_text_is_not_double_extracted(tmp_path: Path) -> None:
    """mc:Choice / mc:Fallback の二重取得が起きないこと (ADR-003)。"""
    path = make_docx(tmp_path / "a.docx", [("p", "本文")])
    inject_docx_body_xml(path, docx_textbox_xml(["一度だけ"]))
    text = texts_of(parse(path))
    assert text.count("一度だけ") == 1


def test_shape_text_is_not_in_body_paragraphs(tmp_path: Path) -> None:
    """図形内テキストが通常段落として二重に出ないこと。"""
    path = make_docx(tmp_path / "a.docx", [("p", "通常段落")])
    inject_docx_body_xml(path, docx_textbox_xml(["図形の中身"]))
    doc = parse(path)
    paragraphs = ["".join(r.text for r in b.runs) for b in doc.blocks if isinstance(b, Paragraph)]
    assert "図形の中身" not in paragraphs


# ケース16: shapes=False で図形を抽出しない
def test_shapes_option_disabled(tmp_path: Path) -> None:
    path = make_docx(tmp_path / "a.docx", [("p", "本文")])
    inject_docx_body_xml(path, docx_textbox_xml(["図形テキスト"]))
    doc = parse(path, ConvertOptions(shapes=False))
    assert not any(isinstance(b, ShapeText) for b in doc.blocks)


# ケース18: 文書タイトルはファイル名にフォールバックする
def test_title_falls_back_to_filename(tmp_path: Path) -> None:
    doc = parse(make_docx(tmp_path / "規程集.docx", [("p", "本文")]))
    assert doc.title == "規程集"


# ケース19: converted_at が引数の値
def test_converted_at_is_injected(tmp_path: Path) -> None:
    doc = parse(make_docx(tmp_path / "a.docx", [("p", "本文")]))
    assert doc.meta.converted_at == NOW


def test_format_is_docx(tmp_path: Path) -> None:
    doc = parse(make_docx(tmp_path / "a.docx", [("p", "本文")]))
    assert doc.format is DocumentFormat.DOCX


def test_empty_paragraphs_are_skipped(tmp_path: Path) -> None:
    doc = parse(make_docx(tmp_path / "a.docx", [("p", ""), ("p", "本文")]))
    paragraphs = [b for b in doc.blocks if isinstance(b, Paragraph)]
    assert len(paragraphs) == 1


def test_no_footnotes_when_absent(tmp_path: Path) -> None:
    doc = parse(make_docx(tmp_path / "a.docx", [("p", "本文")]))
    assert not any(isinstance(b, Footnote) for b in doc.blocks)


def test_block_order_is_preserved(tmp_path: Path) -> None:
    """blocks の順序が本文の出現順である (INV-04)。"""
    doc = parse(
        make_docx(
            tmp_path / "a.docx",
            [("h1", "章"), ("p", "段落1"), ("bullet", "項目"), ("p", "段落2")],
        )
    )
    kinds = [type(b).__name__ for b in doc.blocks]
    assert kinds == ["Heading", "Paragraph", "ListBlock", "Paragraph"]
