"""T001 結合テスト: Excel 二重出力の連携 (要求①②③)。

パーサから2ファイルの書き出しまでを通しで検証する。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from office2ragknowledge import (
    BatchOptions,
    ConvertOptions,
    ExcelModes,
    ExcelOptions,
    convert_batch,
    convert_file,
    write_result,
)
from tests.helpers.compare import body_of
from tests.helpers.make_office import inject_cached_values, make_xlsx


@pytest.fixture
def mixed(tmp_path: Path) -> Path:
    """3シート構成: 正規の表 / 複数表 / 方眼紙レイアウト。"""
    return make_xlsx(
        tmp_path / "mixed.xlsx",
        {
            "売上": [["商品", "4月", "5月"], ["A", 100, 120], ["B", 200, 210]],
            "複数表": [
                ["h1", "h2", "", "h3", "h4"],
                ["a1", "a2", "", "b1", "b2"],
                ["", "", "", "", ""],
                ["c1", "c2", "", "", ""],
            ],
            "申請書": [
                ["休暇", "申請", "書", ""],
                ["", "", "", ""],
                ["氏名", "", "山田", "太郎"],
                ["所属", "", "開発", "部"],
            ],
        },
    )


def outputs_of(path: Path, options: ConvertOptions | None = None) -> dict[str, str]:
    result = convert_file(path, options or ConvertOptions())
    return {o.filename_suffix: o.markdown for o in result.outputs}


# 期待1〜8: 二重出力 (要求③)
def test_two_files_are_written(mixed: Path, tmp_path: Path) -> None:
    result = convert_file(mixed)
    written = write_result(result, tmp_path / "out")
    names = sorted(p.name for p in written.markdown_paths)
    assert names == ["mixed.grid.md", "mixed.table.md"]


def test_output_mode_in_front_matter(mixed: Path) -> None:
    outputs = outputs_of(mixed)
    assert 'output_mode: "table"' in outputs[".table.md"]
    assert 'output_mode: "grid"' in outputs[".grid.md"]


def test_shared_front_matter_fields(mixed: Path) -> None:
    result = convert_file(mixed)
    table, grid = result.outputs
    for field in ("source_file", "source_sha256", "title", "converter"):
        assert getattr(table.meta, field) == getattr(grid.meta, field)


def test_bodies_differ(mixed: Path) -> None:
    outputs = outputs_of(mixed)
    assert body_of(outputs[".table.md"]) != body_of(outputs[".grid.md"])


def test_single_mode_options(mixed: Path) -> None:
    table_only = outputs_of(mixed, ConvertOptions(excel=ExcelOptions(modes=ExcelModes.TABLE)))
    assert set(table_only) == {".table.md"}
    grid_only = outputs_of(mixed, ConvertOptions(excel=ExcelOptions(modes=ExcelModes.GRID)))
    assert set(grid_only) == {".grid.md"}


# 期待9〜14: 表計算モード (要求①③-1)
def test_sheet_headings(mixed: Path) -> None:
    body = body_of(outputs_of(mixed)[".table.md"])
    for name in ("## 売上", "## 複数表", "## 申請書"):
        assert name in body


def test_single_region_has_no_subheading(mixed: Path) -> None:
    body = body_of(outputs_of(mixed)[".table.md"])
    sales = body.split("## 売上")[1].split("## ")[0]
    assert "### 表" not in sales


def test_multiple_regions_get_subheadings(mixed: Path) -> None:
    """要求①: 空行・空列で分割された領域ごとに小見出しが付く。"""
    body = body_of(outputs_of(mixed)[".table.md"])
    section = body.split("## 複数表")[1].split("\n## ")[0]
    assert "### 表 1 (A1:B2)" in section
    assert "### 表 2 (D1:E2)" in section
    assert "### 表 3 (A4:B4)" in section


def test_table_rows_have_equal_columns(mixed: Path) -> None:
    body = body_of(outputs_of(mixed)[".table.md"])
    for line_group in body.split("### "):
        rows = [ln for ln in line_group.splitlines() if ln.startswith("|")]
        if rows:
            assert len({ln.count("|") for ln in rows}) == 1


# 期待15〜18: 方眼紙モード (要求③-2)
def test_grid_mode_reads_as_text(mixed: Path) -> None:
    """P001 §7.3 の期待出力そのもの。"""
    body = body_of(outputs_of(mixed)[".grid.md"])
    section = body.split("## 申請書")[1].strip()
    lines = [ln for ln in section.splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    assert lines[:4] == ["休暇申請書", "", "氏名山田太郎", "所属開発部"]


def test_grid_mode_has_no_table_markup(mixed: Path) -> None:
    body = body_of(outputs_of(mixed)[".grid.md"])
    content = [ln for ln in body.splitlines() if not ln.startswith("#")]
    assert not any(ln.startswith("|") for ln in content)


def test_grid_stats_has_lines_not_tables(mixed: Path) -> None:
    result = convert_file(mixed)
    grid = next(o for o in result.outputs if o.filename_suffix == ".grid.md")
    assert "lines" in grid.meta.stats
    assert "tables" not in grid.meta.stats


# 期待19〜22: 数式 (要求②)
def test_formula_without_cache(tmp_path: Path) -> None:
    path = make_xlsx(tmp_path / "f.xlsx", {"集計": [["値", "計算"], [10, "=A2*2"]]})
    outputs = outputs_of(path)
    for markdown in outputs.values():
        assert "=A2*2" in markdown


def test_formula_warning_is_once_per_sheet(tmp_path: Path) -> None:
    path = make_xlsx(tmp_path / "f.xlsx", {"集計": [["v"], ["=A1*2"], ["=A1*3"], ["=A1*4"]]})
    result = convert_file(path)
    matches = [w for w in result.warnings if "計算結果を持たない" in w]
    assert len(matches) == 1
    assert "3 件" in matches[0]


def test_formula_with_cache_shows_value(tmp_path: Path) -> None:
    path = make_xlsx(tmp_path / "c.xlsx", {"集計": [["値"], ["=A1*2"]]})
    inject_cached_values(path, "42")
    outputs = outputs_of(path)
    assert "42" in outputs[".table.md"]
    assert "=A1*2" not in body_of(outputs[".table.md"])


# 期待23: 冪等性
def test_idempotent_across_runs(mixed: Path, tmp_path: Path) -> None:
    first = outputs_of(mixed)
    second = outputs_of(mixed)
    for suffix in first:
        assert body_of(first[suffix]) == body_of(second[suffix])


def test_batch_counts_inputs_not_outputs(mixed: Path, tmp_path: Path) -> None:
    result = convert_batch([mixed], BatchOptions(output_dir=tmp_path / "out"))
    assert len(result.succeeded) == 1
    assert len(result.written_files) == 2
