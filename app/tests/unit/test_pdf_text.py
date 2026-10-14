"""U006-T2: 文字から行・文字列を組み立てる規則 (P003 §7A.5。※CR-001)。"""

from __future__ import annotations

from office2ragknowledge.pdf.model import PdfChar
from office2ragknowledge.pdf.text import group_lines, is_cjk, join_lines, line_text, text_of


def _chars(text: str, x: float, top: float, size: float = 10.0, gap: float = 0.0) -> list[PdfChar]:
    """1文字の幅 = size (全角相当)、文字間に gap を空けて並べる。"""
    out: list[PdfChar] = []
    for ch in text:
        out.append(PdfChar(ch, x, top, x + size, top + size, size))
        x += size + gap
    return out


def test_is_cjk() -> None:
    assert is_cjk("あ") and is_cjk("漢") and is_cjk("ア") and is_cjk("、") and is_cjk("Ａ")
    assert not is_cjk("a") and not is_cjk("1") and not is_cjk("") and not is_cjk(" ")


def test_space_between_latin_words() -> None:
    chars = _chars("ab", 0, 0) + _chars("cd", 25, 0)  # 隙間 5pt > 0.25 * 10
    assert line_text(chars) == "ab cd"


def test_no_space_inside_word() -> None:
    assert line_text(_chars("abc", 0, 0, gap=1.0)) == "abc"


def test_no_space_between_japanese_chars() -> None:
    assert line_text(_chars("日本語", 0, 0, gap=3.0)) == "日本語"


def test_wide_gap_in_japanese_gets_space() -> None:
    chars = _chars("日本", 0, 0) + _chars("語", 40, 0)  # 隙間 20pt > 1.0 * 10
    assert line_text(chars) == "日本 語"


def test_existing_space_not_duplicated() -> None:
    chars = _chars("a", 0, 0) + [PdfChar(" ", 10, 0, 20, 10, 10)] + _chars("b", 30, 0)
    assert line_text(chars) == "a b"


def test_fullwidth_space_kept() -> None:
    assert line_text(_chars("第1章　概要", 0, 0)) == "第1章　概要"


def test_join_lines() -> None:
    assert join_lines(["日本語の", "文章です。"]) == "日本語の文章です。"
    assert join_lines(["English", "words"]) == "English words"
    assert join_lines(["値は", "100"]) == "値は100"
    assert join_lines(["version", "日本語"]) == "version日本語"
    assert join_lines(["", " a ", "  "]) == "a"


def test_group_lines_by_vertical_position() -> None:
    chars = _chars("一行目", 0, 0) + _chars("二行目", 0, 20)
    lines = group_lines(chars)
    assert ["".join(c.text for c in line) for line in lines] == ["一行目", "二行目"]


def test_return_to_left_starts_new_line() -> None:
    chars = _chars("abc", 0, 0) + _chars("de", 0, 2)  # ほぼ同じ高さでも左へ戻れば改行
    assert len(group_lines(chars)) == 2


def test_text_of() -> None:
    chars = _chars("日本語の", 0, 0) + _chars("文章", 0, 20)
    assert text_of(chars) == "日本語の文章"
