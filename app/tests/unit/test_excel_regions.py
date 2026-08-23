"""U002-T1 の単体テスト: 表領域の検出 (要求①)。

境界条件を厚く置く。特にケース7 (結合セルの境界) とケース15 (行ブロックごとの
列判定) は実装を誤りやすい (P003 §7.4)。
"""

from __future__ import annotations

from itertools import combinations

from office2ragknowledge.models import Cell, MergedRange, SheetRow
from office2ragknowledge.parsers.excel_regions import detect_regions


def mkrows(spec: list[str], *, start_row: int = 1) -> list[SheetRow]:
    """文字列の並びから行を作る。空白文字は空セルを表す。

    例: ``["AB ", "   ", " C "]`` → 1行目に A1,B1、2行目は空、3行目に B3
    """
    rows: list[SheetRow] = []
    for i, line in enumerate(spec):
        row_index = start_row + i
        cells = tuple(
            Cell(row=row_index, col=col + 1, text=ch) for col, ch in enumerate(line) if ch != " "
        )
        rows.append(SheetRow(row_index=row_index, cells=cells))
    return rows


# ケース1: 単一の表 (空行・空列なし)
def test_single_region() -> None:
    rows = mkrows(["AB", "CD"])
    regions, abandoned = detect_regions(rows, [])
    assert len(regions) == 1
    assert (regions[0].top, regions[0].left, regions[0].bottom, regions[0].right) == (1, 1, 2, 2)
    assert abandoned is False


# ケース2: 空行1本で上下2つに分割
def test_split_by_blank_row() -> None:
    rows = mkrows(["AB", "CD", "  ", "EF"])
    regions, _ = detect_regions(rows, [])
    assert len(regions) == 2
    assert (regions[0].top, regions[0].bottom) == (1, 2)
    assert (regions[1].top, regions[1].bottom) == (4, 4)


# ケース3: 空列1本で左右2つに分割
def test_split_by_blank_column() -> None:
    rows = mkrows(["AB CD", "EF GH"])
    regions, _ = detect_regions(rows, [])
    assert len(regions) == 2
    assert (regions[0].left, regions[0].right) == (1, 2)
    assert (regions[1].left, regions[1].right) == (4, 5)


# ケース4: 空行と空列の両方で4領域
def test_split_by_both() -> None:
    rows = mkrows(["AB CD", "     ", "EF GH"])
    regions, _ = detect_regions(rows, [])
    assert len(regions) == 4


# ケース5: 連続する複数の空行が1つの境界として働く
def test_multiple_blank_rows_are_one_boundary() -> None:
    rows = mkrows(["AB", "  ", "  ", "  ", "CD"])
    regions, _ = detect_regions(rows, [])
    assert len(regions) == 2


# ケース6: 先頭・末尾の空行はトリミングされる
def test_leading_and_trailing_blank_rows_are_trimmed() -> None:
    rows = mkrows(["  ", "AB", "  "])
    regions, _ = detect_regions(rows, [])
    assert len(regions) == 1
    assert (regions[0].top, regions[0].bottom) == (2, 2)


# ケース7: 結合セルがある行は空行と判定されない (P002 §1 論点7)
def test_merged_header_row_is_not_treated_as_blank() -> None:
    # A1 に結合見出しがあり、A1:D1 が結合。2行目にデータ。
    rows = [
        SheetRow(row_index=1, cells=(Cell(row=1, col=1, text="2026年度 売上集計"),)),
        SheetRow(
            row_index=2,
            cells=tuple(Cell(row=2, col=c, text=f"h{c}") for c in range(1, 5)),
        ),
        SheetRow(
            row_index=3,
            cells=tuple(Cell(row=3, col=c, text=f"v{c}") for c in range(1, 5)),
        ),
    ]
    merged = [MergedRange(top=1, left=1, bottom=1, right=4)]
    regions, _ = detect_regions(rows, merged)
    # 結合により1行目の B1〜D1 も非空とみなされ、分割されない
    assert len(regions) == 1
    assert (regions[0].top, regions[0].bottom) == (1, 3)
    assert regions[0].right == 4


# ケース8: 結合範囲の左上に値が無ければ非空とみなさない
def test_merged_without_value_is_not_occupied() -> None:
    rows = [
        SheetRow(row_index=1, cells=(Cell(row=1, col=1, text="A"),)),
        SheetRow(row_index=2, cells=()),
        SheetRow(row_index=3, cells=(Cell(row=3, col=1, text="B"),)),
    ]
    # 2行目を覆う結合があるが、左上 (2,1) に Cell が無い
    merged = [MergedRange(top=2, left=1, bottom=2, right=3)]
    regions, _ = detect_regions(rows, merged)
    assert len(regions) == 2


# ケース9: 1セルのみの領域
def test_single_cell_region() -> None:
    rows = mkrows(["A"])
    regions, _ = detect_regions(rows, [])
    assert len(regions) == 1
    assert (regions[0].top, regions[0].left, regions[0].bottom, regions[0].right) == (1, 1, 1, 1)


# ケース10: 上限超過で分割を諦める
def test_abandons_split_when_over_limit() -> None:
    # 市松模様で微小領域を大量に作る (方眼紙シートを表計算モードで処理した状況)
    rows = mkrows(["A A A A A", "         ", "A A A A A", "         ", "A A A A A"])
    regions, abandoned = detect_regions(rows, [], max_regions=2)
    assert abandoned is True
    assert len(regions) == 1
    assert (regions[0].top, regions[0].bottom) == (1, 5)


# ケース11: enabled=False で分割しない
def test_disabled_returns_whole_range() -> None:
    rows = mkrows(["AB", "  ", "CD"])
    regions, abandoned = detect_regions(rows, [], enabled=False)
    assert len(regions) == 1
    assert (regions[0].top, regions[0].bottom) == (1, 3)
    assert abandoned is False


# ケース12: 完全に空のシート
def test_empty_sheet() -> None:
    rows = mkrows(["  ", "  "])
    regions, abandoned = detect_regions(rows, [])
    assert regions == ()
    assert abandoned is False


# ケース13: 領域どうしが重ならない (INV-11)
def test_regions_do_not_overlap() -> None:
    rows = mkrows(["AB CD", "EF GH", "     ", "IJ KL"])
    regions, _ = detect_regions(rows, [])
    assert len(regions) >= 2
    for a, b in combinations(regions, 2):
        assert not a.overlaps(b), f"{a.ref} と {b.ref} が重なっています"


# ケース14: 順序が「上から下、同じ高さなら左から右」
def test_region_order() -> None:
    rows = mkrows(["AB CD", "     ", "EF GH"])
    regions, _ = detect_regions(rows, [])
    keys = [(r.top, r.left) for r in regions]
    assert keys == sorted(keys)


# ケース15: 行ブロックごとに列判定される (使用範囲全体で判定すると誤る)
def test_column_split_is_per_row_block() -> None:
    """上の表が A:C、下の表が E:G のとき、それぞれ独立に検出される。

    使用範囲全体で列判定すると D 列が「全体で空」となり、上下どちらの表も
    D 列で縦に切られてしまう。行ブロックごとに判定すればそうならない。
    """
    rows = mkrows(
        [
            "ABC    ",  # 1行目: A:C
            "DEF    ",  # 2行目: A:C
            "       ",  # 3行目: 空行
            "    GHI",  # 4行目: E:G
            "    JKL",  # 5行目: E:G
        ]
    )
    regions, _ = detect_regions(rows, [])
    assert len(regions) == 2
    upper, lower = regions
    assert (upper.top, upper.bottom, upper.left, upper.right) == (1, 2, 1, 3)
    assert (lower.top, lower.bottom, lower.left, lower.right) == (4, 5, 5, 7)


def test_region_ref_format() -> None:
    rows = mkrows(["ABC", "DEF"])
    regions, _ = detect_regions(rows, [])
    assert regions[0].ref == "A1:C2"


def test_has_header_is_true_by_default() -> None:
    rows = mkrows(["AB", "CD"])
    regions, _ = detect_regions(rows, [])
    assert regions[0].has_header is True
