"""表領域の検出 (要求① / REQ-F-023, REQ-F-054〜057)。

1シート内に複数の表が並んでいる場合に、空行・空列を境界として独立した表領域に
分割する。使用範囲を丸ごと1つの表にすると、列がずれて各表の意味が失われるため。

**中間表現のみを扱う純粋関数**であり、openpyxl に依存しない。
計算量は使用範囲の行数 R・列数 C に対して O(R×C)。
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from ..models import Cell, MergedRange, SheetRow, TableRegion

__all__ = ["detect_regions"]

#: (行, 列) を受け取り、そのセルが非空かを返す判定関数。
OccupiedFn = Callable[[int, int], bool]


def _build_index(rows: Sequence[SheetRow]) -> dict[tuple[int, int], Cell]:
    """(行, 列) → Cell の索引を作る。毎回の線形探索を避けるため。"""
    return {(cell.row, cell.col): cell for row in rows for cell in row.cells}


def _make_occupied_fn(
    index: dict[tuple[int, int], Cell], merged: Sequence[MergedRange]
) -> OccupiedFn:
    """セルが非空かを判定する関数を作る。

    **結合範囲に含まれるセルは、範囲の左上に値があれば範囲全体を非空とみなす。**
    これがないと、複数列にまたがる結合見出しの行が空行と判定され、その下の表と
    不当に分割される (P002 §1 論点7)。
    """
    occupied_merges = [rng for rng in merged if (rng.top, rng.left) in index]

    def is_occupied(row: int, col: int) -> bool:
        if (row, col) in index:
            return True
        return any(rng.contains(row, col) for rng in occupied_merges)

    return is_occupied


def _used_bounds(rows: Sequence[SheetRow]) -> tuple[int, int, int, int] | None:
    """使用範囲 (top, left, bottom, right) を求める。非空セルが無ければ None。"""
    positions = [(cell.row, cell.col) for row in rows for cell in row.cells]
    if not positions:
        return None
    return (
        min(r for r, _ in positions),
        min(c for _, c in positions),
        max(r for r, _ in positions),
        max(c for _, c in positions),
    )


def _trim(
    top: int, left: int, bottom: int, right: int, is_occupied: OccupiedFn
) -> tuple[int, int, int, int] | None:
    """実際に非空セルが存在する範囲まで境界を収縮させる。"""
    rows_with_data = [
        r for r in range(top, bottom + 1) if any(is_occupied(r, c) for c in range(left, right + 1))
    ]
    if not rows_with_data:
        return None
    cols_with_data = [
        c for c in range(left, right + 1) if any(is_occupied(r, c) for r in range(top, bottom + 1))
    ]
    if not cols_with_data:
        return None
    return rows_with_data[0], cols_with_data[0], rows_with_data[-1], cols_with_data[-1]


def _split_runs(start: int, end: int, has_data: Callable[[int], bool]) -> list[tuple[int, int]]:
    """``start``〜``end`` を、データを持たない位置を境界に連続区間へ分割する。"""
    runs: list[tuple[int, int]] = []
    run_start: int | None = None
    for i in range(start, end + 1):
        if has_data(i):
            if run_start is None:
                run_start = i
        elif run_start is not None:
            runs.append((run_start, i - 1))
            run_start = None
    if run_start is not None:
        runs.append((run_start, end))
    return runs


def detect_regions(
    rows: Sequence[SheetRow],
    merged: Sequence[MergedRange],
    *,
    enabled: bool = True,
    max_regions: int = 100,
) -> tuple[tuple[TableRegion, ...], bool]:
    """表領域を検出する。

    Args:
        rows: 使用範囲の全行 (空行を含む)
        merged: 結合範囲
        enabled: 分割検出を行うか (REQ-F-056)
        max_regions: 領域数の上限 (REQ-F-057)

    Returns:
        (検出した領域, 上限超過により分割を諦めたか)

    領域が0件かつ使用範囲が存在する場合は、使用範囲全体を1領域として返す
    (INV-10)。分割の性質上、領域どうしが重なることは構造的に生じない (INV-11)。
    """
    index = _build_index(rows)
    is_occupied = _make_occupied_fn(index, merged)
    bounds = _used_bounds(rows)
    if bounds is None:
        return (), False
    top, left, bottom, right = bounds

    whole = TableRegion(top=top, left=left, bottom=bottom, right=right)
    if not enabled:
        return (whole,), False

    # 手順2: 完全に空の行で水平分割する。空行自体はどの領域にも属さない。
    row_blocks = _split_runs(
        top, bottom, lambda r: any(is_occupied(r, c) for c in range(left, right + 1))
    )

    regions: list[TableRegion] = []
    for block_top, block_bottom in row_blocks:
        # 手順3: **その行ブロック内で** 空列を境界に垂直分割する。
        # 使用範囲全体で列判定すると、上下の表で列位置が異なる場合に分割が効かない。
        col_blocks = _split_runs(
            left,
            right,
            lambda c, t=block_top, b=block_bottom: any(  # type: ignore[misc]
                is_occupied(r, c) for r in range(t, b + 1)
            ),
        )
        for block_left, block_right in col_blocks:
            trimmed = _trim(block_top, block_left, block_bottom, block_right, is_occupied)
            if trimmed is None:
                continue
            t, ln, b, rt = trimmed
            regions.append(TableRegion(top=t, left=ln, bottom=b, right=rt))

    # 手順6: 上限を超えたら分割を破棄する。
    # 方眼紙シートを表計算モードで処理すると微小領域が乱立し、出力が破綻するため。
    if len(regions) > max_regions:
        return (whole,), True

    if not regions:
        return (whole,), False

    # 手順5: 上から下、同じ高さなら左から右
    regions.sort(key=lambda reg: (reg.top, reg.left))
    return tuple(regions), False
