"""Markdown のエスケープ (P002 §5.1 / REQ-F-009)。

**行頭の構造記号のみ** をエスケープする。行中の ``*`` ``_`` `` ` `` ``[`` ``]``
はエスケープしない (ADR-010)。日本語文書では ``_`` を含む識別子や ``*`` を含む
注記が頻出し、全エスケープすると本文がバックスラッシュだらけになって埋め込み
品質を落とすためである。
"""

from __future__ import annotations

import re

__all__ = ["escape_cell", "escape_line", "escape_text"]

#: 行頭の構造記号。順序に意味はないが、最初に一致したものだけをエスケープする。
_LINE_START_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^(\s*)(#)"),  # 見出し
    re.compile(r"^(\s*)([-*+])(?=\s)"),  # 箇条書き (直後が空白のときのみ)
    re.compile(r"^(\s*)(>)"),  # 引用
    re.compile(r"^(\s*)(\d+)(?=\.\s)"),  # 番号付きリスト
)

_CODE_FENCE = re.compile(r"^(\s*)(```|~~~)")


def escape_line(text: str) -> str:
    """1行または複数行のテキストを、行頭の構造記号についてエスケープする。

    複数行の場合は各行に個別に適用する。
    """
    if not text:
        return text
    return "\n".join(_escape_single_line(line) for line in text.split("\n"))


def _escape_single_line(line: str) -> str:
    fence = _CODE_FENCE.match(line)
    if fence is not None:
        indent, marker = fence.group(1), fence.group(2)
        return f"{indent}\\{marker}{line[fence.end() :]}"

    for pattern in _LINE_START_PATTERNS:
        m = pattern.match(line)
        if m is None:
            continue
        indent, marker = m.group(1), m.group(2)
        if marker.isdigit():
            # 番号付きリストは数字の直後の "." をエスケープする
            rest = line[m.end() :]
            return f"{indent}{marker}\\{rest}"
        return f"{indent}\\{marker}{line[m.end() :]}"
    return line


def escape_cell(text: str) -> str:
    """GFM テーブルのセル用にエスケープする。

    ``|`` は列区切りと解釈されるためエスケープし、改行はセル内では表現できない
    ため ``<br>`` に置換する (REQ-F-028)。
    """
    if not text:
        return text
    return (
        text.replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "<br>")
    )


def escape_text(text: str) -> str:
    """``escape_line`` の別名。呼び出し側の意図を読みやすくするために用意する。"""
    return escape_line(text)
