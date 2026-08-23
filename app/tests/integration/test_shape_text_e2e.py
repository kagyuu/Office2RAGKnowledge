"""T002 結合テスト: 図形テキストの通し検証 (中核要求)。

利用者が最初に挙げた要求 (オートシェープから文字を抜き出す) が、
実ファイル → Markdown まで通しで成立することを検証する。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from office2ragknowledge import ConvertOptions, ShapeStyle, convert_file
from office2ragknowledge.ooxml.xml_utils import NS
from tests.helpers.compare import body_of
from tests.helpers.make_office import (
    add_sheet_drawing,
    docx_textbox_xml,
    inject_docx_body_xml,
    make_docx,
    make_pptx,
    make_xlsx,
)

XDR, A = NS["xdr"], NS["a"]


def excel_drawing(text: str, *, with_table: bool = False, with_empty: bool = False) -> str:
    table = (
        "<a:tbl>"
        "<a:tr><a:tc><a:t>A</a:t></a:tc><a:tc><a:t>B</a:t></a:tc></a:tr>"
        "<a:tr><a:tc><a:t>1</a:t></a:tc><a:tc><a:t>2</a:t></a:tc></a:tr>"
        "</a:tbl>"
        if with_table
        else ""
    )
    empty = (
        '<xdr:sp><xdr:nvSpPr><xdr:cNvPr name="空"/></xdr:nvSpPr>'
        "<xdr:txBody><a:p/></xdr:txBody></xdr:sp>"
        if with_empty
        else ""
    )
    return (
        f'<?xml version="1.0"?><xdr:wsDr xmlns:xdr="{XDR}" xmlns:a="{A}">'
        "<xdr:twoCellAnchor>"
        "<xdr:from><xdr:col>1</xdr:col><xdr:colOff>0</xdr:colOff>"
        "<xdr:row>2</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>"
        '<xdr:sp><xdr:nvSpPr><xdr:cNvPr name="注記1"/></xdr:nvSpPr>'
        '<a:prstGeom prst="wedgeRectCallout"/>'
        f"<xdr:txBody><a:p><a:r><a:t>{text}</a:t></a:r></a:p></xdr:txBody>"
        f"{table}</xdr:sp>{empty}"
        "</xdr:twoCellAnchor></xdr:wsDr>"
    )


@pytest.fixture
def shapes_xlsx(tmp_path: Path) -> Path:
    path = make_xlsx(
        tmp_path / "shapes.xlsx",
        {"S1": [["値1", "値2"], ["値3", "値4"]], "S2": [["別シート"]]},
    )
    add_sheet_drawing(path, 0, excel_drawing("承認は課長まで", with_empty=True))
    add_sheet_drawing(path, 1, excel_drawing("2枚目の注記"))
    return path


@pytest.fixture
def shapes_docx(tmp_path: Path) -> Path:
    path = make_docx(tmp_path / "shapes.docx", [("h1", "第1章"), ("p", "本文です。")])
    inject_docx_body_xml(path, docx_textbox_xml(["注意事項", "2段落目"]))
    return path


# 期待1〜3: Word の図形テキスト
def test_word_shape_text_appears(shapes_docx: Path) -> None:
    body = body_of(convert_file(shapes_docx).markdown)
    assert "注意事項" in body
    assert "> **[図形: テキストボックス]**" in body


def test_word_shape_text_is_not_duplicated(shapes_docx: Path) -> None:
    """mc:Choice / mc:Fallback の二重取得が起きないこと (ADR-003)。"""
    body = body_of(convert_file(shapes_docx).markdown)
    assert body.count("注意事項") == 1


def test_word_shape_paragraphs_are_separate(shapes_docx: Path) -> None:
    body = body_of(convert_file(shapes_docx).markdown)
    assert "> 注意事項" in body
    assert "> 2段落目" in body


# 期待7: アンカー段落の直後
def test_word_shape_follows_anchor(shapes_docx: Path) -> None:
    body = body_of(convert_file(shapes_docx).markdown)
    assert body.index("本文です。") < body.index("注意事項")


# 期待8〜10: Excel の両モードで章末に出る
def test_excel_shape_in_both_modes(shapes_xlsx: Path) -> None:
    result = convert_file(shapes_xlsx)
    for output in result.outputs:
        body = body_of(output.markdown)
        assert "承認は課長まで" in body, output.filename_suffix
        assert "@ B3" in body, output.filename_suffix


def test_excel_shape_is_at_chapter_end(shapes_xlsx: Path) -> None:
    for output in convert_file(shapes_xlsx).outputs:
        body = body_of(output.markdown)
        assert body.index("値1") < body.index("承認は課長まで")


def test_excel_shape_goes_to_correct_sheet(shapes_xlsx: Path) -> None:
    body = body_of(convert_file(shapes_xlsx).outputs[0].markdown)
    s1 = body.split("## S1")[1].split("## S2")[0]
    s2 = body.split("## S2")[1]
    assert "承認は課長まで" in s1
    assert "2枚目の注記" in s2


# 期待11: テキストなしの図形は現れない
def test_textless_shape_is_not_rendered(shapes_xlsx: Path) -> None:
    body = body_of(convert_file(shapes_xlsx).outputs[0].markdown)
    assert "図形: 図形" not in body or body.count("> **[図形") == 1


# 期待5: 図形内の表が引用の外に出る
def test_shape_table_outside_quote(tmp_path: Path) -> None:
    path = make_xlsx(tmp_path / "t.xlsx", {"S1": [["本文"]]})
    add_sheet_drawing(path, 0, excel_drawing("表つき", with_table=True))
    body = body_of(convert_file(path).outputs[0].markdown)
    assert "| A | B |" in body
    quote_lines = [ln for ln in body.splitlines() if ln.startswith(">")]
    assert not any("| A |" in ln for ln in quote_lines)


# 期待12: PowerPoint でプレースホルダが二重出力されない
def test_powerpoint_no_duplicate_title(tmp_path: Path) -> None:
    path = make_pptx(tmp_path / "p.pptx", [("重複しないタイトル", ["図形の本文"], None)])
    body = body_of(convert_file(path).markdown)
    assert body.count("重複しないタイトル") == 1


# 期待16: --no-shapes で消える (対照実験)
def test_no_shapes_option_removes_text(shapes_xlsx: Path, shapes_docx: Path) -> None:
    options = ConvertOptions(shapes=False)
    excel_body = body_of(convert_file(shapes_xlsx, options).outputs[0].markdown)
    word_body = body_of(convert_file(shapes_docx, options).markdown)
    assert "承認は課長まで" not in excel_body
    assert "注意事項" not in word_body


# 期待17/18: 体裁の切り替え
def test_shape_style_heading(shapes_docx: Path) -> None:
    options = ConvertOptions(shape_style=ShapeStyle.HEADING)
    body = body_of(convert_file(shapes_docx, options).markdown)
    assert "#### [図形]" in body


def test_shape_style_plain(shapes_docx: Path) -> None:
    options = ConvertOptions(shape_style=ShapeStyle.PLAIN)
    body = body_of(convert_file(shapes_docx, options).markdown)
    assert "注意事項" in body
    assert "[図形" not in body
