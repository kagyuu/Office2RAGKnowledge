"""インライン要素と表・リストの構成要素 (P002 §7.3.5, §7.3.6)。"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "InlineRun",
    "ListItem",
    "ShapeParagraph",
    "TableCell",
    "TableRow",
    "make_run",
    "runs_text",
]


@dataclass(frozen=True, slots=True)
class InlineRun:
    """書式を持つテキストの断片。

    ``text`` は **Markdown エスケープ前の生文字列** を保持する (INV-02)。
    エスケープはレンダラの単一責務である。
    """

    text: str
    bold: bool = False
    italic: bool = False
    strike: bool = False
    code: bool = False
    link_url: str | None = None


def make_run(
    text: str,
    *,
    bold: bool = False,
    italic: bool = False,
    strike: bool = False,
    code: bool = False,
    link_url: str | None = None,
) -> InlineRun | None:
    """``InlineRun`` を作る。``text`` が空なら ``None`` を返す (INV-03)。

    空の run は出力に寄与せず、冪等性比較のノイズになるため作らない。
    """
    if not text:
        return None
    return InlineRun(
        text=text, bold=bold, italic=italic, strike=strike, code=code, link_url=link_url
    )


def runs_text(runs: tuple[InlineRun, ...]) -> str:
    """run の並びから、書式を落とした素のテキストを得る。"""
    return "".join(r.text for r in runs)


@dataclass(frozen=True, slots=True)
class ListItem:
    """リストの1項目。``level`` は 0 が最上位。"""

    runs: tuple[InlineRun, ...] = ()
    level: int = 0
    ordered: bool = False


@dataclass(frozen=True, slots=True)
class TableCell:
    """表のセル。

    ``from_merge`` は結合セルの複製由来であることを示す。レンダリングには
    影響しないが、テストと将来の出力調整のために保持する。
    """

    runs: tuple[InlineRun, ...] = ()
    from_merge: bool = False


@dataclass(frozen=True, slots=True)
class TableRow:
    """表の1行。ヘッダ行は表の先頭にのみ出現しうる。"""

    cells: tuple[TableCell, ...] = ()
    is_header: bool = False


@dataclass(frozen=True, slots=True)
class ShapeParagraph:
    """図形内の1段落。

    ``level`` は図形内の箇条書き階層 (SmartArt のノード階層を含む)。
    """

    runs: tuple[InlineRun, ...] = field(default_factory=tuple)
    level: int = 0
