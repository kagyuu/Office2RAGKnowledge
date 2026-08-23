"""U005-T1 の単体テスト: convert_file / convert_bytes。"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from office2ragknowledge import (
    ConvertOptions,
    CorruptedFileError,
    DocumentFormat,
    ExcelModes,
    ExcelOptions,
    PasswordProtectedError,
    UnsupportedFormatError,
    convert_bytes,
    convert_file,
)
from office2ragknowledge.render.frontmatter import strip_front_matter
from tests.helpers.make_malicious import make_broken_zip, make_ole_file
from tests.helpers.make_office import make_docx, make_pptx, make_xlsx


def excel(tmp_path: Path, name: str = "a.xlsx") -> Path:
    return make_xlsx(tmp_path / name, {"S1": [["h1", "h2"], ["v1", "v2"]]})


# ケース1: 3形式が変換できる
def test_three_formats(tmp_path: Path) -> None:
    docx = make_docx(tmp_path / "a.docx", [("p", "本文")])
    assert convert_file(docx).format is DocumentFormat.DOCX
    assert convert_file(excel(tmp_path)).format is DocumentFormat.XLSX
    pptx = make_pptx(tmp_path / "a.pptx", [("表紙", [], None)])
    assert convert_file(pptx).format is DocumentFormat.PPTX


# ケース2: Excel + BOTH で outputs が2件
def test_excel_produces_two_outputs(tmp_path: Path) -> None:
    result = convert_file(excel(tmp_path))
    assert len(result.outputs) == 2
    assert [o.filename_suffix for o in result.outputs] == [".table.md", ".grid.md"]


# ケース3: Word は1件で markdown が使える
def test_word_single_output(tmp_path: Path) -> None:
    result = convert_file(make_docx(tmp_path / "a.docx", [("p", "本文")]))
    assert len(result.outputs) == 1
    assert "本文" in result.markdown


# ケース4: Excel + BOTH で markdown が ValueError (ADR-009)
def test_excel_markdown_property_raises(tmp_path: Path) -> None:
    result = convert_file(excel(tmp_path))
    with pytest.raises(ValueError, match="outputs"):
        _ = result.markdown


# ケース5: 非対応形式
def test_unsupported_format(tmp_path: Path) -> None:
    path = tmp_path / "a.txt"
    path.write_text("ただのテキスト", encoding="utf-8")
    with pytest.raises(UnsupportedFormatError) as exc:
        convert_file(path)
    assert exc.value.code == "E-002"


def test_legacy_format_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "old.doc"
    path.write_bytes(b"not a zip")
    with pytest.raises(UnsupportedFormatError) as exc:
        convert_file(path)
    assert ".doc" in exc.value.message


# ケース6: パスワード保護
def test_password_protected(tmp_path: Path) -> None:
    path = make_ole_file(tmp_path / "locked.xlsx")
    with pytest.raises(PasswordProtectedError) as exc:
        convert_file(path)
    assert exc.value.code == "E-005"


# ケース7: 壊れた ZIP
def test_corrupted_file(tmp_path: Path) -> None:
    path = make_broken_zip(tmp_path / "broken.xlsx")
    with pytest.raises((CorruptedFileError, UnsupportedFormatError)):
        convert_file(path)


# ケース8: convert_file はファイルを書き出さない
def test_convert_file_has_no_side_effects(tmp_path: Path) -> None:
    path = excel(tmp_path)
    before = set(tmp_path.iterdir())
    convert_file(path)
    assert set(tmp_path.iterdir()) == before


# ケース9: convert_bytes が同じ結果を返す
def test_convert_bytes_matches_convert_file(tmp_path: Path) -> None:
    path = excel(tmp_path)
    from_file = convert_file(path)
    from_bytes = convert_bytes(path.read_bytes(), "a.xlsx")
    assert [strip_front_matter(o.markdown) for o in from_file.outputs] == [
        strip_front_matter(o.markdown) for o in from_bytes.outputs
    ]


# ケース10: source_sha256 が実際のハッシュ
def test_sha256(tmp_path: Path) -> None:
    path = excel(tmp_path)
    result = convert_file(path)
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    assert result.outputs[0].meta.source_sha256 == expected


# ケース11: 拡張子偽装で警告
def test_extension_mismatch_warns(tmp_path: Path) -> None:
    docx = make_docx(tmp_path / "real.docx", [("p", "本文")])
    spoofed = tmp_path / "spoofed.xlsx"
    spoofed.write_bytes(docx.read_bytes())
    result = convert_file(spoofed)
    assert any("拡張子" in w for w in result.warnings)


# ケース12: 冪等性 — 2回変換して converted_at 以外が一致
def test_idempotent(tmp_path: Path) -> None:
    path = excel(tmp_path)
    first = convert_file(path)
    second = convert_file(path)
    for a, b in zip(first.outputs, second.outputs, strict=True):
        assert strip_front_matter(a.markdown) == strip_front_matter(b.markdown)


def test_title_is_basename_not_full_path(tmp_path: Path) -> None:
    """タイトルにフルパスが入らないこと (Windows のパス区切り)。"""
    path = make_xlsx(tmp_path / "体制図.xlsx", {"S1": [["a"]]})
    result = convert_file(path)
    title = result.outputs[0].meta.title
    assert title == "体制図"
    assert "\\" not in (title or "")
    assert "/" not in (title or "")


def test_source_file_is_basename(tmp_path: Path) -> None:
    result = convert_file(excel(tmp_path, "名簿.xlsx"))
    assert result.outputs[0].meta.source_file == "名簿.xlsx"


def test_excel_modes_table_only(tmp_path: Path) -> None:
    options = ConvertOptions(excel=ExcelOptions(modes=ExcelModes.TABLE))
    result = convert_file(excel(tmp_path), options)
    assert len(result.outputs) == 1
    assert result.outputs[0].filename_suffix == ".table.md"
