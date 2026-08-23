"""U002-T3 の単体テスト: 表計算モードのレンダラ (要求③-1)。

``Sheet`` を直接組み立ててレンダラに渡す (パーサを経由しない)。
これにより層の独立性 (P003 §2.3) が保たれていることも同時に確認できる。
"""

from __future__ import annotations

from datetime import UTC, datetime

from office2ragknowledge.models import (
    Cell,
    ConvertOptions,
    Document,
    DocumentFormat,
    DocumentMeta,
    MergedRange,
    Sheet,
    SheetRow,
    TableRegion,
)
from office2ragknowledge.parsers.excel_regions import detect_regions
from office2ragknowledge.render.excel_table import ExcelTableRenderer

NOW = datetime(2026, 8, 24, 10, 0, 0, tzinfo=UTC)


def mkrows(spec: list[str]) -> tuple[SheetRow, ...]:
    rows = []
    for i, line in enumerate(spec, start=1):
        cells = tuple(Cell(row=i, col=c + 1, text=ch) for c, ch in enumerate(line) if ch != " ")
        rows.append(SheetRow(row_index=i, cells=cells))
    return tuple(rows)


def mksheet(
    spec: list[str],
    *,
    name: str = "S1",
    merged: tuple[MergedRange, ...] = (),
    **kwargs: object,
) -> Sheet:
    rows = mkrows(spec)
    regions, abandoned = detect_regions(rows, merged)
    return Sheet(
        name=name,
        rows=rows,
        merged=merged,
        regions=regions,
        region_split_abandoned=abandoned,
        total_rows=len(rows),
        is_empty=not any(r.cells for r in rows),
        **kwargs,  # type: ignore[arg-type]
    )


def mkdoc(*sheets: Sheet, title: str = "ブック") -> Document:
    meta = DocumentMeta(
        source_file="a.xlsx",
        source_path="a.xlsx",
        source_format=DocumentFormat.XLSX,
        source_size_bytes=0,
        source_sha256="",
        converter="test",
        converted_at=NOW,
        title=title,
    )
    return Document(format=DocumentFormat.XLSX, title=title, meta=meta, blocks=sheets)


def render(doc: Document, options: ConvertOptions | None = None) -> tuple[str, dict]:  # type: ignore[type-arg]
    body, stats, _ = ExcelTableRenderer().render(doc, options or ConvertOptions())
    return body, stats


# ケース1: シート見出しとテーブル
def test_sheet_heading_and_table() -> None:
    body, _ = render(mkdoc(mksheet(["AB", "CD"], name="売上")))
    assert "## 売上" in body
    assert "| A | B |" in body
    assert "| --- | --- |" in body


# ケース2: 領域が1つなら小見出しを出さない
def test_no_subheading_for_single_region() -> None:
    body, _ = render(mkdoc(mksheet(["AB", "CD"])))
    assert "### 表" not in body


# ケース3: 領域が2つ以上なら小見出しを出す
def test_subheading_for_multiple_regions() -> None:
    body, _ = render(mkdoc(mksheet(["AB CD", "EF GH"])))
    assert "### 表 1 (A1:B2)" in body
    assert "### 表 2 (D1:E2)" in body


# ケース4: 結合セルの値が範囲内に複製される
def test_merged_cells_are_duplicated() -> None:
    rows = (
        SheetRow(row_index=1, cells=(Cell(row=1, col=1, text="見出し"),)),
        SheetRow(
            row_index=2,
            cells=tuple(Cell(row=2, col=c, text=f"v{c}") for c in (1, 2, 3)),
        ),
    )
    merged = (MergedRange(top=1, left=1, bottom=1, right=3),)
    regions, _ = detect_regions(rows, merged)
    sheet = Sheet(name="S1", rows=rows, merged=merged, regions=regions, total_rows=2)
    body, _ = render(mkdoc(sheet))
    assert "| 見出し | 見出し | 見出し |" in body


# ケース5: 全行の列数が揃う (INV-01)
def test_all_rows_have_same_column_count() -> None:
    body, _ = render(mkdoc(mksheet(["ABC", "D  ", "EF "])))
    table_lines = [ln for ln in body.splitlines() if ln.startswith("|")]
    counts = {ln.count("|") for ln in table_lines}
    assert len(counts) == 1, f"列数が揃っていません: {counts}"


# ケース6: 先頭行がヘッダで、区切り行が入る
def test_header_and_separator() -> None:
    body, _ = render(mkdoc(mksheet(["AB", "CD"])))
    lines = [ln for ln in body.splitlines() if ln.startswith("|")]
    assert lines[0] == "| A | B |"
    assert lines[1] == "| --- | --- |"


# ケース7: セル値の | がエスケープされる
def test_pipe_is_escaped() -> None:
    rows = (SheetRow(row_index=1, cells=(Cell(row=1, col=1, text="a|b"),)),)
    regions, _ = detect_regions(rows, [])
    sheet = Sheet(name="S1", rows=rows, regions=regions, total_rows=1)
    body, _ = render(mkdoc(sheet))
    assert "a\\|b" in body


# ケース8: セル内改行が <br> になる
def test_newline_becomes_br() -> None:
    rows = (SheetRow(row_index=1, cells=(Cell(row=1, col=1, text="a\nb"),)),)
    regions, _ = detect_regions(rows, [])
    sheet = Sheet(name="S1", rows=rows, regions=regions, total_rows=1)
    body, _ = render(mkdoc(sheet))
    assert "a<br>b" in body


# ケース9: 空のシート
def test_empty_sheet() -> None:
    sheet = Sheet(name="空", rows=(), regions=(), is_empty=True)
    body, _ = render(mkdoc(sheet))
    assert "## 空" in body
    assert "(空のシートです)" in body
    assert "|" not in body


# ケース10: 打ち切り注記
def test_truncation_note() -> None:
    sheet = mksheet(["AB"], truncated_at=5)
    sheet = Sheet(
        name=sheet.name,
        rows=sheet.rows,
        regions=sheet.regions,
        truncated_at=5,
        total_rows=100,
    )
    body, _ = render(mkdoc(sheet))
    assert "> ※ このシートは 5 行で打ち切りました (全 100 行)" in body


# ケース11: stats.tables が領域数の合計
def test_stats_tables() -> None:
    _, stats = render(mkdoc(mksheet(["AB CD"]), mksheet(["EF"], name="S2")))
    assert stats["sheets"] == 2
    assert stats["tables"] == 3


# ケース12: 文書冒頭に # タイトル
def test_document_title() -> None:
    body, _ = render(mkdoc(mksheet(["A"]), title="売上ブック"))
    assert body.startswith("# 売上ブック")


# ケース13: 連続する空行が出力に現れない
def test_no_consecutive_blank_lines() -> None:
    body, _ = render(mkdoc(mksheet(["AB", "  ", "  ", "CD"])))
    assert "\n\n\n" not in body


# ケース14: 末尾が改行1つ
def test_ends_with_single_newline() -> None:
    body, _ = render(mkdoc(mksheet(["A"])))
    assert body.endswith("\n")
    assert not body.endswith("\n\n")


def test_region_ref_uses_a1_notation() -> None:
    region = TableRegion(top=1, left=1, bottom=12, right=4)
    assert region.ref == "A1:D12"
