"""U002-T2 の単体テスト: Excel パーサ。

不変条件 INV-07 (空行を含む) / INV-08 (列昇順・非空のみ) / INV-09 (結合を
展開しない) は、方眼紙モードが成立するための前提である。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from office2ragknowledge.models import (
    ConvertOptions,
    DocumentFormat,
    ExcelOptions,
    Sheet,
    col_to_letter,
    letter_to_col,
)
from office2ragknowledge.ooxml.zip_reader import SafeZipReader
from office2ragknowledge.parsers.excel import ExcelParser, parse_cell_ref
from tests.helpers.make_office import make_xlsx

NOW = datetime(2026, 8, 24, 10, 0, 0, tzinfo=UTC)


def parse(path: Path, options: ConvertOptions | None = None):  # type: ignore[no-untyped-def]
    with SafeZipReader(path) as reader:
        return ExcelParser().parse(reader, path.name, options or ConvertOptions(), NOW)


def sheets_of(doc) -> list[Sheet]:  # type: ignore[no-untyped-def]
    return [b for b in doc.blocks if isinstance(b, Sheet)]


# ケース1: 1シート・1表
def test_single_sheet(tmp_path: Path) -> None:
    p = make_xlsx(tmp_path / "a.xlsx", {"S1": [["h1", "h2"], ["v1", "v2"]]})
    doc = parse(p)
    assert doc.format is DocumentFormat.XLSX
    assert len(sheets_of(doc)) == 1


# ケース2: シート名と並び順
def test_sheet_names_and_order(tmp_path: Path) -> None:
    p = make_xlsx(tmp_path / "a.xlsx", {"売上": [["a"]], "経費": [["b"]], "集計": [["c"]]})
    doc = parse(p)
    assert [s.name for s in sheets_of(doc)] == ["売上", "経費", "集計"]


# ケース3: rows が空行を含み欠番なし (INV-07)
def test_rows_include_blank_rows_without_gaps(tmp_path: Path) -> None:
    p = make_xlsx(tmp_path / "a.xlsx", {"S1": [["a"], [], [], ["b"]]})
    sheet = sheets_of(parse(p))[0]
    assert [r.row_index for r in sheet.rows] == [1, 2, 3, 4]
    assert sheet.rows[1].is_empty is True
    assert sheet.rows[2].is_empty is True


# ケース4: cells が列昇順・非空のみ (INV-08)
def test_cells_are_sorted_and_sparse(tmp_path: Path) -> None:
    p = make_xlsx(tmp_path / "a.xlsx", {"S1": [["a", "", "c", "", "e"]]})
    sheet = sheets_of(parse(p))[0]
    cols = [c.col for c in sheet.rows[0].cells]
    assert cols == sorted(cols)
    assert cols == [1, 3, 5]


# ケース5: 結合を展開しない (INV-09)
def test_merged_cells_are_not_expanded(tmp_path: Path) -> None:
    p = make_xlsx(
        tmp_path / "a.xlsx",
        {"S1": [["結合された見出し", "", ""], ["a", "b", "c"]]},
        merges={"S1": ["A1:C1"]},
    )
    sheet = sheets_of(parse(p))[0]
    first_row_cols = [c.col for c in sheet.rows[0].cells]
    assert first_row_cols == [1], "結合範囲が展開されています (INV-09 違反)"
    assert len(sheet.merged) == 1
    rng = sheet.merged[0]
    assert (rng.top, rng.left, rng.bottom, rng.right) == (1, 1, 1, 3)


# ケース6: 空のシート
def test_empty_sheet(tmp_path: Path) -> None:
    p = make_xlsx(tmp_path / "a.xlsx", {"空": [[]]})
    sheet = sheets_of(parse(p))[0]
    assert sheet.is_empty is True
    assert sheet.regions == ()


# ケース7: max_rows で打ち切られる
def test_truncation(tmp_path: Path) -> None:
    rows = [[f"r{i}"] for i in range(1, 11)]
    p = make_xlsx(tmp_path / "a.xlsx", {"S1": rows})
    options = ConvertOptions(excel=ExcelOptions(max_rows=5))
    doc = parse(p, options)
    sheet = sheets_of(doc)[0]
    assert sheet.truncated_at == 5
    assert sheet.total_rows == 10
    assert len(sheet.rows) == 5
    assert any("打ち切りました" in w for w in doc.warnings)


# ケース8: 非表示シートが既定で除外される
def test_hidden_sheet_excluded_by_default(tmp_path: Path) -> None:
    p = make_xlsx(tmp_path / "a.xlsx", {"表": [["a"]], "隠し": [["b"]]}, hidden_sheets={"隠し"})
    assert [s.name for s in sheets_of(parse(p))] == ["表"]


# ケース9: include_hidden で非表示シートが含まれる
def test_hidden_sheet_included_with_option(tmp_path: Path) -> None:
    p = make_xlsx(tmp_path / "a.xlsx", {"表": [["a"]], "隠し": [["b"]]}, hidden_sheets={"隠し"})
    options = ConvertOptions(include_hidden=True)
    assert [s.name for s in sheets_of(parse(p, options))] == ["表", "隠し"]


# ケース10: 非表示行が除外される
def test_hidden_rows_excluded(tmp_path: Path) -> None:
    p = make_xlsx(
        tmp_path / "a.xlsx",
        {"S1": [["a"], ["hidden"], ["c"]]},
        hidden_rows={"S1": [2]},
    )
    sheet = sheets_of(parse(p))[0]
    texts = [c.text for row in sheet.rows for c in row.cells]
    assert "hidden" not in texts
    assert texts == ["a", "c"]


# ケース11: 日付の整形
def test_date_format(tmp_path: Path) -> None:
    from datetime import date

    p = make_xlsx(
        tmp_path / "a.xlsx",
        {"S1": [[date(2026, 4, 1)]]},
        number_formats={"S1": {"A1": "yyyy-mm-dd"}},
    )
    sheet = sheets_of(parse(p))[0]
    assert sheet.rows[0].cells[0].text == "2026-04-01"


# ケース12: パーセントの整形
def test_percent_format(tmp_path: Path) -> None:
    p = make_xlsx(tmp_path / "a.xlsx", {"S1": [[0.153]]}, number_formats={"S1": {"A1": "0.0%"}})
    sheet = sheets_of(parse(p))[0]
    assert sheet.rows[0].cells[0].text == "15.3%"


# ケース13: 論理値
def test_boolean_values(tmp_path: Path) -> None:
    p = make_xlsx(tmp_path / "a.xlsx", {"S1": [[True, False]]})
    sheet = sheets_of(parse(p))[0]
    assert [c.text for c in sheet.rows[0].cells] == ["TRUE", "FALSE"]


# ケース14: col_to_letter の境界値
def test_col_to_letter_boundaries() -> None:
    assert col_to_letter(1) == "A"
    assert col_to_letter(25) == "Y"
    assert col_to_letter(26) == "Z"
    assert col_to_letter(27) == "AA"
    assert col_to_letter(52) == "AZ"
    assert col_to_letter(53) == "BA"
    assert col_to_letter(702) == "ZZ"
    assert col_to_letter(703) == "AAA"


# ケース15: letter_to_col が逆関数
def test_letter_to_col_roundtrip() -> None:
    for col in (1, 25, 26, 27, 52, 53, 701, 702, 703, 16384):
        assert letter_to_col(col_to_letter(col)) == col


# ケース16: converted_at が引数の値になる (パーサが now() を呼んでいない)
def test_converted_at_is_injected(tmp_path: Path) -> None:
    p = make_xlsx(tmp_path / "a.xlsx", {"S1": [["a"]]})
    doc = parse(p)
    assert doc.meta.converted_at == NOW


def test_parse_cell_ref() -> None:
    assert parse_cell_ref("B3") == (3, 2)
    assert parse_cell_ref("AA10") == (10, 27)
    assert parse_cell_ref("bogus") is None


def test_shapes_are_empty_in_this_sprint(tmp_path: Path) -> None:
    """U002 の時点では図形は未実装 (U003 で埋める)。"""
    p = make_xlsx(tmp_path / "a.xlsx", {"S1": [["a"]]})
    sheet = sheets_of(parse(p))[0]
    assert sheet.shapes == ()
    assert sheet.shape_count == 0


def test_cell_text_is_not_escaped(tmp_path: Path) -> None:
    """パーサはエスケープ前の生文字列を格納する (INV-02)。"""
    p = make_xlsx(tmp_path / "a.xlsx", {"S1": [["# 見出し風", "a|b"]]})
    sheet = sheets_of(parse(p))[0]
    texts = [c.text for c in sheet.rows[0].cells]
    assert texts == ["# 見出し風", "a|b"]


def test_options_are_not_mutated(tmp_path: Path) -> None:
    p = make_xlsx(tmp_path / "a.xlsx", {"S1": [["a"]]})
    options = ConvertOptions()
    before = replace(options)
    parse(p, options)
    assert options == before
