"""タグなし PDF のレイアウト (P003 §7A.6〜7A.9。※CR-001・CR-002)。

タグなし PDF では構造を推定しない (ADR-013)。ページ上の文字の座標から、
行片 → 図ユニット → 読み順 → 段落 の順に組み立てる。

決定性 (REQ-NF-018 / REQ-F-128): 座標は 0.01pt に丸めてから比較し、並べ替えの
キーは (座標, 文字列) の全順序とする。集合の反復順に依存しない。
"""

from __future__ import annotations

import math
import re
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from .model import PdfChar, PdfPage, PdfSource, Rect
from .text import join_lines, line_text

__all__ = [
    "FigureUnit",
    "Fragment",
    "LayoutBlock",
    "LayoutResult",
    "build_fragments",
    "build_paragraphs",
    "extract_figures",
    "layout_document",
    "normalize_repeat_key",
    "order_units",
    "remove_headers_footers",
]

#: 行片を分ける文字間の隙間 (文字サイズに対する比)。段間・表の列間はここで分かれる。
FRAGMENT_GAP = 1.0

#: 図領域とみなす矩形の最小の幅・高さ (pt)。下線・区切り線を除く。
FIGURE_MIN_SIDE = 5.0

#: 図領域とみなす矩形の面積の上限 (ページ面積に対する比)。ページ全体の枠・背景を除く。
FIGURE_MAX_AREA = 0.8

#: 図領域の内側の判定の許容 (pt)。
FIGURE_TOLERANCE = 2.0

#: 段落を区切る行間の隙間 (文字サイズに対する比)。
PARAGRAPH_GAP = 0.8

#: 段落を区切る文字サイズの変化の割合。
SIZE_CHANGE = 0.2

#: ヘッダー・フッター帯の高さ (ページの高さに対する比。ADR-014)。
HEADER_FOOTER_BAND = 0.10

#: ヘッダー・フッターとみなす出現ページの割合の下限 (ADR-014)。
HEADER_FOOTER_MIN_RATIO = 0.3

#: 段の片側に必要なユニットの数 (P003 §7A.9)。
COLUMN_MIN_UNITS = 3

#: 左右の段の縦の範囲の重なりの下限 (低い方の高さに対する比)。
COLUMN_MIN_OVERLAP = 0.5

#: 段の幅の下限 (内容の幅に対する比)。項目名と値が並ぶ書式を段組みと誤認しないため。
COLUMN_MIN_WIDTH = 0.2


def _r(value: float) -> float:
    return round(value, 2)


@dataclass(frozen=True, slots=True)
class Fragment:
    """行片。1行のうち、大きな隙間で区切られた一続きの文字列。"""

    page: int
    text: str
    x0: float
    top: float
    x1: float
    bottom: float
    size: float

    @property
    def center_y(self) -> float:
        return (self.top + self.bottom) / 2


@dataclass(frozen=True, slots=True)
class FigureUnit:
    """図領域とその内側の行。"""

    page: int
    x0: float
    top: float
    x1: float
    bottom: float
    lines: tuple[str, ...]


Unit = Fragment | FigureUnit


@dataclass(frozen=True, slots=True)
class OrderedUnit:
    """読み順に並べたユニットと、その属する区画 (段・区間)。"""

    unit: Unit
    region: tuple[int, int] = (0, 0)
    """(区間の番号, 段の番号)。段落の区切りの判定に使う。"""


@dataclass(frozen=True, slots=True)
class LayoutBlock:
    """出力の単位。段落または図。"""

    kind: Literal["paragraph", "figure"]
    text: str = ""
    lines: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LayoutResult:
    blocks: tuple[LayoutBlock, ...]
    headers_footers_removed: int = 0
    multi_column_pages: int = 0


# ---------------------------------------------------------------------------
# 行片 (P003 §7A.6)
# ---------------------------------------------------------------------------


def _cluster_rows(chars: Sequence[PdfChar]) -> list[list[PdfChar]]:
    """文字を縦の中心の近さで行にまとめる。各行は左から右に並べる。"""
    ordered = sorted(chars, key=lambda c: (_r(c.center_y), _r(c.x0), c.text))
    rows: list[list[PdfChar]] = []
    for ch in ordered:
        if rows:
            ref = rows[-1][0]
            if ch.center_y - ref.center_y <= 0.5 * max(min(ref.size, ch.size), 1.0):
                rows[-1].append(ch)
                continue
        rows.append([ch])
    return [sorted(row, key=lambda c: (_r(c.x0), c.text)) for row in rows]


def _make_fragment(page: int, chars: list[PdfChar]) -> Fragment | None:
    text = line_text(chars)
    visible = [c for c in chars if not c.text.isspace()]
    if not text or not visible:
        return None
    return Fragment(
        page=page,
        text=text,
        x0=_r(min(c.x0 for c in visible)),
        top=_r(min(c.top for c in visible)),
        x1=_r(max(c.x1 for c in visible)),
        bottom=_r(max(c.bottom for c in visible)),
        size=_r(statistics.median(c.size for c in visible)),
    )


def build_fragments(page: PdfPage) -> list[Fragment]:
    """ページの文字を行片にする。"""
    fragments: list[Fragment] = []
    for row in _cluster_rows(page.chars):
        current: list[PdfChar] = []
        last: PdfChar | None = None
        for ch in row:
            if ch.text.isspace():
                current.append(ch)
                continue
            if last is not None and ch.x0 - last.x1 > FRAGMENT_GAP * max(last.size, ch.size, 1.0):
                fragment = _make_fragment(page.number, current)
                if fragment is not None:
                    fragments.append(fragment)
                current = []
            current.append(ch)
            last = ch
        fragment = _make_fragment(page.number, current)
        if fragment is not None:
            fragments.append(fragment)
    return fragments


# ---------------------------------------------------------------------------
# ヘッダー・フッター (P003 §7A.7。※CR-002)
# ---------------------------------------------------------------------------

_DIGITS = re.compile(r"[0-9０-９]+")
_ROMAN = re.compile(r"^[ivxlcdmIVXLCDM\u2160-\u217f]+$")
_SPACES = re.compile(r"\s+")


def normalize_repeat_key(text: str) -> str:
    """繰り返しの判定に使うキー。空白を除き、数字の並びを ``#`` にする。

    例: ``- 12 -`` → ``-#-``、``3 / 10`` → ``#/#``、``iv`` → ``#``
    """
    compact = _SPACES.sub("", text)
    if _ROMAN.match(compact):
        return "#"
    return _DIGITS.sub("#", compact)


def _band(fragment: Fragment, page: PdfPage) -> str | None:
    limit = page.height * HEADER_FOOTER_BAND
    if fragment.center_y <= limit:
        return "top"
    if fragment.center_y >= page.height - limit:
        return "bottom"
    return None


def remove_headers_footers(
    pages: Sequence[PdfPage], fragments: Sequence[Sequence[Fragment]]
) -> tuple[list[list[Fragment]], int]:
    """ページ上下の帯に繰り返し現れる行片を除く。(残った行片, 除去数) を返す。

    総ページ数 ``n`` に対し、2ページ以上かつ ``ceil(0.3 n)`` ページ以上に現れる
    (帯, 正規化テキスト) をヘッダー・フッターとする。1ページだけの文書と、
    1ページにしか現れないテキストは除去しない (REQ-F-122)。
    """
    n = len(pages)
    if n < 2:
        return [list(f) for f in fragments], 0
    seen: dict[tuple[str, str], set[int]] = {}
    for page, page_fragments in zip(pages, fragments, strict=True):
        for f in page_fragments:
            band = _band(f, page)
            if band is not None:
                seen.setdefault((band, normalize_repeat_key(f.text)), set()).add(page.number)
    needed = max(2, math.ceil(HEADER_FOOTER_MIN_RATIO * n))
    targets = {key for key, numbers in seen.items() if len(numbers) >= needed}
    kept: list[list[Fragment]] = []
    removed = 0
    for page, page_fragments in zip(pages, fragments, strict=True):
        page_kept = []
        for f in page_fragments:
            band = _band(f, page)
            if band is not None and (band, normalize_repeat_key(f.text)) in targets:
                removed += 1
            else:
                page_kept.append(f)
        kept.append(page_kept)
    return kept, removed


# ---------------------------------------------------------------------------
# 図領域 (P003 §7A.8)
# ---------------------------------------------------------------------------


def _figure_candidates(page: PdfPage) -> list[Rect]:
    page_area = page.width * page.height
    result = []
    for x0, top, x1, bottom in page.figure_rects:
        w, h = x1 - x0, bottom - top
        if w > FIGURE_MIN_SIDE and h > FIGURE_MIN_SIDE and w * h < FIGURE_MAX_AREA * page_area:
            result.append((_r(x0), _r(top), _r(x1), _r(bottom)))
    return sorted(set(result))


def _inside(f: Fragment, rect: Rect) -> bool:
    x0, top, x1, bottom = rect
    t = FIGURE_TOLERANCE
    return f.x0 >= x0 - t and f.x1 <= x1 + t and f.top >= top - t and f.bottom <= bottom + t


def _rows_of(fragments: Sequence[Fragment]) -> list[list[Fragment]]:
    """行片を同じ高さの行にまとめる (上から下、行内は左から右)。"""
    ordered = sorted(fragments, key=lambda f: (f.center_y, f.x0, f.text))
    rows: list[list[Fragment]] = []
    for f in ordered:
        if rows and abs(f.center_y - rows[-1][0].center_y) <= 0.5 * max(f.size, 1.0):
            rows[-1].append(f)
        else:
            rows.append([f])
    return [sorted(row, key=lambda f: (f.x0, f.text)) for row in rows]


def extract_figures(
    page: PdfPage, fragments: Sequence[Fragment]
) -> tuple[list[FigureUnit], list[Fragment]]:
    """図領域に収まる行片を図ユニットにまとめ、残りの行片と分けて返す。"""
    candidates = _figure_candidates(page)
    members: dict[Rect, list[Fragment]] = {}
    rest: list[Fragment] = []
    for f in fragments:
        containing = [rect for rect in candidates if _inside(f, rect)]
        if not containing:
            rest.append(f)
            continue
        smallest = min(containing, key=lambda r: ((r[2] - r[0]) * (r[3] - r[1]), r))
        members.setdefault(smallest, []).append(f)
    figures = []
    for rect in sorted(members):
        lines = tuple(" ".join(f.text for f in row) for row in _rows_of(members[rect]))
        figures.append(FigureUnit(page.number, rect[0], rect[1], rect[2], rect[3], lines))
    return figures, rest


# ---------------------------------------------------------------------------
# 読み順 (P003 §7A.9)
# ---------------------------------------------------------------------------


def _unit_key(unit: Unit) -> tuple[float, float, str]:
    text = unit.text if isinstance(unit, Fragment) else "\n".join(unit.lines)
    return (unit.top, unit.x0, text)


def _body_size(units: Sequence[Unit]) -> float:
    sizes = [u.size for u in units if isinstance(u, Fragment)]
    return float(statistics.median(sizes)) if sizes else 10.0


def find_gutters(units: Sequence[Unit]) -> list[tuple[float, float]]:
    """段間 (縦の空白の帯) を確定して返す (P003 §7A.9 の手順1・2)。"""
    if len(units) < 2 * COLUMN_MIN_UNITS:
        return []
    left = min(u.x0 for u in units)
    right = max(u.x1 for u in units)
    width = int(math.ceil(right - left))
    if width <= 0:
        return []
    coverage = [0] * (width + 1)
    for u in units:
        start = max(0, int(math.floor(u.x0 - left)) + 1)
        end = min(width, int(math.ceil(u.x1 - left)) - 1)
        for p in range(start, end + 1):
            coverage[p] += 1
    threshold = max(2, len(units) // 10)
    min_width = _body_size(units)
    runs: list[tuple[int, int]] = []
    p = 0
    while p <= width:
        if coverage[p] <= threshold:
            q = p
            while q + 1 <= width and coverage[q + 1] <= threshold:
                q += 1
            if p > 0 and q < width and q - p + 1 >= min_width:
                runs.append((p, q))
            p = q + 1
        else:
            p += 1
    gutters = []
    for p0, p1 in runs:
        g0, g1 = left + p0, left + p1
        lefts = [u for u in units if u.x1 <= g0 + 0.5]
        rights = [u for u in units if u.x0 >= g1 - 0.5]
        if len(lefts) < COLUMN_MIN_UNITS or len(rights) < COLUMN_MIN_UNITS:
            continue
        # 段の幅は段抜き要素を含めず、左右のユニット群だけで測る
        l_x0 = min(u.x0 for u in lefts)
        r_x1 = max(u.x1 for u in rights)
        if min(g0 - l_x0, r_x1 - g1) < COLUMN_MIN_WIDTH * (r_x1 - l_x0):
            continue
        l_top, l_bottom = min(u.top for u in lefts), max(u.bottom for u in lefts)
        r_top, r_bottom = min(u.top for u in rights), max(u.bottom for u in rights)
        overlap = min(l_bottom, r_bottom) - max(l_top, r_top)
        if overlap < COLUMN_MIN_OVERLAP * min(l_bottom - l_top, r_bottom - r_top):
            continue
        gutters.append((_r(g0), _r(g1)))
    return gutters


def order_units(page: PdfPage, units: Sequence[Unit]) -> tuple[list[OrderedUnit], bool]:
    """ユニットを読み順に並べる。(並べた結果, 段組みを検出したか) を返す。

    段組みの無いページは、上から下、同じ高さでは左から右とする。段組みを検出した
    ページは、段抜き要素で区間に分け、区間ごとに左の段から右の段へ、各段を上から
    下へ読む (P003 §7A.9。※CR-002)。
    """
    del page
    gutters = find_gutters(units)
    if not gutters:
        return [OrderedUnit(u) for u in sorted(units, key=_unit_key)], False
    mids = sorted((g0 + g1) / 2 for g0, g1 in gutters)

    def spans(u: Unit) -> bool:
        return any(u.x0 < m < u.x1 for m in mids)

    spanners = sorted((u for u in units if spans(u)), key=_unit_key)
    sections: list[list[list[Unit]]] = [
        [[] for _ in range(len(mids) + 1)] for _ in range(len(spanners) + 1)
    ]
    for u in units:
        if spans(u):
            continue
        center_y = (u.top + u.bottom) / 2
        section = sum(1 for s in spanners if (s.top + s.bottom) / 2 < center_y)
        column = sum(1 for m in mids if m < (u.x0 + u.x1) / 2)
        sections[section][column].append(u)
    ordered: list[OrderedUnit] = []
    for index, columns in enumerate(sections):
        for column_index, members in enumerate(columns):
            for u in sorted(members, key=_unit_key):
                ordered.append(OrderedUnit(u, (index, column_index)))
        if index < len(spanners):
            ordered.append(OrderedUnit(spanners[index], (index, -1)))
    return ordered, True


# ---------------------------------------------------------------------------
# 段落 (P003 §7A.9 の段落の組み立て)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _Line:
    top: float
    bottom: float
    size: float
    region: tuple[int, int]
    parts: list[str]

    @property
    def center_y(self) -> float:
        return (self.top + self.bottom) / 2


def _breaks_paragraph(prev: _Line, line: _Line) -> bool:
    if line.region != prev.region:
        return True
    if line.top < prev.top:  # 上へ戻った (別の流れ)
        return True
    size = max(prev.size, line.size, 1.0)
    if line.top - prev.bottom > PARAGRAPH_GAP * size:
        return True
    return abs(prev.size - line.size) / size > SIZE_CHANGE


def build_paragraphs(ordered: Sequence[OrderedUnit]) -> list[LayoutBlock]:
    """読み順に並んだユニットを、段落と図のブロックにする。"""
    blocks: list[LayoutBlock] = []
    lines: list[_Line] = []

    def flush() -> None:
        if lines:
            text = join_lines(" ".join(line.parts) for line in lines)
            if text:
                blocks.append(LayoutBlock("paragraph", text=text))
            lines.clear()

    for item in ordered:
        unit = item.unit
        if isinstance(unit, FigureUnit):
            flush()
            blocks.append(LayoutBlock("figure", lines=unit.lines))
            continue
        if lines:
            last = lines[-1]
            same_row = abs(unit.center_y - last.center_y) <= 0.5 * max(unit.size, 1.0)
            if same_row and item.region == last.region and unit.top >= last.top - unit.size:
                last.parts.append(unit.text)
                last.bottom = max(last.bottom, unit.bottom)
                continue
        line = _Line(unit.top, unit.bottom, unit.size, item.region, [unit.text])
        if lines and _breaks_paragraph(lines[-1], line):
            flush()
        lines.append(line)
    flush()
    return blocks


# ---------------------------------------------------------------------------
# 文書全体
# ---------------------------------------------------------------------------


def layout_document(source: PdfSource, *, shapes: bool, headers_footers: bool) -> LayoutResult:
    """タグなし PDF の全ページをレイアウトし、ブロックの並びを返す。

    Args:
        shapes: 図領域を図ユニットにするか (偽なら枠内の文字も本文に残す)
        headers_footers: ヘッダー・フッターを出力するか (偽なら除去する。REQ-F-124)
    """
    blocks: list[LayoutBlock] = []
    multi_column = 0
    all_fragments = [build_fragments(page) for page in source.pages]
    removed = 0
    if not headers_footers:
        all_fragments, removed = remove_headers_footers(source.pages, all_fragments)
    for page, fragments in zip(source.pages, all_fragments, strict=True):
        units: list[Unit]
        if shapes:
            figures, rest = extract_figures(page, fragments)
            units = [*figures, *rest]
        else:
            units = list(fragments)
        ordered, columns = order_units(page, units)
        multi_column += int(columns)
        blocks.extend(build_paragraphs(ordered))
    return LayoutResult(tuple(blocks), removed, multi_column)
