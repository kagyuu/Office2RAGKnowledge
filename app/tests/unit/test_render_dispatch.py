"""U002-T5 の単体テスト: 二重出力の組み立て (要求③)。

1つの中間表現から、``--excel-modes`` に応じて1〜2件の出力を生成する。
**この関数はファイルに触れない** (解析は1回のみ。REQ-F-068)。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from office2ragknowledge.models import (
    Cell,
    ConvertOptions,
    Document,
    DocumentFormat,
    DocumentMeta,
    ExcelModes,
    ExcelOptions,
    OutputMode,
    Sheet,
    SheetRow,
)
from office2ragknowledge.parsers.excel_regions import detect_regions
from office2ragknowledge.render import render_document

NOW = datetime(2026, 8, 24, 10, 0, 0, tzinfo=UTC)


def mkdoc(*, warnings: tuple[str, ...] = ()) -> Document:
    rows = (
        SheetRow(
            row_index=1,
            cells=(Cell(row=1, col=1, text="あ"), Cell(row=1, col=2, text="い")),
        ),
        SheetRow(row_index=2, cells=(Cell(row=2, col=1, text="う"),)),
    )
    regions, _ = detect_regions(rows, [])
    sheet = Sheet(name="S1", rows=rows, regions=regions, total_rows=2)
    meta = DocumentMeta(
        source_file="a.xlsx",
        source_path="a.xlsx",
        source_format=DocumentFormat.XLSX,
        source_size_bytes=10,
        source_sha256="abc",
        converter="test",
        converted_at=NOW,
        title="ブック",
        warnings=warnings,
    )
    return Document(
        format=DocumentFormat.XLSX,
        title="ブック",
        meta=meta,
        blocks=(sheet,),
        warnings=warnings,
    )


def opts(modes: ExcelModes = ExcelModes.BOTH, **kw: object) -> ConvertOptions:
    return ConvertOptions(excel=ExcelOptions(modes=modes), **kw)  # type: ignore[arg-type]


# ケース1: BOTH で2件、順序は (table, grid)
def test_both_returns_two_outputs_in_order() -> None:
    outputs = render_document(mkdoc(), opts())
    assert len(outputs) == 2
    assert [o.mode for o in outputs] == [OutputMode.TABLE, OutputMode.GRID]


# ケース2: サフィックス
def test_suffixes() -> None:
    outputs = render_document(mkdoc(), opts())
    assert [o.filename_suffix for o in outputs] == [".table.md", ".grid.md"]


# ケース3: TABLE のみ。サフィックスは .table.md のまま (.md にしない)
def test_table_only() -> None:
    outputs = render_document(mkdoc(), opts(ExcelModes.TABLE))
    assert len(outputs) == 1
    assert outputs[0].mode is OutputMode.TABLE
    assert outputs[0].filename_suffix == ".table.md"


# ケース4: GRID のみ
def test_grid_only() -> None:
    outputs = render_document(mkdoc(), opts(ExcelModes.GRID))
    assert len(outputs) == 1
    assert outputs[0].mode is OutputMode.GRID
    assert outputs[0].filename_suffix == ".grid.md"


# ケース5: 2件の meta が stats 以外で一致する
def test_meta_is_shared_except_stats() -> None:
    table, grid = render_document(mkdoc(), opts())
    for field in ("source_file", "source_path", "source_sha256", "title", "converter"):
        assert getattr(table.meta, field) == getattr(grid.meta, field)
    assert table.meta.converted_at == grid.meta.converted_at
    assert table.meta.stats != grid.meta.stats


# ケース6: front matter に output_mode が入る
def test_front_matter_output_mode() -> None:
    table, grid = render_document(mkdoc(), opts())
    assert 'output_mode: "table"' in table.markdown
    assert 'output_mode: "grid"' in grid.markdown


# ケース7: front_matter=False で front matter が出ない
def test_no_front_matter_option() -> None:
    outputs = render_document(mkdoc(), opts(front_matter=False))
    for output in outputs:
        assert not output.markdown.startswith("---")
        assert "output_mode" not in output.markdown


# ケース8: 2件の本文が異なる
def test_two_outputs_differ() -> None:
    table, grid = render_document(mkdoc(), opts(front_matter=False))
    assert table.markdown != grid.markdown
    assert "|" in table.markdown
    assert "|" not in grid.markdown


# ケース9: ファイル I/O が発生しない (Document のみを入力とする)
def test_no_file_io(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """render_document がファイルを開かないことを確認する。"""
    import builtins

    original_open = builtins.open
    opened: list[str] = []

    def tracking_open(file, *args, **kwargs):  # type: ignore[no-untyped-def]
        opened.append(str(file))
        return original_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", tracking_open)
    render_document(mkdoc(), opts())
    assert opened == [], f"ファイルが開かれました: {opened}"


# ケース10: 表領域の上限超過の警告は表計算モードにのみ入る
def test_region_warning_only_in_table_mode() -> None:
    warning = "シート「S1」は表領域が 100 件を超えたため、分割せず1つの表として出力しました"
    table, grid = render_document(mkdoc(warnings=(warning,)), opts())
    assert any("表領域が" in w for w in table.warnings)
    assert not any("表領域が" in w for w in grid.warnings)


def test_other_warnings_are_in_both_modes() -> None:
    warning = "シート「S1」に計算結果を持たない数式セルが 3 件あり、数式を出力しました"
    table, grid = render_document(mkdoc(warnings=(warning,)), opts())
    assert warning in table.warnings
    assert warning in grid.warnings


def test_non_excel_raises_not_implemented_until_u004() -> None:
    """Word / PowerPoint のレンダラは U004 で実装される。"""
    meta = DocumentMeta(
        source_file="a.docx",
        source_path="a.docx",
        source_format=DocumentFormat.DOCX,
        source_size_bytes=0,
        source_sha256="",
        converter="test",
        converted_at=NOW,
    )
    doc = Document(format=DocumentFormat.DOCX, title="文書", meta=meta)
    try:
        outputs = render_document(doc, ConvertOptions())
    except NotImplementedError:
        pytest.skip("U004 未実装のため NotImplementedError (想定内)")
    else:
        assert len(outputs) == 1
        assert outputs[0].mode is None
        assert outputs[0].filename_suffix == ".md"
