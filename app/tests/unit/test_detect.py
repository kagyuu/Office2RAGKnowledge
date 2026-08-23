"""U001-T5 の単体テスト: 形式判定 (API-05)。"""

from __future__ import annotations

from pathlib import Path

from office2ragknowledge.detect import (
    LEGACY_EXTENSIONS,
    detect_format,
    format_from_extension,
    is_encrypted_ole,
)
from office2ragknowledge.models import DocumentFormat
from tests.helpers.make_malicious import make_ole_file
from tests.helpers.make_office import make_docx, make_pptx, make_xlsx


# ケース1: 3形式が正しく判定される
def test_detect_three_formats(tmp_path: Path) -> None:
    docx = make_docx(tmp_path / "a.docx", [("p", "本文")])
    xlsx = make_xlsx(tmp_path / "a.xlsx", {"S1": [["a"]]})
    pptx = make_pptx(tmp_path / "a.pptx", [("タイトル", ["本文"], None)])
    assert detect_format(docx) is DocumentFormat.DOCX
    assert detect_format(xlsx) is DocumentFormat.XLSX
    assert detect_format(pptx) is DocumentFormat.PPTX


# ケース2: ZIP でないバイト列が None
def test_non_zip_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "a.txt"
    path.write_text("ただのテキスト", encoding="utf-8")
    assert detect_format(path) is None


# ケース3: 拡張子を偽装しても実形式が優先される (REQ-F-001)
def test_extension_spoofing_uses_real_format(tmp_path: Path) -> None:
    docx = make_docx(tmp_path / "real.docx", [("p", "本文")])
    spoofed = tmp_path / "spoofed.xlsx"
    spoofed.write_bytes(docx.read_bytes())
    assert detect_format(spoofed) is DocumentFormat.DOCX
    assert format_from_extension("spoofed.xlsx") is DocumentFormat.XLSX


# ケース4: マクロ有効形式の拡張子
def test_macro_enabled_extensions() -> None:
    assert format_from_extension("a.docm") is DocumentFormat.DOCX
    assert format_from_extension("a.xlsm") is DocumentFormat.XLSX
    assert format_from_extension("a.pptm") is DocumentFormat.PPTX


# ケース5: 旧形式は None かつ LEGACY_EXTENSIONS に含まれる
def test_legacy_extensions() -> None:
    assert format_from_extension("a.doc") is None
    assert ".doc" in LEGACY_EXTENSIONS
    assert ".xls" in LEGACY_EXTENSIONS
    assert ".ppt" in LEGACY_EXTENSIONS


# ケース6: OLE シグネチャの検出
def test_is_encrypted_ole(tmp_path: Path) -> None:
    ole = make_ole_file(tmp_path / "locked.xlsx")
    assert is_encrypted_ole(ole) is True
    normal = make_xlsx(tmp_path / "a.xlsx", {"S1": [["a"]]})
    assert is_encrypted_ole(normal) is False


# ケース7: 空のバイト列で例外にならず None
def test_empty_file_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "empty.xlsx"
    path.write_bytes(b"")
    assert detect_format(path) is None
    assert is_encrypted_ole(path) is False


def test_detect_from_bytes(tmp_path: Path) -> None:
    """バイト列からも判定できる (convert_bytes 用)。"""
    xlsx = make_xlsx(tmp_path / "a.xlsx", {"S1": [["a"]]})
    assert detect_format(xlsx.read_bytes()) is DocumentFormat.XLSX
