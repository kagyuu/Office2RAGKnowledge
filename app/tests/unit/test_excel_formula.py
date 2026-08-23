"""U002-T2 の単体テスト: 数式のキャッシュ値の扱い (要求②)。

**ケース6 (空の `<v>` の判定) は必須。** P003 §1.2 の実測で特定した落とし穴で
あり、ここを誤ると要求②が機能しない。
"""

from __future__ import annotations

import zipfile
from datetime import UTC, datetime
from pathlib import Path

from office2ragknowledge.models import ConvertOptions, ExcelOptions, Sheet
from office2ragknowledge.ooxml.zip_reader import SafeZipReader
from office2ragknowledge.parsers.excel import ExcelParser
from tests.helpers.make_office import inject_cached_values, make_xlsx

NOW = datetime(2026, 8, 24, 10, 0, 0, tzinfo=UTC)


def parse(path: Path, options: ConvertOptions | None = None):  # type: ignore[no-untyped-def]
    with SafeZipReader(path) as reader:
        return ExcelParser().parse(reader, path.name, options or ConvertOptions(), NOW)


def only_sheet(doc) -> Sheet:  # type: ignore[no-untyped-def]
    return next(b for b in doc.blocks if isinstance(b, Sheet))


def formula_sheet(tmp_path: Path, name: str = "a.xlsx") -> Path:
    return make_xlsx(
        tmp_path / name,
        {"集計": [["値", "計算"], [10, "=A2*2"], [20, "=A3*2"]]},
    )


# ケース1: キャッシュ値なしで数式そのものが出力される (先頭の = を含む)
def test_formula_text_without_cache(tmp_path: Path) -> None:
    sheet = only_sheet(parse(formula_sheet(tmp_path)))
    cell = next(c for row in sheet.rows for c in row.cells if c.is_formula)
    assert cell.text.startswith("=")
    assert cell.text == "=A2*2"


# ケース2: value_missing / is_formula
def test_flags_without_cache(tmp_path: Path) -> None:
    sheet = only_sheet(parse(formula_sheet(tmp_path)))
    cell = next(c for row in sheet.rows for c in row.cells if c.is_formula)
    assert cell.is_formula is True
    assert cell.value_missing is True
    assert cell.formula == "=A2*2"


# ケース3: formula_without_cache_count が件数と一致
def test_missing_cache_count(tmp_path: Path) -> None:
    sheet = only_sheet(parse(formula_sheet(tmp_path)))
    assert sheet.formula_without_cache_count == 2


# ケース4: 警告はシート単位で1件 (REQ-F-052)
def test_warning_is_per_sheet(tmp_path: Path) -> None:
    doc = parse(formula_sheet(tmp_path))
    matches = [w for w in doc.warnings if "計算結果を持たない数式セル" in w]
    assert len(matches) == 1, f"警告がシート単位で1件でない: {matches}"
    assert "2 件" in matches[0]
    assert "集計" in matches[0]


# ケース5: キャッシュ値ありで値が出力される
def test_value_with_cache(tmp_path: Path) -> None:
    path = formula_sheet(tmp_path, "cached.xlsx")
    inject_cached_values(path, "999")
    sheet = only_sheet(parse(path))
    cell = next(c for row in sheet.rows for c in row.cells if c.is_formula)
    assert cell.value_missing is False
    assert cell.text == "999"
    assert sheet.formula_without_cache_count == 0


# ケース6 (必須): 空の <v> を持つセルが「キャッシュ値なし」と判定される
def test_empty_v_element_means_no_cache(tmp_path: Path) -> None:
    """openpyxl は ``<f>A2*2</f><v></v>`` を書き出す。

    ``<v>`` 要素は **存在するが中身が空**である。要素の有無で判定すると
    「値あり」と誤判定し、空文字がセル値として出力されて数式が失われる。
    """
    path = formula_sheet(tmp_path)
    # 前提: 生 XML に空の <v> が存在することを確認する
    with zipfile.ZipFile(path) as zf:
        sheet_xml = next(
            zf.read(n).decode("utf-8") for n in zf.namelist() if n.startswith("xl/worksheets/sheet")
        )
    assert "<v></v>" in sheet_xml or "<v/>" in sheet_xml, (
        "前提が崩れている: openpyxl が空の <v> を書き出していない"
    )

    sheet = only_sheet(parse(path))
    cell = next(c for row in sheet.rows for c in row.cells if c.is_formula)
    assert cell.value_missing is True, "空の <v> が『値あり』と誤判定されている"
    assert cell.text == "=A2*2"


# ケース7: 共有数式の参照セルに先頭セルの数式が割り当てられる
def test_shared_formula(tmp_path: Path) -> None:
    path = make_xlsx(tmp_path / "shared.xlsx", {"S1": [[1, "=A1*2"], [2, "=A2*2"]]})
    sheet = only_sheet(parse(path))
    formulas = [c.formula for row in sheet.rows for c in row.cells if c.is_formula]
    assert all(f and f.startswith("=") for f in formulas)


# ケース8: 数式でないセル
def test_non_formula_cell(tmp_path: Path) -> None:
    sheet = only_sheet(parse(formula_sheet(tmp_path)))
    cell = sheet.rows[1].cells[0]
    assert cell.is_formula is False
    assert cell.formula is None
    assert cell.value_missing is False


# ケース9: キャッシュ値なしが0件なら警告が出ない
def test_no_warning_when_all_cached(tmp_path: Path) -> None:
    path = make_xlsx(tmp_path / "plain.xlsx", {"S1": [["a", "b"]]})
    doc = parse(path)
    assert not any("計算結果を持たない" in w for w in doc.warnings)


def test_formulas_option_appends_formula_when_cached(tmp_path: Path) -> None:
    """--formulas 指定時、キャッシュ値があれば値と数式を併記する。"""
    path = formula_sheet(tmp_path, "cached2.xlsx")
    inject_cached_values(path, "42")
    options = ConvertOptions(excel=ExcelOptions(formulas=True))
    sheet = only_sheet(parse(path, options))
    cell = next(c for row in sheet.rows for c in row.cells if c.is_formula)
    assert cell.text == "42 (=A2*2)"


def test_formulas_option_has_no_effect_without_cache(tmp_path: Path) -> None:
    """キャッシュ値が無ければ併記する値が無いため、数式のみ。"""
    options = ConvertOptions(excel=ExcelOptions(formulas=True))
    sheet = only_sheet(parse(formula_sheet(tmp_path), options))
    cell = next(c for row in sheet.rows for c in row.cells if c.is_formula)
    assert cell.text == "=A2*2"
