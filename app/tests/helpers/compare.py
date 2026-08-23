"""Markdown の比較ヘルパ (P006 §6)。

front matter の ``converted_at`` は実行のたびに変わるため、冪等性の比較では
front matter を除いて比べる (REQ-NF-018)。
"""

from __future__ import annotations

from office2ragknowledge.render.frontmatter import strip_front_matter

__all__ = ["assert_markdown_equal", "body_of"]


def body_of(markdown: str) -> str:
    """front matter を除いた本文を返す。"""
    return strip_front_matter(markdown)


def assert_markdown_equal(actual: str, expected: str, *, label: str = "") -> None:
    """front matter を除いた本文が一致することを表明する。"""
    a, b = body_of(actual), body_of(expected)
    if a != b:
        import difflib

        diff = "\n".join(
            difflib.unified_diff(b.splitlines(), a.splitlines(), "expected", "actual", lineterm="")
        )
        raise AssertionError(f"Markdown が一致しません{(' ' + label) if label else ''}:\n{diff}")
