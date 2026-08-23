"""U003-T4 の単体テスト: Excel への図形の組み込み (REQ-F-035)。

openpyxl は図形を作れないため、生成した ``.xlsx`` の ZIP に drawing パートと
関係ファイルを注入してテストする。
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from office2ragknowledge.models import ConvertOptions, ExcelOptions, Sheet
from office2ragknowledge.ooxml.xml_utils import NS
from office2ragknowledge.ooxml.zip_reader import SafeZipReader
from office2ragknowledge.parsers.excel import ExcelParser
from office2ragknowledge.render.excel_grid import ExcelGridRenderer
from office2ragknowledge.render.excel_table import ExcelTableRenderer
from tests.helpers.make_office import add_sheet_drawing, make_xlsx

NOW = datetime(2026, 8, 24, tzinfo=UTC)
XDR, A = NS["xdr"], NS["a"]


def drawing_xml(
    *,
    col: int = 1,
    row: int = 2,
    text: str = "承認は課長まで",
    anchor_tag: str = "twoCellAnchor",
    with_empty_shape: bool = False,
) -> str:
    """図形1つ (必要なら空図形も) を含む drawing XML を作る。

    ``xdr:col`` / ``xdr:row`` は **0起点** である。
    """
    from_el = (
        f"<xdr:from><xdr:col>{col}</xdr:col><xdr:colOff>0</xdr:colOff>"
        f"<xdr:row>{row}</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>"
        if anchor_tag != "absoluteAnchor"
        else ""
    )
    empty = (
        '<xdr:sp><xdr:nvSpPr><xdr:cNvPr name="空図形"/></xdr:nvSpPr>'
        "<xdr:txBody><a:p/></xdr:txBody></xdr:sp>"
        if with_empty_shape
        else ""
    )
    return (
        f'<?xml version="1.0"?>'
        f'<xdr:wsDr xmlns:xdr="{XDR}" xmlns:a="{A}">'
        f"<xdr:{anchor_tag}>{from_el}"
        f'<xdr:sp><xdr:nvSpPr><xdr:cNvPr name="吹き出し1"/></xdr:nvSpPr>'
        f'<a:prstGeom prst="wedgeRectCallout"/>'
        f"<xdr:txBody><a:p><a:r><a:t>{text}</a:t></a:r></a:p></xdr:txBody></xdr:sp>"
        f"{empty}"
        f"</xdr:{anchor_tag}>"
        f"</xdr:wsDr>"
    )


def build(tmp_path: Path, **kwargs: object) -> Path:
    path = make_xlsx(tmp_path / "a.xlsx", {"S1": [["値1", "値2"], ["値3", "値4"]]})
    add_sheet_drawing(path, 0, drawing_xml(**kwargs))  # type: ignore[arg-type]
    return path


def parse(path: Path, options: ConvertOptions | None = None) -> Sheet:
    with SafeZipReader(path) as reader:
        doc = ExcelParser().parse(reader, path.name, options or ConvertOptions(), NOW)
    return next(b for b in doc.blocks if isinstance(b, Sheet))


# ケース1: 図形を持つシートで shapes が非空
def test_shapes_are_extracted(tmp_path: Path) -> None:
    sheet = parse(build(tmp_path))
    assert len(sheet.shapes) == 1
    assert sheet.shapes[0].paragraphs[0].runs[0].text == "承認は課長まで"


# ケース2: アンカーの 0起点 → 1起点 変換 (col=1, row=2 → B3)
def test_anchor_is_converted_from_zero_based(tmp_path: Path) -> None:
    sheet = parse(build(tmp_path, col=1, row=2))
    assert sheet.shapes[0].anchor == "B3"


def test_anchor_a1(tmp_path: Path) -> None:
    sheet = parse(build(tmp_path, col=0, row=0))
    assert sheet.shapes[0].anchor == "A1"


# ケース3: absoluteAnchor は anchor=None
def test_absolute_anchor_has_no_ref(tmp_path: Path) -> None:
    sheet = parse(build(tmp_path, anchor_tag="absoluteAnchor"))
    assert sheet.shapes[0].anchor is None


# ケース4: _rels で解決するため、シート順とファイル名が一致しなくても正しく付く
def test_drawing_is_resolved_via_rels(tmp_path: Path) -> None:
    path = make_xlsx(tmp_path / "multi.xlsx", {"一枚目": [["a"]], "二枚目": [["b"]]})
    # 2枚目 (sheet2.xml) に図形を付ける
    add_sheet_drawing(path, 1, drawing_xml(text="二枚目の図形"))
    with SafeZipReader(path) as reader:
        doc = ExcelParser().parse(reader, path.name, ConvertOptions(), NOW)
    sheets = [b for b in doc.blocks if isinstance(b, Sheet)]
    assert sheets[0].shapes == (), "1枚目に誤って図形が付いています"
    assert len(sheets[1].shapes) == 1
    assert sheets[1].shapes[0].paragraphs[0].runs[0].text == "二枚目の図形"


# ケース5: shapes=False で抽出しない
def test_shapes_option_disabled(tmp_path: Path) -> None:
    sheet = parse(build(tmp_path), ConvertOptions(shapes=False))
    assert sheet.shapes == ()
    assert sheet.shape_count == 0


# ケース6: drawing を持たないシートで例外にならない
def test_sheet_without_drawing(tmp_path: Path) -> None:
    path = make_xlsx(tmp_path / "plain.xlsx", {"S1": [["a"]]})
    sheet = parse(path)
    assert sheet.shapes == ()


# ケース7: 打ち切りされたシートでも図形が抽出される
def test_shapes_survive_truncation(tmp_path: Path) -> None:
    path = make_xlsx(tmp_path / "big.xlsx", {"S1": [[f"r{i}"] for i in range(1, 21)]})
    add_sheet_drawing(path, 0, drawing_xml(text="打ち切り後も残る"))
    sheet = parse(path, ConvertOptions(excel=ExcelOptions(max_rows=5)))
    assert sheet.truncated_at == 5
    assert len(sheet.shapes) == 1


# ケース8: 両モードで章の末尾に図形ブロックが出る
def test_shape_block_in_both_modes(tmp_path: Path) -> None:
    path = build(tmp_path)
    with SafeZipReader(path) as reader:
        doc = ExcelParser().parse(reader, path.name, ConvertOptions(), NOW)
    options = ConvertOptions()
    table_body, _, _ = ExcelTableRenderer().render(doc, options)
    grid_body, _, _ = ExcelGridRenderer().render(doc, options)
    for body in (table_body, grid_body):
        assert "承認は課長まで" in body
        assert "@ B3" in body
    # 章の末尾: 本文セルより後にある
    assert table_body.index("値1") < table_body.index("承認は課長まで")
    assert grid_body.index("値1") < grid_body.index("承認は課長まで")


# ケース9: shape_count がテキストなしの図形も含む総数
def test_shape_count_includes_textless_shapes(tmp_path: Path) -> None:
    sheet = parse(build(tmp_path, with_empty_shape=True))
    assert len(sheet.shapes) == 1, "テキストなしの図形がブロック化されています"
    assert sheet.shape_count == 2, "テキストなしの図形が総数に数えられていません"


def test_shape_kind_is_classified(tmp_path: Path) -> None:
    sheet = parse(build(tmp_path))
    assert sheet.shapes[0].shape_kind == "吹き出し"
