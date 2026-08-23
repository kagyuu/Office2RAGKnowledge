"""U002-T4 の単体テスト: 方眼紙モードのレンダラ (要求③-2)。

**ケース1 (申請書の例) は利用者が指定した仕様そのものであり必須。**
**ケース6 (結合セルの非複製) は表計算モードとの差の中心。**
"""

from __future__ import annotations

from datetime import UTC, datetime

from office2ragknowledge.models import (
    Cell,
    ConvertOptions,
    Document,
    DocumentFormat,
    DocumentMeta,
    ExcelOptions,
    MergedRange,
    Sheet,
    SheetRow,
)
from office2ragknowledge.render.excel_grid import ExcelGridRenderer

NOW = datetime(2026, 8, 24, 10, 0, 0, tzinfo=UTC)


def mksheet(
    cell_map: dict[tuple[int, int], str],
    *,
    name: str = "S1",
    max_row: int | None = None,
    merged: tuple[MergedRange, ...] = (),
    **kwargs: object,
) -> Sheet:
    """(行, 列) → 文字列 から Sheet を作る。空行も欠番なく含める (INV-07)。"""
    last = max_row or (max(r for r, _ in cell_map) if cell_map else 0)
    rows = []
    for r in range(1, last + 1):
        cells = tuple(
            Cell(row=r, col=c, text=text)
            for (rr, c), text in sorted(cell_map.items(), key=lambda kv: kv[0][1])
            if rr == r
        )
        rows.append(SheetRow(row_index=r, cells=cells))
    return Sheet(
        name=name,
        rows=tuple(rows),
        merged=merged,
        regions=(),
        total_rows=last,
        is_empty=not cell_map,
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
    body, stats, _ = ExcelGridRenderer().render(doc, options or ConvertOptions())
    return body, stats


# ケース1 (必須): P001 §7.3 の申請書の例
def test_application_form_example() -> None:
    """利用者が指定した仕様そのもの。

    入力:
        A1「休暇」B1「申請」C1「書」/ 2行目は空 /
        A3「氏名」C3「山田」D3「太郎」/ A4「所属」C4「開発」D4「部」
    期待:
        休暇申請書 / (空行) / 氏名山田太郎 / 所属開発部
    """
    sheet = mksheet(
        {
            (1, 1): "休暇",
            (1, 2): "申請",
            (1, 3): "書",
            (3, 1): "氏名",
            (3, 3): "山田",
            (3, 4): "太郎",
            (4, 1): "所属",
            (4, 3): "開発",
            (4, 4): "部",
        },
        name="申請書",
    )
    body, _ = render(mkdoc(sheet))
    lines = body.splitlines()
    start = lines.index("## 申請書")
    content = [ln for ln in lines[start + 1 :]]
    # 先頭の空行を除いた本文
    while content and not content[0]:
        content.pop(0)
    assert content == ["休暇申請書", "", "氏名山田太郎", "所属開発部"]


# ケース2: 同一行が区切り文字なしで直結される
def test_cells_are_joined_without_separator() -> None:
    sheet = mksheet({(1, 1): "あ", (1, 2): "い", (1, 3): "う"})
    body, _ = render(mkdoc(sheet))
    assert "あいう" in body


# ケース3: grid_separator が効く
def test_grid_separator() -> None:
    sheet = mksheet({(1, 1): "あ", (1, 2): "い"})
    options = ConvertOptions(excel=ExcelOptions(grid_separator=" "))
    body, _ = render(mkdoc(sheet), options)
    assert "あ い" in body


# ケース4: 空行が空行として出力される
def test_blank_row_becomes_blank_line() -> None:
    sheet = mksheet({(1, 1): "上", (3, 1): "下"})
    body, _ = render(mkdoc(sheet))
    lines = body.splitlines()
    i = lines.index("上")
    assert lines[i + 1] == ""
    assert lines[i + 2] == "下"


# ケース5: 連続する3つの空行が1つに畳まれる
def test_consecutive_blank_rows_are_collapsed() -> None:
    sheet = mksheet({(1, 1): "上", (5, 1): "下"})
    body, _ = render(mkdoc(sheet))
    lines = body.splitlines()
    i = lines.index("上")
    assert lines[i + 1] == ""
    assert lines[i + 2] == "下", "連続する空行が畳まれていません"


# ケース6 (必須): 結合セルが1回だけ出力される
def test_merged_cell_is_output_once() -> None:
    """中間表現は結合を展開しない (INV-09) ため、レンダラは何もしない。

    複製されると「休暇申請書休暇申請書休暇申請書」になる。
    """
    sheet = mksheet(
        {(1, 1): "休暇申請書"},
        merged=(MergedRange(top=1, left=1, bottom=1, right=3),),
    )
    body, _ = render(mkdoc(sheet))
    assert body.count("休暇申請書") == 1


# ケース7: テーブル記法が現れない
def test_no_table_markup() -> None:
    sheet = mksheet({(1, 1): "a", (1, 2): "b", (2, 1): "c", (2, 2): "d"})
    body, _ = render(mkdoc(sheet))
    content = [ln for ln in body.splitlines() if not ln.startswith("#")]
    assert not any(ln.startswith("|") for ln in content)
    assert "| --- |" not in body


# ケース8: セル内改行がそのまま保持される (<br> にならない)
def test_newline_is_preserved() -> None:
    sheet = mksheet({(1, 1): "a\nb"})
    body, _ = render(mkdoc(sheet))
    assert "<br>" not in body
    assert "a\nb" in body


# ケース9: formulas=True でも出力が変わらない
def test_formulas_option_is_ignored() -> None:
    sheet = mksheet({(1, 1): "=SUM(A1:A9)"})
    plain, _ = render(mkdoc(sheet))
    with_formulas, _ = render(mkdoc(sheet), ConvertOptions(excel=ExcelOptions(formulas=True)))
    assert plain == with_formulas


# ケース10: 空のシート
def test_empty_sheet() -> None:
    sheet = Sheet(name="空", rows=(), regions=(), is_empty=True)
    body, _ = render(mkdoc(sheet))
    assert "(空のシートです)" in body


# ケース11: 打ち切り注記
def test_truncation_note() -> None:
    base = mksheet({(1, 1): "a"})
    sheet = Sheet(name=base.name, rows=base.rows, regions=(), truncated_at=5, total_rows=100)
    body, _ = render(mkdoc(sheet))
    assert "> ※ このシートは 5 行で打ち切りました (全 100 行)" in body


# ケース12: stats に lines があり tables が無い
def test_stats_has_lines_not_tables() -> None:
    sheet = mksheet({(1, 1): "a", (3, 1): "b"})
    _, stats = render(mkdoc(sheet))
    assert "lines" in stats
    assert "tables" not in stats
    assert stats["lines"] == 2


# ケース13: 行頭の # がエスケープされる
def test_line_start_hash_is_escaped() -> None:
    sheet = mksheet({(1, 1): "# 見出し風"})
    body, _ = render(mkdoc(sheet))
    assert "\\# 見出し風" in body


# ケース14: 行頭でないセルの # はエスケープされない (連結後にエスケープしている)
def test_hash_in_middle_is_not_escaped() -> None:
    sheet = mksheet({(1, 1): "あ", (1, 2): "#タグ"})
    body, _ = render(mkdoc(sheet))
    assert "あ#タグ" in body
    assert "\\#" not in body


# ケース15: 先頭と末尾の空行が残らない
def test_no_leading_or_trailing_blank_lines() -> None:
    sheet = mksheet({(2, 1): "本文"}, max_row=4)
    body, _ = render(mkdoc(sheet))
    lines = body.splitlines()
    i = lines.index("## S1")
    after = lines[i + 1 :]
    while after and not after[0]:
        after.pop(0)
    assert after == ["本文"]


# ケース16: 文書冒頭に # タイトル
def test_document_title() -> None:
    body, _ = render(mkdoc(mksheet({(1, 1): "a"}), title="申請書ブック"))
    assert body.startswith("# 申請書ブック")
