"""T006 結合テスト: PDF 変換の連携 (※CR-001・CR-002)。

形式判定 → pdf/backend → 構造木 / レイアウト → PdfParser → 中間表現 →
MarkdownRenderer → ファイル出力、および CLI (convert / inspect) を通して検証する。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from office2ragknowledge import convert_bytes
from office2ragknowledge.cli.main import app
from office2ragknowledge.render.frontmatter import strip_front_matter
from tests.helpers.make_office import make_docx
from tests.helpers.pdf_samples import (
    LEFT_LINES,
    RIGHT_LINES,
    broken_pdf,
    copy_restricted_pdf,
    locked_pdf,
    scanned_page_pdf,
    single_page_pdf,
    tagged_report_pdf,
    two_column_report_pdf,
)

runner = CliRunner()


def _front(md: str) -> str:
    return md.split("\n---\n", 1)[0]


def _body(md: str) -> str:
    return strip_front_matter(md)


@pytest.fixture
def report_md(tmp_path: Path) -> str:
    src = tmp_path / "report.pdf"
    src.write_bytes(tagged_report_pdf())
    out = tmp_path / "out"
    result = runner.invoke(app, ["convert", str(src), "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert sorted(p.name for p in out.iterdir()) == ["report.md"]
    return (out / "report.md").read_text(encoding="utf-8")


# 期待1: 出力ファイルと front matter
def test_tagged_front_matter(report_md: str) -> None:
    lines = report_md.splitlines()
    assert lines[3] == 'source_format: "pdf"'
    assert lines[4] == 'pdf_structure: "tagged"'
    assert 'title: "PDF変換の報告書"' in report_md
    assert 'author: "山田太郎"' in report_md


# 期待2: 見出し
def test_tagged_headings(report_md: str) -> None:
    body = _body(report_md)
    heading_lines = [line for line in body.splitlines() if line.startswith("#")]
    assert heading_lines == ["# PDF変換の報告書", "# 第1章 概要", "## 1.1 背景", "### 1.1.1 詳細"]


# 期待3: リスト
def test_tagged_nested_list(report_md: str) -> None:
    assert "- 項目A\n  - 子項目A-1\n    - 孫項目A-1-a\n- 項目B" in report_md


# 期待4: 表
def test_tagged_table(report_md: str) -> None:
    table = [line for line in _body(report_md).splitlines() if line.startswith("|")]
    assert table == [
        "| 区分 | 内容 | 備考 |",
        "| --- | --- | --- |",
        "| 結合したセル | 結合したセル | 注 |",
        "| 通常 | 値 | なし |",
    ]


# 期待5: 図
def test_tagged_figure(report_md: str) -> None:
    assert "![システム構成図](画像は出力されていません)" in report_md
    assert "> **[図形: 図]**\n> 構成図の中の文字" in report_md


# 期待6: ページをまたぐ段落
def test_paragraph_across_pages(report_md: str) -> None:
    assert "\nこの段落は次のページへ続いています。\n" in report_md
    assert "本章では、PDF を RAG 向けの Markdown に変換する方法を説明します。" in report_md


# 期待7: Artifact
def test_tagged_artifacts_excluded(report_md: str) -> None:
    body = _body(report_md)
    assert "ヘッダー" not in body
    assert not re.search(r"^\d+$", body, flags=re.M)
    front = _front(report_md)
    assert "headers_footers_removed: 4" in front
    assert "multi_column_pages: 0" in front


def _two_column(tmp_path: Path, *extra: str) -> str:
    src = tmp_path / "two.pdf"
    src.write_bytes(two_column_report_pdf())
    out = tmp_path / ("out" + "".join(extra).replace("-", ""))
    result = runner.invoke(app, ["convert", str(src), "-o", str(out), *extra])
    assert result.exit_code == 0, result.output
    return (out / "two.md").read_text(encoding="utf-8")


# 期待8: ヘッダー・フッター除去
def test_untagged_headers_footers_removed(tmp_path: Path) -> None:
    md = _two_column(tmp_path)
    body = _body(md)
    assert "社外秘" not in body
    assert not re.search(r"- \d -", body)
    assert 'pdf_structure: "untagged"' in md
    assert "headers_footers_removed: 6" in _front(md)


# 期待9: --headers-footers
def test_untagged_headers_footers_kept_with_option(tmp_path: Path) -> None:
    md = _two_column(tmp_path, "--headers-footers")
    body = _body(md)
    assert body.count("社外秘 技術報告書") == 3
    assert "headers_footers_removed: 0" in _front(md)


# 期待10: 段組み
def test_untagged_columns(tmp_path: Path) -> None:
    md = _two_column(tmp_path)
    paragraphs = [p for p in _body(md).split("\n\n") if p.strip()]
    title_index = paragraphs.index("段組みの報告書の表題")
    assert paragraphs[title_index + 1] == "".join(LEFT_LINES)
    assert paragraphs[title_index + 2] == "".join(RIGHT_LINES)
    assert "multi_column_pages: 1" in _front(md)


# 期待11: 図
def test_untagged_figure(tmp_path: Path) -> None:
    md = _two_column(tmp_path)
    assert "> **[図形: 図]**\n> 図の一行目\n> 図の二行目" in md
    assert "2ページ目の本文です。\n\n> **[図形: 図]**" in md


# 期待12: 見出し・リスト記号が無い
def test_untagged_has_no_structure_marks(tmp_path: Path) -> None:
    body_lines = _body(_two_column(tmp_path)).splitlines()[1:]  # 1行目は文書タイトル
    assert not [line for line in body_lines if line.startswith("#")]
    assert not [line for line in body_lines if line.startswith("- ")]


# 期待13: 1ページ
def test_single_page_keeps_band_text() -> None:
    body = _body(convert_bytes(single_page_pdf(), "one.pdf").markdown)
    assert "一枚ものの上端" in body
    assert "- 1 -" in body or "\\- 1 -" in body


# 期待14: 冪等性
@pytest.mark.parametrize("factory", [tagged_report_pdf, two_column_report_pdf, scanned_page_pdf])
def test_idempotent(factory) -> None:  # type: ignore[no-untyped-def]
    data = factory()
    first = convert_bytes(data, "a.pdf").markdown
    second = convert_bytes(data, "a.pdf").markdown
    assert _body(first) == _body(second)
    strip = re.compile(r"^converted_at: .*$", flags=re.M)
    assert strip.sub("", first) == strip.sub("", second)


# 期待15: inspect
def test_inspect(tmp_path: Path) -> None:
    (tmp_path / "report.pdf").write_bytes(tagged_report_pdf())
    (tmp_path / "two.pdf").write_bytes(two_column_report_pdf())
    (tmp_path / "locked.pdf").write_bytes(locked_pdf())
    paths = [str(tmp_path / n) for n in ("report.pdf", "two.pdf", "locked.pdf")]
    result = runner.invoke(app, ["inspect", *paths])
    assert result.exit_code == 0
    assert "構造: report.pdf=タグ付き / two.pdf=タグなし" in result.output
    assert "PDF=ページ数" in result.output
    payload = json.loads(runner.invoke(app, ["inspect", *paths, "--json"]).output)
    by_name = {Path(p["path"]).name: p for p in payload}
    assert (
        by_name["report.pdf"]["unit_label"] == "ページ" and by_name["report.pdf"]["unit_count"] == 2
    )
    assert by_name["report.pdf"]["pdf_tagged"] is True
    assert by_name["two.pdf"]["pdf_tagged"] is False and by_name["two.pdf"]["unit_count"] == 3
    assert (
        by_name["locked.pdf"]["status"] == "protected"
        and by_name["locked.pdf"]["password_protected"]
    )


# 期待16: 異常系をバッチで
def test_batch_with_bad_pdfs(tmp_path: Path) -> None:
    src = tmp_path / "in"
    src.mkdir()
    (src / "locked.pdf").write_bytes(locked_pdf())
    (src / "broken.pdf").write_bytes(broken_pdf())
    make_docx(src / "ok.docx", [("p", "正常な文書")])
    out = tmp_path / "out"
    result = runner.invoke(app, ["convert", str(src), "-o", str(out)])
    assert result.exit_code == 1
    # 失敗一覧は種別の表示名を出す (P002 §3.4。F004)
    assert "パスワード保護" in result.output and "破損ファイル" in result.output
    assert (out / "ok.md").exists()
    assert "Traceback" not in result.output


# 期待17: 警告
def test_warnings_in_front_matter() -> None:
    scanned = convert_bytes(scanned_page_pdf(), "s.pdf").markdown
    assert "ページ 2 からテキストを抽出できませんでした" in _front(scanned)
    restricted = convert_bytes(copy_restricted_pdf(), "r.pdf").markdown
    assert "コピーを制限する権限設定" in _front(restricted)
    assert "コピー禁止の本文" in restricted


# 期待18: MuPDF 由来の標準エラー出力が無い
def test_no_library_output_on_stderr(capfd: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    from office2ragknowledge.errors import CorruptedFileError

    with pytest.raises(CorruptedFileError):
        convert_bytes(broken_pdf(), "b.pdf")
    convert_bytes(tagged_report_pdf(), "r.pdf")
    captured = capfd.readouterr()
    assert captured.err == "" and captured.out == ""
