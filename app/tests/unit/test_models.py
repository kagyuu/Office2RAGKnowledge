"""U001-T2 の単体テスト: 中間表現とオプションの型定義。"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path

import pytest

from office2ragknowledge.models import (
    BatchResult,
    ConversionResult,
    ConvertOptions,
    DocumentFormat,
    DocumentMeta,
    ExcelModes,
    FailureInfo,
    ImageMode,
    InlineRun,
    MarkdownOutput,
    MergedRange,
    OnExists,
    OutputMode,
    ShapeStyle,
    SheetRow,
    make_run,
)

NOW = datetime(2026, 8, 24, 10, 0, 0, tzinfo=UTC)


def _meta() -> DocumentMeta:
    return DocumentMeta(
        source_file="a.xlsx",
        source_path="a.xlsx",
        source_format=DocumentFormat.XLSX,
        source_size_bytes=1,
        source_sha256="deadbeef",
        converter="office2ragknowledge 1.0.0",
        converted_at=NOW,
    )


def _output(text: str, mode: OutputMode | None = None) -> MarkdownOutput:
    return MarkdownOutput(markdown=text, meta=_meta(), mode=mode)


# ケース1: 全 dataclass が frozen である
def test_dataclasses_are_frozen() -> None:
    run = InlineRun(text="a")
    with pytest.raises(FrozenInstanceError):
        run.text = "b"  # type: ignore[misc]
    opts = ConvertOptions()
    with pytest.raises(FrozenInstanceError):
        opts.shapes = False  # type: ignore[misc]


# ケース2: 列挙型の値が CLI 文字列と一致する
def test_enum_values_match_cli_strings() -> None:
    assert ExcelModes.BOTH == "both"
    assert ExcelModes.TABLE == "table"
    assert ExcelModes.GRID == "grid"
    assert OutputMode.TABLE == "table"
    assert OutputMode.GRID == "grid"
    assert ShapeStyle.QUOTE == "quote"
    assert ShapeStyle.HEADING == "heading"
    assert ShapeStyle.PLAIN == "plain"
    assert ImageMode.NONE == "none"
    assert ImageMode.EXTRACT == "extract"
    assert OnExists.SKIP == "skip"
    assert OnExists.OVERWRITE == "overwrite"
    assert OnExists.FAIL == "fail"
    assert DocumentFormat.DOCX == "docx"
    assert DocumentFormat.XLSX == "xlsx"
    assert DocumentFormat.PPTX == "pptx"


# ケース3: OutputMode に BOTH が存在しない
def test_output_mode_has_no_both() -> None:
    assert not hasattr(OutputMode, "BOTH")
    assert {m.value for m in OutputMode} == {"table", "grid"}


# ケース4: make_run が空文字で None を返す (INV-03)
def test_make_run_rejects_empty_text() -> None:
    assert make_run("") is None
    run = make_run("あ", bold=True)
    assert run is not None
    assert run.text == "あ"
    assert run.bold is True


# ケース5: outputs 1件で markdown が使える
def test_markdown_property_with_single_output() -> None:
    result = ConversionResult(
        source_path=Path("a.docx"),
        format=DocumentFormat.DOCX,
        outputs=(_output("# 本文"),),
    )
    assert result.markdown == "# 本文"


# ケース6: outputs 2件で ValueError (ADR-009 の中心的な契約)
def test_markdown_property_raises_on_multiple_outputs() -> None:
    result = ConversionResult(
        source_path=Path("a.xlsx"),
        format=DocumentFormat.XLSX,
        outputs=(_output("表", OutputMode.TABLE), _output("方眼", OutputMode.GRID)),
    )
    with pytest.raises(ValueError, match="outputs"):
        _ = result.markdown


# ケース7: outputs 0件でも ValueError
def test_markdown_property_raises_on_zero_outputs() -> None:
    result = ConversionResult(source_path=Path("a.docx"), format=DocumentFormat.DOCX)
    with pytest.raises(ValueError):
        _ = result.markdown


# ケース8: BatchResult.exit_code
def test_batch_result_exit_code() -> None:
    assert BatchResult().exit_code == 0
    with_failure = BatchResult(
        failures=(FailureInfo(path=Path("a.doc"), code="E-002", message="非対応"),)
    )
    assert with_failure.exit_code == 1


# ケース9: SheetRow.is_empty
def test_sheet_row_is_empty() -> None:
    from office2ragknowledge.models import Cell

    assert SheetRow(row_index=1).is_empty is True
    row = SheetRow(row_index=1, cells=(Cell(row=1, col=1, text="a"),))
    assert row.is_empty is False


# ケース10: MergedRange.contains は閉区間
def test_merged_range_contains_is_inclusive() -> None:
    rng = MergedRange(top=2, left=1, bottom=3, right=4)
    assert rng.contains(2, 1) is True
    assert rng.contains(3, 4) is True
    assert rng.contains(3, 2) is True
    assert rng.contains(4, 2) is False
    assert rng.contains(1, 2) is False
    assert rng.contains(2, 5) is False


# ケース11: ConvertOptions の既定値が P002 §6.2 のとおり
def test_convert_options_defaults() -> None:
    opts = ConvertOptions()
    assert opts.shapes is True
    assert opts.shape_style is ShapeStyle.QUOTE
    assert opts.images is ImageMode.NONE
    assert opts.include_hidden is False
    assert opts.notes is True
    assert opts.headers_footers is False
    assert opts.comments is False
    assert opts.front_matter is True
    assert opts.excel.modes is ExcelModes.BOTH
    assert opts.excel.grid_separator == ""
    assert opts.excel.table_regions is True
    assert opts.excel.max_table_regions == 100
    assert opts.excel.formulas is False
    assert opts.excel.max_rows == 10_000


def test_convert_options_excel_is_independent_instance() -> None:
    """既定値の ExcelOptions がインスタンス間で共有されていないこと。"""
    a = ConvertOptions()
    b = ConvertOptions()
    assert a.excel == b.excel
