"""A002 受け入れテスト: 利用シナリオ。

P001 §1.2 が定めた3種類の利用者が、それぞれの利用シーンで問題なく使えることを
検証する。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from office2ragknowledge import (
    BatchOptions,
    ConvertOptions,
    ExcelModes,
    ExcelOptions,
    convert_batch,
    convert_bytes,
    convert_file,
    inspect_file,
)
from office2ragknowledge.cli.main import app
from office2ragknowledge.render.frontmatter import strip_front_matter
from tests.helpers.make_malicious import make_ole_file
from tests.helpers.make_office import make_docx, make_pptx, make_xlsx

runner = CliRunner()


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    """3形式が混在する階層構造 (非対応形式を含む)。"""
    root = tmp_path / "docs" / "2026"
    root.mkdir(parents=True)
    (root / "sub").mkdir()
    for i in range(3):
        make_docx(root / f"規程{i}.docx", [("h1", f"第{i}章"), ("p", "本文")])
    for i in range(3):
        make_xlsx(root / f"売上{i}.xlsx", {"S1": [["月", "額"], [4, 100]]})
    make_pptx(root / "sub" / "会議.pptx", [("表紙", ["要点"], "ノート")])
    (root / "旧.doc").write_bytes(b"legacy")
    (root / "メモ.txt").write_text("対象外", encoding="utf-8")
    return root


# ============================================================
# シナリオ1: RAGパイプライン構築者 — バッチ変換
# ============================================================


def test_recursive_batch(corpus: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = runner.invoke(app, ["convert", str(corpus), "-r", "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert (out / "会議.md").is_file(), "サブディレクトリが変換されていません"


def test_unsupported_does_not_stop_batch(corpus: Path, tmp_path: Path) -> None:
    result = convert_batch([corpus], BatchOptions(output_dir=tmp_path / "out", recursive=True))
    assert len(result.succeeded) == 7
    assert len(result.failures) == 0
    assert len(result.skipped) >= 2  # .doc と .txt


def test_output_count_is_visible(corpus: Path, tmp_path: Path) -> None:
    result = convert_batch([corpus], BatchOptions(output_dir=tmp_path / "out", recursive=True))
    # Excel 3件 → 6ファイル、Word 3件 → 3ファイル、PPT 1件 → 1ファイル
    assert len(result.written_files) == 10
    assert len(result.succeeded) == 7


def test_front_matter_identifies_source(corpus: Path) -> None:
    result = convert_file(corpus / "売上0.xlsx")
    for output in result.outputs:
        assert output.meta.source_file == "売上0.xlsx"
        assert len(output.meta.source_sha256) == 64


def test_parallel_matches_sequential(corpus: Path, tmp_path: Path) -> None:
    one = convert_batch([corpus], BatchOptions(output_dir=tmp_path / "o1", recursive=True, jobs=1))
    four = convert_batch([corpus], BatchOptions(output_dir=tmp_path / "o2", recursive=True, jobs=4))
    assert [p.name for p in one.succeeded] == [p.name for p in four.succeeded]
    for a, b in zip(
        sorted((tmp_path / "o1").iterdir()), sorted((tmp_path / "o2").iterdir()), strict=True
    ):
        assert strip_front_matter(a.read_text(encoding="utf-8")) == strip_front_matter(
            b.read_text(encoding="utf-8")
        )


# ============================================================
# シナリオ2: ナレッジ整備担当者 — 単発変換と目視確認
# ============================================================


def test_inspect_before_convert(corpus: Path) -> None:
    info = inspect_file(corpus / "sub" / "会議.pptx")
    assert info.status == "ok"
    assert info.unit_label == "スライド"
    assert info.unit_count >= 1
    assert info.estimated_chars > 0


def test_single_file_convert(corpus: Path, tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["convert", str(corpus / "規程0.docx"), "-o", str(tmp_path / "out")]
    )
    assert result.exit_code == 0
    assert (tmp_path / "out" / "規程0.md").is_file()


def test_output_is_human_readable(corpus: Path) -> None:
    body = strip_front_matter(convert_file(corpus / "規程0.docx").markdown)
    assert body.startswith("# 規程0")
    assert "## 第0章" in body


def test_warnings_are_surfaced(tmp_path: Path) -> None:
    path = make_xlsx(tmp_path / "f.xlsx", {"集計": [["v"], ["=A1*2"]]})
    result = runner.invoke(app, ["convert", str(path), "-o", str(tmp_path / "out")])
    assert "警告" in result.output
    assert "計算結果を持たない" in result.output


# ============================================================
# シナリオ3: パイプ処理
# ============================================================


def test_stdout_is_pipeable(corpus: Path) -> None:
    result = runner.invoke(app, ["convert", str(corpus / "規程0.docx"), "--stdout"])
    assert result.exit_code == 0
    assert result.output.startswith("---")
    assert "変換結果:" not in result.output
    assert "警告" not in result.output


def test_stdout_excel_guides_the_user(corpus: Path) -> None:
    result = runner.invoke(app, ["convert", str(corpus / "売上0.xlsx"), "--stdout"])
    assert result.exit_code == 2
    assert "--excel-modes" in result.output
    assert "table" in result.output and "grid" in result.output


def test_stdout_excel_with_mode(corpus: Path) -> None:
    result = runner.invoke(
        app, ["convert", str(corpus / "売上0.xlsx"), "--stdout", "--excel-modes", "table"]
    )
    assert result.exit_code == 0
    assert 'output_mode: "table"' in result.output


# ============================================================
# シナリオ4: 開発者 — ライブラリとしての利用
# ============================================================


def test_library_import_and_use(corpus: Path) -> None:
    result = convert_file(corpus / "規程0.docx", ConvertOptions())
    assert result.markdown


def test_convert_file_writes_nothing(corpus: Path, tmp_path: Path) -> None:
    before = set(corpus.iterdir())
    convert_file(corpus / "規程0.docx")
    assert set(corpus.iterdir()) == before


def test_excel_markdown_property_prevents_silent_loss(corpus: Path) -> None:
    """取りこぼしを黙って起こさない契約 (ADR-009)。"""
    result = convert_file(corpus / "売上0.xlsx")
    assert len(result.outputs) == 2
    with pytest.raises(ValueError):
        _ = result.markdown


def test_convert_bytes_for_web_apps(corpus: Path) -> None:
    data = (corpus / "売上0.xlsx").read_bytes()
    result = convert_bytes(
        data, "uploaded.xlsx", ConvertOptions(excel=ExcelOptions(modes=ExcelModes.GRID))
    )
    assert len(result.outputs) == 1
    assert result.outputs[0].meta.source_file == "uploaded.xlsx"


def test_library_does_not_log_by_default(corpus: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """import しただけでは標準エラーにログを出さない (NullHandler)。"""
    capsys.readouterr()
    convert_file(corpus / "規程0.docx")
    captured = capsys.readouterr()
    assert captured.err == ""


# ============================================================
# シナリオ5: 運用者 — エラーからの復旧
# ============================================================


def test_password_protected_guidance(tmp_path: Path) -> None:
    src = tmp_path / "in"
    src.mkdir()
    make_docx(src / "ok.docx", [("p", "本文")])
    make_ole_file(src / "locked.xlsx")
    result = runner.invoke(app, ["convert", str(src), "-o", str(tmp_path / "out")])
    assert result.exit_code == 1
    assert "パスワード" in result.output


def test_legacy_format_guidance(corpus: Path) -> None:
    result = runner.invoke(app, ["convert", str(corpus / "旧.doc")])
    assert ".doc" in result.output
    assert "docx" in result.output


def test_error_messages_are_japanese_without_traceback(tmp_path: Path) -> None:
    result = runner.invoke(app, ["convert", str(tmp_path / "存在しない")])
    assert "エラー" in result.output
    assert "Traceback" not in result.output
