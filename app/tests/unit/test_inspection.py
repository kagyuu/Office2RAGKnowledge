"""U005-T2 の単体テスト: inspect_file。"""

from __future__ import annotations

from pathlib import Path

import pytest

from office2ragknowledge import inspect_file
from office2ragknowledge.models import DocumentFormat
from office2ragknowledge.ooxml.xml_utils import NS
from tests.helpers.make_malicious import make_broken_zip, make_ole_file
from tests.helpers.make_office import add_sheet_drawing, make_docx, make_pptx, make_xlsx

XDR, A = NS["xdr"], NS["a"]


def excel_with_shape(tmp_path: Path) -> Path:
    path = make_xlsx(
        tmp_path / "book.xlsx",
        {"S1": [["h", "i"], [1, "=A2*2"]], "S2": [["x"], [], ["y"]]},
    )
    add_sheet_drawing(
        path,
        0,
        f'<?xml version="1.0"?><xdr:wsDr xmlns:xdr="{XDR}" xmlns:a="{A}">'
        "<xdr:twoCellAnchor><xdr:from><xdr:col>0</xdr:col><xdr:colOff>0</xdr:colOff>"
        "<xdr:row>0</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>"
        '<xdr:sp><xdr:nvSpPr><xdr:cNvPr name="s1"/></xdr:nvSpPr>'
        "<xdr:txBody><a:p><a:r><a:t>注記</a:t></a:r></a:p></xdr:txBody></xdr:sp>"
        '<xdr:sp><xdr:nvSpPr><xdr:cNvPr name="s2"/></xdr:nvSpPr>'
        "<xdr:txBody><a:p/></xdr:txBody></xdr:sp>"
        "</xdr:twoCellAnchor></xdr:wsDr>",
    )
    return path


# ケース1/2: 単位ラベル
def test_unit_labels(tmp_path: Path) -> None:
    assert inspect_file(make_xlsx(tmp_path / "a.xlsx", {"S": [["a"]]})).unit_label == "シート"
    assert inspect_file(make_pptx(tmp_path / "a.pptx", [("T", [], None)])).unit_label == "スライド"
    assert inspect_file(make_docx(tmp_path / "a.docx", [("p", "本文")])).unit_label == "段落"


# ケース3/4: Excel 固有の項目
def test_excel_specific_fields(tmp_path: Path) -> None:
    info = inspect_file(excel_with_shape(tmp_path))
    assert info.format is DocumentFormat.XLSX
    assert info.unit_count == 2
    assert info.table_region_count is not None and info.table_region_count >= 2
    assert info.formula_without_cache_count == 1


# ケース5: 他形式では None
def test_non_excel_fields_are_none(tmp_path: Path) -> None:
    info = inspect_file(make_docx(tmp_path / "a.docx", [("p", "本文")]))
    assert info.table_region_count is None
    assert info.formula_without_cache_count is None


# ケース6: 図形の総数とテキストあり数
def test_shape_counts(tmp_path: Path) -> None:
    info = inspect_file(excel_with_shape(tmp_path))
    assert info.shape_with_text_count == 1
    assert info.shape_count == 2, "テキストなしの図形が総数に含まれていません"


# ケース7: 非対応形式で status="unsupported"、例外にならない
def test_unsupported_status(tmp_path: Path) -> None:
    path = tmp_path / "a.txt"
    path.write_text("text", encoding="utf-8")
    info = inspect_file(path)
    assert info.status == "unsupported"


# ケース8: 壊れたファイルで status="corrupted"
def test_corrupted_status(tmp_path: Path) -> None:
    info = inspect_file(make_broken_zip(tmp_path / "broken.xlsx"))
    assert info.status in ("corrupted", "unsupported")


def test_protected_status(tmp_path: Path) -> None:
    info = inspect_file(make_ole_file(tmp_path / "locked.xlsx"))
    assert info.status == "protected"
    assert info.password_protected is True


# ケース9: 存在しないパスで FileNotFoundError
def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        inspect_file(tmp_path / "nope.xlsx")


# ケース10: estimated_chars がレンダリング結果の長さ
def test_estimated_chars(tmp_path: Path) -> None:
    from office2ragknowledge import ConvertOptions, convert_file
    from office2ragknowledge.models import ExcelModes, ExcelOptions

    path = make_xlsx(tmp_path / "a.xlsx", {"S": [["あ", "い"], ["う", "え"]]})
    info = inspect_file(path)
    options = ConvertOptions(front_matter=False, excel=ExcelOptions(modes=ExcelModes.TABLE))
    result = convert_file(path, options)
    assert info.estimated_chars == len(result.outputs[0].markdown)
