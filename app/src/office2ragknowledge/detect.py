"""形式判定 (API-05 / REQ-F-001)。

拡張子だけに頼らず、ZIP 内の ``[Content_Types].xml`` から実形式を判定する。
拡張子と実形式が食い違う場合は **実形式を優先** し、呼び出し元が警告を残す。

PDF (※CR-001) は ZIP ではないため、先頭 1024 バイト以内の ``%PDF-`` で判定する
(P003 §4.3)。
"""

from __future__ import annotations

from pathlib import Path

from .errors import CorruptedFileError, FileTooLargeError
from .models import DocumentFormat
from .ooxml.xml_utils import NS
from .ooxml.zip_reader import SafeZipReader

__all__ = [
    "LEGACY_EXTENSIONS",
    "SUPPORTED_EXTENSIONS",
    "detect_format",
    "format_from_extension",
    "is_encrypted_ole",
]

#: 旧バイナリ形式。非対応であることを明示的に案内するために保持する (E-002)。
LEGACY_EXTENSIONS = frozenset({".doc", ".xls", ".ppt"})

#: 対応する拡張子。マクロ有効形式も本文のみ読み取る (REQ-NF-009)。
SUPPORTED_EXTENSIONS: dict[str, DocumentFormat] = {
    ".docx": DocumentFormat.DOCX,
    ".docm": DocumentFormat.DOCX,
    ".xlsx": DocumentFormat.XLSX,
    ".xlsm": DocumentFormat.XLSX,
    ".pptx": DocumentFormat.PPTX,
    ".pptm": DocumentFormat.PPTX,
    ".pdf": DocumentFormat.PDF,
}

_ZIP_MAGIC = b"PK\x03\x04"
_PDF_MAGIC = b"%PDF-"
#: PDF ヘッダを探す範囲。仕様は先頭以外の位置のヘッダも許容する (P003 §4.3)。
_PDF_HEADER_WINDOW = 1024
_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

#: ContentType の部分一致で形式を決める。マクロ有効形式も同じ語を含む。
_CONTENT_TYPE_MARKERS: tuple[tuple[str, DocumentFormat], ...] = (
    ("wordprocessingml.document", DocumentFormat.DOCX),
    ("spreadsheetml.sheet", DocumentFormat.XLSX),
    ("presentationml.presentation", DocumentFormat.PPTX),
)


def format_from_extension(name: str) -> DocumentFormat | None:
    """拡張子から形式を推定する。対応外なら ``None``。"""
    return SUPPORTED_EXTENSIONS.get(Path(name).suffix.lower())


def _head_bytes(source: Path | str | bytes, size: int) -> bytes:
    if isinstance(source, bytes):
        return source[:size]
    path = Path(source)
    with path.open("rb") as fp:
        return fp.read(size)


def is_encrypted_ole(source: Path | str | bytes) -> bool:
    """OLE 複合ファイル (暗号化された OOXML) のシグネチャを持つか。

    パスワード保護された OOXML は ZIP ではなく OLE 複合ファイルになる。
    """
    return _head_bytes(source, len(_OLE_MAGIC)) == _OLE_MAGIC


def detect_format(source: Path | str | bytes) -> DocumentFormat | None:
    """拡張子と ZIP 内容から形式を判定する。

    対応形式でない場合は例外ではなく ``None`` を返す。パスワード保護の判定は
    呼び出し元が ``is_encrypted_ole`` で行う (P003 §4.3)。
    """
    head = _head_bytes(source, _PDF_HEADER_WINDOW)
    if _PDF_MAGIC in head:
        return DocumentFormat.PDF
    if head[: len(_ZIP_MAGIC)] != _ZIP_MAGIC:
        return None
    try:
        with SafeZipReader(source) as reader:
            if not reader.has("[Content_Types].xml"):
                return None
            root = reader.read_xml("[Content_Types].xml")
            for override in root.iter(f"{{{NS['ct']}}}Override"):
                content_type = override.get("ContentType", "")
                for marker, fmt in _CONTENT_TYPE_MARKERS:
                    if marker in content_type:
                        return fmt
    except (CorruptedFileError, FileTooLargeError):
        raise
    except OSError:
        raise
    return None
