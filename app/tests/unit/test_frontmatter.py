"""U001-T6 の単体テスト: front matter の生成。

キー順は P001 §7.1 の記載順に固定する (冪等性のため)。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from office2ragknowledge.models import DocumentFormat, DocumentMeta, OutputMode
from office2ragknowledge.render.frontmatter import render_front_matter, strip_front_matter

NOW = datetime(2026, 8, 24, 10, 0, 0, tzinfo=UTC)
CREATED = datetime(2026, 4, 1, 9, 0, 0, tzinfo=UTC)


def full_meta() -> DocumentMeta:
    return DocumentMeta(
        source_file="売上管理.xlsx",
        source_path="docs/2026/売上管理.xlsx",
        source_format=DocumentFormat.XLSX,
        source_size_bytes=1048576,
        source_sha256="a1b2c3",
        converter="office2ragknowledge 1.0.0",
        converted_at=NOW,
        title="2026年度 売上管理",
        author="HONDOH Atsushi",
        created_at=CREATED,
        modified_at=NOW,
        stats={"sheets": 5, "tables": 8},
        warnings=("シート「明細」は 10000 行で打ち切りました",),
    )


def keys_of(text: str) -> list[str]:
    keys = []
    for line in text.splitlines():
        if line in ("---",) or line.startswith(" ") or line.startswith("  -"):
            continue
        key = line.split(":", 1)[0]
        if key:
            keys.append(key)
    return keys


# ケース1: キー順が P001 §7.1 のとおり
def test_key_order_is_fixed() -> None:
    text = render_front_matter(full_meta(), OutputMode.TABLE)
    assert keys_of(text) == [
        "source_file",
        "source_path",
        "source_format",
        "output_mode",
        "source_size_bytes",
        "source_sha256",
        "title",
        "author",
        "created_at",
        "modified_at",
        "converted_at",
        "converter",
        "stats",
        "warnings",
    ]


# ケース2: author が None ならキーごと省略 (null を出さない)
def test_none_author_is_omitted() -> None:
    text = render_front_matter(replace(full_meta(), author=None), None)
    assert "author" not in text
    assert "null" not in text


# ケース3: mode=TABLE で output_mode が出力される
def test_output_mode_table() -> None:
    text = render_front_matter(full_meta(), OutputMode.TABLE)
    assert 'output_mode: "table"' in text


def test_output_mode_grid() -> None:
    text = render_front_matter(full_meta(), OutputMode.GRID)
    assert 'output_mode: "grid"' in text


# ケース4: mode=None で output_mode キーが出ない
def test_output_mode_omitted_when_none() -> None:
    text = render_front_matter(full_meta(), None)
    assert "output_mode" not in text


# ケース5: warnings が空ならキーごと省略
def test_empty_warnings_omitted() -> None:
    text = render_front_matter(replace(full_meta(), warnings=()), None)
    assert "warnings" not in text


# ケース6: stats が2スペースインデントでネスト出力される
def test_stats_are_nested() -> None:
    text = render_front_matter(full_meta(), None)
    assert "stats:\n  sheets: 5\n  tables: 8" in text


def test_empty_stats_omitted() -> None:
    text = render_front_matter(replace(full_meta(), stats={}), None)
    assert "stats" not in text


# ケース7: タイトルの " がエスケープされる
def test_quote_in_title_is_escaped() -> None:
    text = render_front_matter(replace(full_meta(), title='引用"あり"'), None)
    assert '\\"' in text


# ケース8: 日本語が正しく出力される
def test_japanese_values() -> None:
    text = render_front_matter(full_meta(), None)
    assert "売上管理.xlsx" in text
    assert "2026年度 売上管理" in text


# ケース9: --- で始まり --- で終わる
def test_delimiters() -> None:
    text = render_front_matter(full_meta(), None)
    assert text.startswith("---\n")
    assert text.endswith("---\n")


# ケース10: strip_front_matter が front matter を除去する
def test_strip_front_matter() -> None:
    text = render_front_matter(full_meta(), None) + "\n# 本文\n\nテキスト\n"
    assert strip_front_matter(text) == "# 本文\n\nテキスト\n"


# ケース11: front matter を持たない文字列でも壊れない
def test_strip_without_front_matter() -> None:
    body = "# 本文\n\nテキスト\n"
    assert strip_front_matter(body) == body


def test_converted_at_is_the_only_volatile_field() -> None:
    """converted_at 以外は2回生成しても同一である (REQ-NF-018)。"""
    a = render_front_matter(full_meta(), OutputMode.TABLE)
    later = replace(full_meta(), converted_at=datetime(2026, 12, 31, tzinfo=UTC))
    b = render_front_matter(later, OutputMode.TABLE)
    a_lines = [ln for ln in a.splitlines() if not ln.startswith("converted_at")]
    b_lines = [ln for ln in b.splitlines() if not ln.startswith("converted_at")]
    assert a_lines == b_lines
