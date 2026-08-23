"""U001-T4 の単体テスト: 安全な ZIP 読み取り。

パストラバーサル (REQ-NF-008) と ZIP爆弾 (REQ-NF-006) の防御を検証する。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from office2ragknowledge.errors import CorruptedFileError, FileTooLargeError
from office2ragknowledge.ooxml.zip_reader import SafeZipReader
from tests.helpers.make_malicious import (
    make_absolute_path_zip,
    make_broken_zip,
    make_path_traversal_zip,
    make_too_many_entries_zip,
    make_zip_bomb,
)
from tests.helpers.make_office import zip_from_mapping


# ケース1: 正常な ZIP からエントリを読める
def test_read_normal_zip(tmp_path: Path) -> None:
    path = zip_from_mapping(tmp_path / "a.zip", {"a.txt": "hello", "b/c.xml": "<x/>"})
    with SafeZipReader(path) as reader:
        assert reader.read("a.txt") == b"hello"
        assert reader.has("b/c.xml")
        assert set(reader.names()) == {"a.txt", "b/c.xml"}


# ケース2: ../ を含む ZIP が CorruptedFileError (REQ-NF-008)
def test_path_traversal_is_rejected(tmp_path: Path) -> None:
    path = make_path_traversal_zip(tmp_path / "evil.zip")
    with pytest.raises(CorruptedFileError):
        SafeZipReader(path)


# ケース3: 絶対パスのエントリが CorruptedFileError
def test_absolute_path_is_rejected(tmp_path: Path) -> None:
    path = make_absolute_path_zip(tmp_path / "abs.zip")
    with pytest.raises(CorruptedFileError):
        SafeZipReader(path)


# ケース4: 圧縮率が上限を超えると FileTooLargeError (REQ-NF-006)
def test_zip_bomb_is_rejected(tmp_path: Path) -> None:
    path = make_zip_bomb(tmp_path / "bomb.zip")
    with pytest.raises(FileTooLargeError):
        SafeZipReader(path)


# ケース5: エントリ数が上限を超えると FileTooLargeError
def test_too_many_entries_is_rejected(tmp_path: Path) -> None:
    path = make_too_many_entries_zip(tmp_path / "many.zip")
    with pytest.raises(FileTooLargeError):
        SafeZipReader(path)


# ケース6: ZIP でないバイト列が CorruptedFileError
def test_non_zip_raises_corrupted(tmp_path: Path) -> None:
    path = make_broken_zip(tmp_path / "broken.zip")
    with pytest.raises(CorruptedFileError):
        SafeZipReader(path)


# ケース7: 存在しないエントリの read が CorruptedFileError (KeyError が漏れない)
def test_missing_entry_raises_corrupted(tmp_path: Path) -> None:
    path = zip_from_mapping(tmp_path / "a.zip", {"a.txt": "x"})
    with SafeZipReader(path) as reader, pytest.raises(CorruptedFileError):
        reader.read("missing.xml")


# ケース8: resolve_rels が相対 Target を正規化する
def test_resolve_rels_normalizes(tmp_path: Path) -> None:
    rels = (
        '<?xml version="1.0"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://x/drawing" Target="../drawings/drawing1.xml"/>'
        "</Relationships>"
    )
    path = zip_from_mapping(
        tmp_path / "a.zip",
        {
            "xl/worksheets/sheet1.xml": "<worksheet/>",
            "xl/worksheets/_rels/sheet1.xml.rels": rels,
            "xl/drawings/drawing1.xml": "<wsDr/>",
        },
    )
    with SafeZipReader(path) as reader:
        mapping = reader.resolve_rels("xl/worksheets/sheet1.xml")
    assert mapping == {"rId1": "xl/drawings/drawing1.xml"}


# ケース9: Target がルート外に出る場合 CorruptedFileError
def test_resolve_rels_rejects_escape(tmp_path: Path) -> None:
    rels = (
        '<?xml version="1.0"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://x/drawing" Target="../../../etc/passwd"/>'
        "</Relationships>"
    )
    path = zip_from_mapping(
        tmp_path / "a.zip",
        {
            "xl/worksheets/sheet1.xml": "<worksheet/>",
            "xl/worksheets/_rels/sheet1.xml.rels": rels,
        },
    )
    with SafeZipReader(path) as reader, pytest.raises(CorruptedFileError):
        reader.resolve_rels("xl/worksheets/sheet1.xml")


# ケース10: with で使え、抜けた後に閉じている
def test_context_manager_closes(tmp_path: Path) -> None:
    path = zip_from_mapping(tmp_path / "a.zip", {"a.txt": "x"})
    with SafeZipReader(path) as reader:
        assert reader.read("a.txt") == b"x"
    with pytest.raises(ValueError):
        reader.read("a.txt")


def test_bytes_source(tmp_path: Path) -> None:
    """バイト列からも開ける (convert_bytes 用)。"""
    path = zip_from_mapping(tmp_path / "a.zip", {"a.txt": "hello"})
    data = path.read_bytes()
    with SafeZipReader(data) as reader:
        assert reader.read("a.txt") == b"hello"


def test_external_rel_is_skipped(tmp_path: Path) -> None:
    """外部参照は解決しない (REQ-NF-010)。"""
    rels = (
        '<?xml version="1.0"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://x/hyperlink" Target="http://example.com"'
        ' TargetMode="External"/>'
        "</Relationships>"
    )
    path = zip_from_mapping(
        tmp_path / "a.zip",
        {"word/document.xml": "<doc/>", "word/_rels/document.xml.rels": rels},
    )
    with SafeZipReader(path) as reader:
        assert reader.resolve_rels("word/document.xml") == {}
