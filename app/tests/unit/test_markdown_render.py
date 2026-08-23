"""U004-T3 の単体テスト: Word / PowerPoint 共通レンダラ。"""

from __future__ import annotations

from datetime import UTC, datetime

from office2ragknowledge.models import (
    ConvertOptions,
    Document,
    DocumentFormat,
    DocumentMeta,
    Footnote,
    Heading,
    Image,
    ImageMode,
    InlineRun,
    ListBlock,
    ListItem,
    Paragraph,
    ShapeParagraph,
    ShapeText,
    SlideBreak,
    Table,
    TableCell,
    TableRow,
)
from office2ragknowledge.render import render_document
from office2ragknowledge.render.markdown import MarkdownRenderer

NOW = datetime(2026, 8, 24, tzinfo=UTC)


def mkdoc(*blocks, fmt=DocumentFormat.DOCX, title="文書", source="a.docx"):  # type: ignore[no-untyped-def]
    meta = DocumentMeta(
        source_file=source,
        source_path=source,
        source_format=fmt,
        source_size_bytes=0,
        source_sha256="",
        converter="test",
        converted_at=NOW,
        title=title,
    )
    return Document(format=fmt, title=title, meta=meta, blocks=blocks)


def render(doc, options=None):  # type: ignore[no-untyped-def]
    body, stats, _ = MarkdownRenderer().render(doc, options or ConvertOptions())
    return body, stats


def run(text: str, **kw: object) -> InlineRun:
    return InlineRun(text=text, **kw)  # type: ignore[arg-type]


# ケース1: 見出し
def test_heading() -> None:
    body, _ = render(mkdoc(Heading(level=2, runs=(run("章"),))))
    assert "## 章" in body


# ケース2/3: リストの階層と番号付き
def test_list_indent_and_ordered() -> None:
    items = (
        ListItem(runs=(run("親"),), level=0),
        ListItem(runs=(run("子"),), level=1),
        ListItem(runs=(run("番号"),), level=0, ordered=True),
    )
    body, _ = render(mkdoc(ListBlock(items=items)))
    assert "- 親" in body
    assert "  - 子" in body
    assert "1. 番号" in body


# ケース4: テーブル
def test_table() -> None:
    table = Table(
        rows=(
            TableRow(
                cells=(TableCell(runs=(run("A"),)), TableCell(runs=(run("B"),))),
                is_header=True,
            ),
            TableRow(cells=(TableCell(runs=(run("1"),)), TableCell(runs=(run("2"),)))),
        )
    )
    body, _ = render(mkdoc(table))
    assert "| A | B |" in body
    assert "| --- | --- |" in body


# ケース5: 書式
def test_inline_formatting() -> None:
    runs = (
        run("太字", bold=True),
        run("斜体", italic=True),
        run("取消", strike=True),
        run("コード", code=True),
    )
    body, _ = render(mkdoc(Paragraph(runs=runs)))
    assert "**太字**" in body
    assert "*斜体*" in body
    assert "~~取消~~" in body
    assert "`コード`" in body


# ケース6: リンク
def test_link() -> None:
    body, _ = render(mkdoc(Paragraph(runs=(run("公式", link_url="https://example.com"),))))
    assert "[公式](https://example.com)" in body


# ケース7/8: 脚注が末尾に移送される (INV-04)
def test_footnote_moved_to_end() -> None:
    body, _ = render(
        mkdoc(Paragraph(runs=(run("本文"),)), Footnote(marker="1", runs=(run("脚注本文"),)))
    )
    assert "## 脚注" in body
    assert "[^1]: 脚注本文" in body
    assert body.index("本文") < body.index("## 脚注")


def test_no_footnote_section_when_empty() -> None:
    body, _ = render(mkdoc(Paragraph(runs=(run("本文"),))))
    assert "## 脚注" not in body


# ケース9/10: 位置不明の図形が末尾に移送される
def test_unanchored_shape_moved_to_end() -> None:
    shape = ShapeText(
        shape_kind="テキストボックス",
        anchor=None,
        paragraphs=(ShapeParagraph(runs=(run("位置不明"),)),),
    )
    body, _ = render(mkdoc(Paragraph(runs=(run("本文"),)), shape))
    assert "## 図形テキスト (位置不明)" in body
    assert body.index("本文") < body.index("## 図形テキスト")


def test_anchored_shape_stays_in_place() -> None:
    shape = ShapeText(
        shape_kind="テキストボックス",
        anchor="B3",
        paragraphs=(ShapeParagraph(runs=(run("位置あり"),)),),
    )
    body, _ = render(mkdoc(shape, Paragraph(runs=(run("あとの本文"),))))
    assert "## 図形テキスト (位置不明)" not in body
    assert body.index("位置あり") < body.index("あとの本文")


# ケース11/12: スライド見出し
def test_slide_heading() -> None:
    body, _ = render(mkdoc(SlideBreak(slide_number=1, slide_title="表紙"), fmt=DocumentFormat.PPTX))
    assert "## スライド 1: 表紙" in body


def test_slide_heading_without_title() -> None:
    body, _ = render(mkdoc(SlideBreak(slide_number=2, slide_title=None), fmt=DocumentFormat.PPTX))
    assert "## スライド 2" in body
    assert "スライド 2:" not in body


# ケース13: ノート
def test_notes_section() -> None:
    slide = SlideBreak(
        slide_number=1,
        slide_title="表紙",
        notes=(ShapeParagraph(runs=(run("発表者メモ"),)),),
    )
    body, _ = render(mkdoc(slide, fmt=DocumentFormat.PPTX))
    assert "### ノート" in body
    assert "発表者メモ" in body


# ケース14/15: 画像
def test_image_placeholder() -> None:
    body, _ = render(mkdoc(Image(alt_text="構成図", media_ref="word/media/i.png", index=1)))
    assert "![構成図](画像は出力されていません)" in body


def test_image_extract_path() -> None:
    body, _ = render(
        mkdoc(Image(alt_text="構成図", media_ref="word/media/i.png", extension="png", index=1)),
        ConvertOptions(images=ImageMode.EXTRACT),
    )
    assert "![構成図](./a_assets/0001.png)" in body


# ケース16/17: render_document が1件を返す
def test_render_document_docx() -> None:
    outputs = render_document(
        mkdoc(Paragraph(runs=(run("本文"),))), ConvertOptions(front_matter=False)
    )
    assert len(outputs) == 1
    assert outputs[0].mode is None
    assert outputs[0].filename_suffix == ".md"


def test_render_document_pptx() -> None:
    outputs = render_document(
        mkdoc(SlideBreak(slide_number=1), fmt=DocumentFormat.PPTX, source="a.pptx"),
        ConvertOptions(front_matter=False),
    )
    assert len(outputs) == 1
    assert outputs[0].filename_suffix == ".md"


# ケース18/19
def test_document_title_and_no_blank_runs() -> None:
    body, _ = render(mkdoc(Paragraph(runs=(run("本文"),)), title="規程集"))
    assert body.startswith("# 規程集")
    assert "\n\n\n" not in body


def test_stats_word() -> None:
    _, stats = render(mkdoc(Heading(level=2, runs=(run("章"),)), Paragraph(runs=(run("本文"),))))
    assert stats["headings"] == 1
    assert stats["paragraphs"] == 1
    assert "slides" not in stats


def test_stats_pptx() -> None:
    _, stats = render(
        mkdoc(SlideBreak(slide_number=1), SlideBreak(slide_number=2), fmt=DocumentFormat.PPTX)
    )
    assert stats["slides"] == 2
