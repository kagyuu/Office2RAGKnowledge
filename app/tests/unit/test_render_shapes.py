"""U003-T3 の単体テスト: 図形テキストブロックの描画。"""

from __future__ import annotations

from datetime import UTC, datetime

from office2ragknowledge.models import (
    Cell,
    ConvertOptions,
    Document,
    DocumentFormat,
    DocumentMeta,
    InlineRun,
    ShapeParagraph,
    ShapeStyle,
    ShapeText,
    Sheet,
    SheetRow,
    Table,
    TableCell,
    TableRow,
)
from office2ragknowledge.render.excel_grid import ExcelGridRenderer
from office2ragknowledge.render.excel_table import ExcelTableRenderer
from office2ragknowledge.render.shapes import render_shape_block, render_shape_blocks

NOW = datetime(2026, 8, 24, tzinfo=UTC)


def mkshape(
    texts: list[str] | None = None,
    *,
    kind: str = "テキストボックス",
    anchor: str | None = None,
    group_path: tuple[str, ...] = (),
    levels: list[int] | None = None,
    tables: tuple[Table, ...] = (),
) -> ShapeText:
    texts = texts if texts is not None else ["図形のテキスト"]
    paras = tuple(
        ShapeParagraph(runs=(InlineRun(text=t),), level=(levels[i] if levels else 0))
        for i, t in enumerate(texts)
    )
    return ShapeText(
        shape_kind=kind,
        anchor=anchor,
        group_path=group_path,
        paragraphs=paras,
        tables=tables,
    )


def mktable() -> Table:
    return Table(
        rows=(
            TableRow(
                cells=(
                    TableCell(runs=(InlineRun(text="A"),)),
                    TableCell(runs=(InlineRun(text="B"),)),
                ),
                is_header=True,
            ),
            TableRow(
                cells=(
                    TableCell(runs=(InlineRun(text="1"),)),
                    TableCell(runs=(InlineRun(text="2"),)),
                ),
            ),
        )
    )


# ケース1: quote 体裁
def test_quote_style() -> None:
    out = render_shape_block(mkshape(), ShapeStyle.QUOTE)
    assert out.startswith("> **[図形: テキストボックス]**")
    assert "> 図形のテキスト" in out


# ケース2: anchor が付く
def test_anchor_is_shown() -> None:
    out = render_shape_block(mkshape(anchor="B3"), ShapeStyle.QUOTE)
    assert "> **[図形: テキストボックス @ B3]**" in out


# ケース3: グループ注記
def test_group_note() -> None:
    out = render_shape_block(mkshape(group_path=("業務フロー図",)), ShapeStyle.QUOTE)
    assert "(グループ「業務フロー図」内)" in out


# ケース4: 2階層のとき最も内側の名前が使われる
def test_group_note_uses_innermost() -> None:
    out = render_shape_block(mkshape(group_path=("外", "内")), ShapeStyle.QUOTE)
    assert "(グループ「内」内)" in out
    assert "「外」" not in out


# ケース5: 複数段落が段落ごとの引用行になる
def test_multiple_paragraphs_become_separate_lines() -> None:
    out = render_shape_block(mkshape(["1段落目", "2段落目"]), ShapeStyle.QUOTE)
    lines = out.splitlines()
    assert "> 1段落目" in lines
    assert "> 2段落目" in lines


# ケース6: heading 体裁
def test_heading_style() -> None:
    out = render_shape_block(mkshape(kind="四角形"), ShapeStyle.HEADING)
    assert out.startswith("#### [図形] 四角形")
    assert "> " not in out


# ケース7: plain 体裁
def test_plain_style() -> None:
    out = render_shape_block(mkshape(), ShapeStyle.PLAIN)
    assert out == "図形のテキスト"
    assert "[図形" not in out


# ケース8: 図形内の表が引用の外に出る
def test_table_is_outside_quote() -> None:
    out = render_shape_block(mkshape(kind="四角形", tables=(mktable(),)), ShapeStyle.QUOTE)
    quote_lines = [ln for ln in out.splitlines() if ln.startswith(">")]
    assert not any("|" in ln for ln in quote_lines), "引用行に表が含まれています"
    assert "| A | B |" in out


# ケース9: 表の直前に見出し行が出る
def test_table_has_label() -> None:
    out = render_shape_block(mkshape(kind="四角形", tables=(mktable(),)), ShapeStyle.QUOTE)
    assert "> **[図形: 四角形] 内の表**" in out


# ケース10: SmartArt が箇条書きになり level がインデントになる
def test_smartart_becomes_bullet_list() -> None:
    shape = mkshape(["計画", "実行", "評価"], kind="SmartArt", levels=[0, 1, 1])
    out = render_shape_block(shape, ShapeStyle.QUOTE)
    assert "> - 計画" in out
    assert ">   - 実行" in out


# ケース11: 行頭の # がエスケープされる
def test_escape_in_body() -> None:
    out = render_shape_block(mkshape(["# 見出し風"]), ShapeStyle.QUOTE)
    assert "> \\# 見出し風" in out


# ケース12: 空タプルで空文字
def test_empty_shapes() -> None:
    assert render_shape_blocks(()) == ""


# ケース13: 複数の図形が空行で区切られる
def test_multiple_shapes_separated_by_blank_line() -> None:
    out = render_shape_blocks((mkshape(["A"]), mkshape(["B"])), ShapeStyle.QUOTE)
    assert "\n\n" in out


# ケース14 (必須): 両モードで同じ図形ブロックが出力される (REQ-F-035)
def test_both_excel_modes_render_identical_shape_blocks() -> None:
    shape = mkshape(["承認は課長まで"], kind="吹き出し", anchor="H3")
    rows = (SheetRow(row_index=1, cells=(Cell(row=1, col=1, text="値"),)),)
    sheet = Sheet(name="S1", rows=rows, regions=(), shapes=(shape,), total_rows=1)
    meta = DocumentMeta(
        source_file="a.xlsx",
        source_path="a.xlsx",
        source_format=DocumentFormat.XLSX,
        source_size_bytes=0,
        source_sha256="",
        converter="test",
        converted_at=NOW,
    )
    doc = Document(format=DocumentFormat.XLSX, title="B", meta=meta, blocks=(sheet,))
    options = ConvertOptions()
    table_body, _, _ = ExcelTableRenderer().render(doc, options)
    grid_body, _, _ = ExcelGridRenderer().render(doc, options)

    expected = "> **[図形: 吹き出し @ H3]**\n> 承認は課長まで"
    assert expected in table_body
    assert expected in grid_body


def test_shape_block_is_at_end_of_chapter() -> None:
    """図形ブロックは章の末尾に出る (REQ-F-035)。"""
    shape = mkshape(["図形テキスト"])
    rows = (SheetRow(row_index=1, cells=(Cell(row=1, col=1, text="本文セル"),)),)
    from office2ragknowledge.parsers.excel_regions import detect_regions

    regions, _ = detect_regions(rows, [])
    sheet = Sheet(name="S1", rows=rows, regions=regions, shapes=(shape,), total_rows=1)
    meta = DocumentMeta(
        source_file="a.xlsx",
        source_path="a.xlsx",
        source_format=DocumentFormat.XLSX,
        source_size_bytes=0,
        source_sha256="",
        converter="test",
        converted_at=NOW,
    )
    doc = Document(format=DocumentFormat.XLSX, title="B", meta=meta, blocks=(sheet,))
    body, _, _ = ExcelTableRenderer().render(doc, ConvertOptions())
    assert body.index("本文セル") < body.index("図形テキスト")
