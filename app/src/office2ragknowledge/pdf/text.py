"""文字から行・文字列を組み立てる規則 (P003 §7A.5。※CR-001)。

タグ付き PDF の構造要素の中身と、タグなし PDF の行片の両方で使う。
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from .model import PdfChar

__all__ = ["group_lines", "is_cjk", "join_lines", "line_text", "text_of"]

#: 日本語 (CJK) とみなす範囲。連結時に空白を挟まない。
_CJK_RANGES: tuple[tuple[int, int], ...] = (
    (0x3000, 0x30FF),  # CJK 記号と句読点・ひらがな・カタカナ
    (0x3400, 0x9FFF),  # CJK 統合漢字 (拡張A を含む)
    (0xF900, 0xFAFF),  # CJK 互換漢字
    (0xFF00, 0xFFEF),  # 全角形・半角形
)

#: 連続する ASCII の空白類を1つにまとめる (全角空白 U+3000 は残す)。
_ASCII_SPACES = re.compile(r"[ \t\r\n\f\v ]+")


def is_cjk(ch: str) -> bool:
    """文字が CJK (日本語の文字・全角記号) か。"""
    if not ch:
        return False
    code = ord(ch[0])
    return any(lo <= code <= hi for lo, hi in _CJK_RANGES)


def _size(*chars: PdfChar) -> float:
    return max([c.size for c in chars] + [1.0])


def _same_line(prev: PdfChar, ch: PdfChar) -> bool:
    """内容順で隣り合う2文字が同じ行に属するか。"""
    tolerance = 0.5 * max(min(prev.size, ch.size), 1.0)
    if abs(prev.center_y - ch.center_y) > tolerance:
        return False
    # 左へ大きく戻ったら改行とみなす
    return ch.x0 >= prev.x1 - _size(prev, ch)


def group_lines(chars: Sequence[PdfChar]) -> list[list[PdfChar]]:
    """内容順の文字を行に分ける。"""
    lines: list[list[PdfChar]] = []
    for ch in chars:
        if lines and _same_line(lines[-1][-1], ch):
            lines[-1].append(ch)
        else:
            lines.append([ch])
    return lines


def line_text(chars: Sequence[PdfChar]) -> str:
    """1行分の文字を文字列にする。単語間の隙間に空白を補う。"""
    parts: list[str] = []
    prev: PdfChar | None = None
    for ch in chars:
        if prev is not None and not ch.text.isspace() and not prev.text.isspace():
            gap = ch.x0 - prev.x1
            cjk = is_cjk(prev.text[-1]) or is_cjk(ch.text[0])
            threshold = (1.0 if cjk else 0.25) * _size(prev, ch)
            if gap > threshold:
                parts.append(" ")
        parts.append(ch.text)
        prev = ch
    return _ASCII_SPACES.sub(" ", "".join(parts)).strip()


def join_lines(texts: Iterable[str]) -> str:
    """行を連結して1つの文字列にする。日本語の境界では空白を挟まない。"""
    result = ""
    for raw in texts:
        text = raw.strip()
        if not text:
            continue
        if not result:
            result = text
        elif is_cjk(result[-1]) or is_cjk(text[0]):
            result += text
        else:
            result += " " + text
    return result


def text_of(chars: Sequence[PdfChar]) -> str:
    """文字の並びを、行に分けてから連結した文字列にする。"""
    return join_lines(line_text(line) for line in group_lines(chars))
