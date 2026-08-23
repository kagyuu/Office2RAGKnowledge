"""U001-T6 の単体テスト: Markdown エスケープ。

**行頭の構造記号のみ**をエスケープし、行中の記号はエスケープしない (ADR-010)。
"""

from __future__ import annotations

from office2ragknowledge.render.escape import escape_cell, escape_line


# ケース1: 行頭の # がエスケープされる
def test_heading_marker_is_escaped() -> None:
    assert escape_line("# 見出し") == "\\# 見出し"


# ケース2: 行頭の - がエスケープされる
def test_bullet_marker_is_escaped() -> None:
    assert escape_line("- 項目") == "\\- 項目"
    assert escape_line("* 項目") == "\\* 項目"
    assert escape_line("+ 項目") == "\\+ 項目"


# ケース3: 直後が空白でない行頭の - はエスケープされない
def test_hyphen_without_space_is_not_escaped() -> None:
    assert escape_line("-abc") == "-abc"
    assert escape_line("-1.5") == "-1.5"


# ケース4: 行頭の > がエスケープされる
def test_quote_marker_is_escaped() -> None:
    assert escape_line("> 引用") == "\\> 引用"


# ケース5: 行頭の番号付きリスト
def test_ordered_list_marker_is_escaped() -> None:
    assert escape_line("1. 項目") == "1\\. 項目"
    assert escape_line("12. 項目") == "12\\. 項目"


def test_number_without_space_is_not_escaped() -> None:
    assert escape_line("1.5 倍") == "1.5 倍"


# ケース6: 行中の * はエスケープされない
def test_inline_asterisk_is_not_escaped() -> None:
    assert escape_line("a*b*c") == "a*b*c"


# ケース7: 行中の _ はエスケープされない (日本語文書での過剰エスケープ防止)
def test_inline_underscore_is_not_escaped() -> None:
    assert escape_line("snake_case_name") == "snake_case_name"
    assert escape_line("値は `code` です") == "値は `code` です"
    assert escape_line("参照[1]を見よ") == "参照[1]を見よ"


# ケース8: セル内の | がエスケープされる
def test_cell_pipe_is_escaped() -> None:
    assert escape_cell("a|b") == "a\\|b"


# ケース9: セル内改行が <br> になる
def test_cell_newline_becomes_br() -> None:
    assert escape_cell("a\nb") == "a<br>b"
    assert escape_cell("a\r\nb") == "a<br>b"


# ケース10: 複数行で2行目の行頭も個別にエスケープされる
def test_multiline_each_line_is_escaped() -> None:
    assert escape_line("本文\n# 見出し") == "本文\n\\# 見出し"
    assert escape_line("# あ\n# い") == "\\# あ\n\\# い"


# ケース11: 日本語テキストがそのまま保持される
def test_japanese_text_is_preserved() -> None:
    text = "これは日本語のテキストです。①㈱髙﨑"
    assert escape_line(text) == text


def test_code_fence_is_escaped() -> None:
    assert escape_line("```python") == "\\```python"


def test_empty_string() -> None:
    assert escape_line("") == ""
    assert escape_cell("") == ""
