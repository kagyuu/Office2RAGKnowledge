"""T003 結合テスト: Word と PowerPoint の変換。"""

from __future__ import annotations

from pathlib import Path

from office2ragknowledge import ConvertOptions, convert_file
from tests.helpers.compare import body_of
from tests.helpers.make_office import make_docx, make_pptx


def word(tmp_path: Path) -> Path:
    return make_docx(
        tmp_path / "sample.docx",
        [
            ("h1", "第1章 総則"),
            ("p", "本文の段落です。"),
            ("bullet", "項目A"),
            ("bullet", "項目B"),
            ("number", "手順1"),
            ("h2", "第1節 目的"),
            ("p", "詳細な説明。"),
        ],
    )


def pptx(tmp_path: Path) -> Path:
    return make_pptx(
        tmp_path / "sample.pptx",
        [("表紙", ["要点1", "要点2"], "発表者ノート"), (None, ["本文のみ"], None)],
    )


# Word 期待1〜4
def test_word_single_output(tmp_path: Path) -> None:
    result = convert_file(word(tmp_path))
    assert len(result.outputs) == 1
    assert result.outputs[0].filename_suffix == ".md"


def test_word_no_output_mode(tmp_path: Path) -> None:
    # 一時ディレクトリ名が source_path に入るため、front matter のキーとして
    # 行頭に現れないことを確認する
    markdown = convert_file(word(tmp_path)).markdown
    assert not any(ln.startswith("output_mode:") for ln in markdown.splitlines())


def test_word_document_title(tmp_path: Path) -> None:
    body = body_of(convert_file(word(tmp_path)).markdown)
    assert body.startswith("# sample")


def test_word_heading_levels(tmp_path: Path) -> None:
    body = body_of(convert_file(word(tmp_path)).markdown)
    assert "## 第1章 総則" in body
    assert "### 第1節 目的" in body


# Word 期待5
def test_word_list_structure(tmp_path: Path) -> None:
    body = body_of(convert_file(word(tmp_path)).markdown)
    assert "- 項目A" in body
    assert "- 項目B" in body
    assert "1. 手順1" in body


# Word 期待10/11
def test_word_no_headers_by_default(tmp_path: Path) -> None:
    body = body_of(convert_file(word(tmp_path)).markdown)
    assert "## ヘッダー" not in body


def test_word_no_horizontal_rule(tmp_path: Path) -> None:
    body = body_of(convert_file(word(tmp_path)).markdown)
    assert "\n---\n" not in body


# PowerPoint 期待17〜21
def test_pptx_slide_headings(tmp_path: Path) -> None:
    body = body_of(convert_file(pptx(tmp_path)).markdown)
    assert "## スライド 1: 表紙" in body
    assert "## スライド 2" in body


def test_pptx_notes(tmp_path: Path) -> None:
    body = body_of(convert_file(pptx(tmp_path)).markdown)
    assert "### ノート" in body
    assert "発表者ノート" in body


def test_pptx_no_notes_option(tmp_path: Path) -> None:
    body = body_of(convert_file(pptx(tmp_path), ConvertOptions(notes=False)).markdown)
    assert "### ノート" not in body


# 期待25: マスター由来の文言が出ない
def test_pptx_no_master_text(tmp_path: Path) -> None:
    body = body_of(convert_file(pptx(tmp_path)).markdown)
    assert "Click to edit" not in body


# 期待16/26: 冪等性
def test_word_and_pptx_are_idempotent(tmp_path: Path) -> None:
    for path in (word(tmp_path), pptx(tmp_path)):
        first = body_of(convert_file(path).markdown)
        second = body_of(convert_file(path).markdown)
        assert first == second, path.name
