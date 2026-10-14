"""A006 受け入れテスト: PDF 入力 (P001 §1.3 課題8・課題9。※CR-001・CR-002)。

CR-001・CR-002 の「期待する振る舞い」を、利用者から見える結果 (出力ファイル・
終了コード・サマリ) で確認する。番号は docs/P009-acceptance-direction/A006 の表に対応する。
"""

from __future__ import annotations

import json
import re
import socket
from pathlib import Path

import pytest
from typer.testing import CliRunner

from office2ragknowledge import DocumentFormat, convert_bytes
from office2ragknowledge.cli.main import app
from office2ragknowledge.render.frontmatter import strip_front_matter
from tests.helpers.make_office import make_docx, make_xlsx
from tests.helpers.pdf_samples import (
    LEFT_LINES,
    RIGHT_LINES,
    broken_pdf,
    locked_pdf,
    reading_order_pdf,
    scanned_page_pdf,
    single_column_pdf,
    single_page_pdf,
    tagged_report_pdf,
    two_column_report_pdf,
)

runner = CliRunner()


def _front(md: str) -> str:
    return md.split("\n---\n", 1)[0]


@pytest.fixture
def mixed_folder(tmp_path: Path) -> Path:
    docs = tmp_path / "docs"
    (docs / "sub").mkdir(parents=True)
    make_docx(docs / "word.docx", [("p", "Word の本文")])
    make_xlsx(docs / "book.xlsx", {"S1": [["a", "b"], ["1", "2"]]})
    (docs / "report.pdf").write_bytes(tagged_report_pdf())
    (docs / "two.pdf").write_bytes(two_column_report_pdf())
    (docs / "sub" / "one.pdf").write_bytes(single_page_pdf())
    return docs


@pytest.fixture
def converted(mixed_folder: Path, tmp_path: Path) -> Path:
    out = tmp_path / "out"
    result = runner.invoke(app, ["convert", str(mixed_folder), "-r", "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert "成功 5 件" in result.output
    assert "出力ファイル: 6 件" in result.output
    return out


# 1: 混在フォルダのバッチ変換
def test_1_mixed_batch(converted: Path) -> None:
    # -o 指定時はサブディレクトリのファイルも出力先の直下に書き出される (REQ-F-004。F005)
    names = sorted(p.name for p in converted.iterdir() if p.suffix == ".md")
    assert names == ["book.grid.md", "book.table.md", "one.md", "report.md", "two.md", "word.md"]


# 2: 単発・パイプ
def test_2_stdout(tmp_path: Path) -> None:
    src = tmp_path / "report.pdf"
    src.write_bytes(tagged_report_pdf())
    result = runner.invoke(app, ["convert", str(src), "--stdout", "--quiet"])
    assert result.exit_code == 0
    assert result.stdout.startswith("---\n")
    assert 'source_format: "pdf"' in result.stdout


# 3: ライブラリ利用
def test_3_library() -> None:
    result = convert_bytes(tagged_report_pdf(), "report.pdf")
    assert result.format is DocumentFormat.PDF
    assert len(result.outputs) == 1
    assert result.markdown.startswith("---\n")


# 4: タグ付きの章立て
def test_4_tagged_structure(converted: Path) -> None:
    md = (converted / "report.md").read_text(encoding="utf-8")
    headings = [line for line in strip_front_matter(md).splitlines() if line.startswith("#")]
    assert headings[1:] == ["# 第1章 概要", "## 1.1 背景", "### 1.1.1 詳細"]
    assert "- 項目A\n  - 子項目A-1\n    - 孫項目A-1-a" in md
    assert "| 区分 | 内容 | 備考 |" in md


# 5: タグなしは羅列
def test_5_untagged_plain(converted: Path) -> None:
    body = strip_front_matter((converted / "two.md").read_text(encoding="utf-8"))
    lines = body.splitlines()[1:]
    assert not [line for line in lines if line.startswith(("#", "- ", "* ", "1. "))]


# 6: 図表内テキストと代替テキスト
def test_6_figures(converted: Path) -> None:
    report = (converted / "report.md").read_text(encoding="utf-8")
    assert "![システム構成図](画像は出力されていません)" in report
    assert "> **[図形: 図]**\n> 構成図の中の文字" in report
    two = (converted / "two.md").read_text(encoding="utf-8")
    assert "> **[図形: 図]**\n> 図の一行目\n> 図の二行目" in two


# 7: スキャンページ (OCR しない)
def test_7_scanned_page() -> None:
    md = convert_bytes(scanned_page_pdf(), "scan.pdf").markdown
    assert "ページ 2 からテキストを抽出できませんでした" in _front(md)
    assert "OCR は行いません" in _front(md)


# 8: 論理構造の判別
def test_8_structure_flag(converted: Path) -> None:
    assert 'pdf_structure: "tagged"' in (converted / "report.md").read_text(encoding="utf-8")
    assert 'pdf_structure: "untagged"' in (converted / "two.md").read_text(encoding="utf-8")


# 9: 暗号化・破損
def test_9_errors(tmp_path: Path) -> None:
    src = tmp_path / "in"
    src.mkdir()
    (src / "a_locked.pdf").write_bytes(locked_pdf())
    (src / "b_broken.pdf").write_bytes(broken_pdf())
    make_docx(src / "c_ok.docx", [("p", "後続の正常ファイル")])
    result = runner.invoke(app, ["convert", str(src), "-o", str(tmp_path / "out")])
    assert result.exit_code == 1
    assert "パスワード保護" in result.output and "破損ファイル" in result.output
    assert "Traceback" not in result.output
    assert (tmp_path / "out" / "c_ok.md").exists()


# 10: inspect
def test_10_inspect(tmp_path: Path) -> None:
    (tmp_path / "report.pdf").write_bytes(tagged_report_pdf())
    (tmp_path / "scan.pdf").write_bytes(scanned_page_pdf())
    paths = [str(tmp_path / "report.pdf"), str(tmp_path / "scan.pdf")]
    result = runner.invoke(app, ["inspect", *paths, "--json"])
    payload = {Path(p["path"]).name: p for p in json.loads(result.output)}
    assert payload["report.pdf"]["unit_label"] == "ページ"
    assert payload["report.pdf"]["unit_count"] == 2
    assert payload["report.pdf"]["pdf_tagged"] is True
    assert payload["scan.pdf"]["pdf_tagged"] is False


# 11: 冪等性
@pytest.mark.parametrize("factory", [tagged_report_pdf, two_column_report_pdf])
def test_11_idempotent(factory) -> None:  # type: ignore[no-untyped-def]
    data = factory()
    a = convert_bytes(data, "x.pdf").markdown
    b = convert_bytes(data, "x.pdf").markdown
    assert strip_front_matter(a) == strip_front_matter(b)


# 12: オフライン
def test_12_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    def deny(*args: object, **kwargs: object) -> None:
        raise AssertionError("ネットワーク通信を試みた")

    monkeypatch.setattr(socket, "socket", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    assert "第1章 概要" in convert_bytes(tagged_report_pdf(), "r.pdf").markdown
    assert "multi_column_pages: 1" in convert_bytes(two_column_report_pdf(), "t.pdf").markdown


# 13: ヘッダー・フッター
def test_13_headers_footers(converted: Path) -> None:
    md = (converted / "two.md").read_text(encoding="utf-8")
    body = strip_front_matter(md)
    assert "社外秘" not in body and not re.search(r"- \d -", body)
    assert "headers_footers_removed: 6" in _front(md)


# 14: 表紙・1ページ
def test_14_cover_and_single_page(converted: Path) -> None:
    one = strip_front_matter((converted / "one.md").read_text(encoding="utf-8"))
    assert "一枚ものの上端" in one
    two = strip_front_matter((converted / "two.md").read_text(encoding="utf-8"))
    assert "段組みの報告書の表題" in two  # 1ページ目の上端付近にだけある表題


# 15: 除去の無効化
def test_15_headers_footers_option(tmp_path: Path) -> None:
    src = tmp_path / "two.pdf"
    src.write_bytes(two_column_report_pdf())
    out = tmp_path / "o"
    result = runner.invoke(app, ["convert", str(src), "-o", str(out), "--headers-footers"])
    assert result.exit_code == 0
    body = strip_front_matter((tmp_path / "o" / "two.md").read_text(encoding="utf-8"))
    assert body.count("社外秘 技術報告書") == 3


# 16: タグ付きの Artifact
def test_16_tagged_artifacts(converted: Path) -> None:
    body = strip_front_matter((converted / "report.md").read_text(encoding="utf-8"))
    assert "ヘッダー" not in body


# 17: 段組み
def test_17_columns(converted: Path) -> None:
    md = (converted / "two.md").read_text(encoding="utf-8")
    paragraphs = [p for p in strip_front_matter(md).split("\n\n") if p.strip()]
    i = paragraphs.index("段組みの報告書の表題")
    assert paragraphs[i + 1 : i + 3] == ["".join(LEFT_LINES), "".join(RIGHT_LINES)]
    assert "multi_column_pages: 1" in _front(md)


# 18: 1段組み
def test_18_single_column() -> None:
    md = convert_bytes(single_column_pdf(), "s.pdf").markdown
    body = strip_front_matter(md)
    lines = [f"1段組みの{i}行目の文章で、幅いっぱいに書かれています。" for i in range(5)]
    assert "".join(lines) in body
    assert "multi_column_pages: 0" in _front(md)


# 19: タグ付きの読み順は構造ツリーの順
def test_19_tagged_reading_order() -> None:
    body = strip_front_matter(convert_bytes(reading_order_pdf(), "o.pdf").markdown)
    assert body.index("ページ上では下にある段落") < body.index("ページ上では上にある段落")
