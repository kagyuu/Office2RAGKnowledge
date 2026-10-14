"""U006-T5: PDF の既存の層への統合 (形式判定・変換・構造確認・レンダラ・CLI。※CR-001)。"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from office2ragknowledge import convert_bytes, convert_file, inspect_file
from office2ragknowledge.cli.main import app
from office2ragknowledge.detect import SUPPORTED_EXTENSIONS, detect_format
from office2ragknowledge.errors import CorruptedFileError, PasswordProtectedError
from office2ragknowledge.models import (
    ConvertOptions,
    Document,
    DocumentFormat,
    DocumentMeta,
    Image,
    ImageMode,
    Paragraph,
    make_run,
)
from office2ragknowledge.render import render_document
from office2ragknowledge.render.frontmatter import render_front_matter
from tests.helpers.make_pdf import Elem, Page, Text, build_pdf, encrypt_pdf

runner = CliRunner()
NOW = datetime(2026, 10, 14, tzinfo=UTC)


def _tagged() -> bytes:
    pages = [
        Page(
            items=[
                Text(50, 780, "見出し", 18, mcid=0),
                Text(50, 740, "本文の段落です。", 12, mcid=1),
            ]
        )
    ]
    tree = Elem(
        "Document", [Elem("H1", [(0, 0)]), Elem("P", [(0, 1)]), Elem("Figure", [], alt="図の説明")]
    )
    return build_pdf(pages, tree, title="報告書")


def test_pdf_extension_is_supported() -> None:
    assert SUPPORTED_EXTENSIONS[".pdf"] is DocumentFormat.PDF


def test_detect_pdf_signature() -> None:
    assert detect_format(b"%PDF-1.7\n...") is DocumentFormat.PDF
    assert detect_format(b"\x00" * 100 + b"%PDF-1.4\n") is DocumentFormat.PDF  # 1024 バイト以内
    assert detect_format(b"\x00" * 2000 + b"%PDF-1.4\n") is None


def test_convert_bytes_pdf() -> None:
    result = convert_bytes(_tagged(), "report.pdf")
    assert result.format is DocumentFormat.PDF
    assert len(result.outputs) == 1
    out = result.outputs[0]
    assert out.filename_suffix == ".md" and out.mode is None
    md = result.markdown
    lines = md.splitlines()
    assert lines[3] == 'source_format: "pdf"' and lines[4] == 'pdf_structure: "tagged"'
    assert 'title: "報告書"' in md
    assert "\n# 見出し\n" in md
    assert "![図の説明](画像は出力されていません)" in md
    assert "output_mode" not in md


def test_convert_file_pdf(tmp_path: Path) -> None:
    path = tmp_path / "a.pdf"
    path.write_bytes(build_pdf([Page(items=[Text(50, 780, "abc", 12)])]))
    result = convert_file(path)
    assert 'pdf_structure: "untagged"' in result.markdown
    assert result.outputs[0].meta.source_sha256


def test_pdf_errors() -> None:
    with pytest.raises(PasswordProtectedError):
        convert_bytes(
            encrypt_pdf(build_pdf([Page(items=[Text(50, 780, "x")])]), user="pw"), "a.pdf"
        )
    with pytest.raises(CorruptedFileError):
        convert_bytes(b"%PDF-1.7\nbroken", "a.pdf")


def test_pdf_stats_order_and_values() -> None:
    meta = convert_bytes(_tagged(), "a.pdf").outputs[0].meta
    assert list(meta.stats) == [
        "pages",
        "paragraphs",
        "headings",
        "tables",
        "shapes_with_text",
        "images",
        "headers_footers_removed",
        "multi_column_pages",
    ]
    assert meta.stats["pages"] == 1 and meta.stats["headings"] == 1 and meta.stats["images"] == 1


def test_pdf_image_placeholder_even_with_extract() -> None:
    result = convert_bytes(_tagged(), "a.pdf", ConvertOptions(images=ImageMode.EXTRACT))
    assert "![図の説明](画像は出力されていません)" in result.markdown
    assert result.images == ()


def _meta(**kw: object) -> DocumentMeta:
    base = DocumentMeta(
        source_file="a.pdf",
        source_path="a.pdf",
        source_format=DocumentFormat.PDF,
        source_size_bytes=1,
        source_sha256="x",
        converter="c",
        converted_at=NOW,
    )
    return replace(base, **kw)  # type: ignore[arg-type]


def test_front_matter_pdf_structure_position() -> None:
    text = render_front_matter(_meta(pdf_structure="untagged"), None)
    keys = [line.split(":")[0] for line in text.splitlines() if ":" in line]
    assert keys[:4] == ["source_file", "source_path", "source_format", "pdf_structure"]
    assert "pdf_structure" not in render_front_matter(_meta(), None)


def test_renderer_media_ref_empty_is_placeholder() -> None:
    doc = Document(
        format=DocumentFormat.PDF,
        title="t",
        meta=_meta(stats={"pages": 2}),
        blocks=(Image(alt_text="図", media_ref=""), Paragraph(runs=(make_run("本文"),))),  # type: ignore[arg-type]
    )
    (out,) = render_document(doc, ConvertOptions(images=ImageMode.EXTRACT))
    assert "![図](画像は出力されていません)" in out.markdown
    assert out.meta.stats["pages"] == 2 and out.meta.stats["paragraphs"] == 1


def test_inspect_pdf(tmp_path: Path) -> None:
    tagged = tmp_path / "t.pdf"
    tagged.write_bytes(_tagged())
    info = inspect_file(tagged)
    assert info.status == "ok" and info.format is DocumentFormat.PDF
    assert (info.unit_label, info.unit_count, info.pdf_tagged) == ("ページ", 1, True)
    plain = tmp_path / "p.pdf"
    plain.write_bytes(build_pdf([Page(), Page()]))
    assert inspect_file(plain).pdf_tagged is False
    assert inspect_file(plain).unit_count == 2
    locked = tmp_path / "l.pdf"
    locked.write_bytes(encrypt_pdf(build_pdf([Page()]), user="pw"))
    info = inspect_file(locked)
    assert info.status == "protected" and info.password_protected
    broken = tmp_path / "b.pdf"
    broken.write_bytes(b"%PDF-1.7\nbroken")
    assert inspect_file(broken).status == "corrupted"


def test_non_pdf_inspect_has_no_pdf_tagged(tmp_path: Path) -> None:
    from tests.helpers.make_office import make_docx

    assert inspect_file(make_docx(tmp_path / "a.docx", [("p", "x")])).pdf_tagged is None


def test_cli_inspect_shows_structure(tmp_path: Path) -> None:
    (tmp_path / "t.pdf").write_bytes(_tagged())
    result = runner.invoke(app, ["inspect", str(tmp_path / "t.pdf")])
    assert result.exit_code == 0
    assert "構造: t.pdf=タグ付き" in result.output
    result = runner.invoke(app, ["inspect", str(tmp_path / "t.pdf"), "--json"])
    assert json.loads(result.output)[0]["pdf_tagged"] is True


def test_cli_version_shows_pdf_library() -> None:
    result = runner.invoke(app, ["--version"])
    assert "pdfminer.six" in result.output
    assert "PyMuPDF" not in result.output


def test_cli_help_mentions_pdf() -> None:
    result = runner.invoke(app, ["convert", "--help"])
    assert "PDF" in result.output
