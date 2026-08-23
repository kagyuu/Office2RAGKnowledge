"""Excel 専用の中間表現 (P002 §7.3.3, §7.3.4)。

**設計の要点**: 表計算モードは結合セルを範囲内に複製し、方眼紙モードは左上を
1回だけ出力する。扱いが正反対であるため、**中間表現は結合を展開せず範囲情報の
まま保持する** (ADR-004 / INV-09)。展開済みのテーブルを持つと、方眼紙モードの
レンダラが複製を取り除けない。
"""

from __future__ import annotations

from dataclasses import dataclass

from .document import Block, ShapeText

__all__ = [
    "Cell",
    "MergedRange",
    "Sheet",
    "SheetRow",
    "TableRegion",
    "col_to_letter",
    "letter_to_col",
]


def col_to_letter(col: int) -> str:
    """1起点の列番号を A1 形式の列名に変換する (1→A, 26→Z, 27→AA)。

    26進数だが 0 に相当する桁が無いため、通常の基数変換ではなく
    「余りが 0 のとき Z として桁借りする」処理が必要である。
    """
    if col < 1:
        raise ValueError(f"列番号は1以上である必要があります: {col}")
    letters = ""
    while col > 0:
        col, rem = divmod(col - 1, 26)
        letters = chr(ord("A") + rem) + letters
    return letters


def letter_to_col(letters: str) -> int:
    """A1 形式の列名を1起点の列番号に変換する (col_to_letter の逆)。"""
    if not letters or not letters.isalpha():
        raise ValueError(f"列名が不正です: {letters!r}")
    col = 0
    for ch in letters.upper():
        col = col * 26 + (ord(ch) - ord("A") + 1)
    return col


@dataclass(frozen=True, slots=True)
class Cell:
    """シートのセル。座標は **1起点**。

    ``text`` は表示形式を適用した後の文字列 (REQ-F-026)。
    ``value_missing`` が真の場合、``text`` には数式文字列が入る (REQ-F-051)。
    """

    row: int
    col: int
    text: str
    is_formula: bool = False
    formula: str | None = None
    value_missing: bool = False


@dataclass(frozen=True, slots=True)
class SheetRow:
    """シートの1行。

    ``cells`` は **非空セルのみ** を列番号の昇順で持つ (INV-08、疎な保持)。
    """

    row_index: int
    cells: tuple[Cell, ...] = ()

    @property
    def is_empty(self) -> bool:
        """この行に非空セルが1つも無いか。"""
        return len(self.cells) == 0


@dataclass(frozen=True, slots=True)
class TableRegion:
    """検出された表領域。1起点の閉区間。"""

    top: int
    left: int
    bottom: int
    right: int
    has_header: bool = True

    @property
    def ref(self) -> str:
        """``A1:D12`` 形式の座標表記 (P002 §5.4.4)。"""
        return f"{col_to_letter(self.left)}{self.top}:{col_to_letter(self.right)}{self.bottom}"

    def overlaps(self, other: TableRegion) -> bool:
        """他の領域と矩形が重なるか (INV-11 の検証に用いる)。"""
        return not (
            self.right < other.left
            or other.right < self.left
            or self.bottom < other.top
            or other.bottom < self.top
        )


@dataclass(frozen=True, slots=True)
class MergedRange:
    """結合範囲。1起点の閉区間。左上セルの値が範囲の代表値。"""

    top: int
    left: int
    bottom: int
    right: int

    def contains(self, row: int, col: int) -> bool:
        """指定座標がこの範囲に含まれるか (境界を含む)。"""
        return self.top <= row <= self.bottom and self.left <= col <= self.right


@dataclass(frozen=True, slots=True)
class Sheet(Block):
    """Excel の1シート。

    表計算モードと方眼紙モードの **両方のレンダラがこの構造を消費する**。
    したがって、どちらのレンダラも必要とする情報をすべて保持する。
    """

    name: str
    rows: tuple[SheetRow, ...] = ()
    """使用範囲の全行。**空行も要素として含む** (INV-07)。

    方眼紙モードが空行を段落境界として使うため、欠番があると構造が壊れる。
    """

    merged: tuple[MergedRange, ...] = ()
    """結合範囲の一覧。**結合は展開せずここに保持する** (INV-09)。"""

    regions: tuple[TableRegion, ...] = ()
    """検出済みの表領域。空シートを除き最低1要素 (INV-10)。"""

    shapes: tuple[ShapeText, ...] = ()
    """このシートに属する図形。**両モードとも章の末尾に出力する** (REQ-F-035)。"""

    hidden: bool = False
    region_split_abandoned: bool = False
    """上限超過により領域分割を諦めたか (REQ-F-057)。"""

    truncated_at: int | None = None
    total_rows: int = 0
    formula_without_cache_count: int = 0
    shape_count: int = 0
    """図形の総数。**テキストを持たない図形も含む**。

    ``shapes`` は INV-05 によりテキストを持つ図形しか保持しないため、
    ``inspect`` の「図形」列 (総数と、うちテキストあり数) を出すには
    このフィールドが要る (P003 §8.3)。
    """

    is_empty: bool = False
