"""単一ファイルの変換 (API-01 / API-02)。

**副作用を持たない。** ファイルを書き出さないため、結果をそのまま利用者が扱える
(REQ-F-102)。書き出しは ``write_result`` (API-06) の責務。

Excel は既定で2件の出力を返す (要求③)。解析は1回のみ行い、2つのレンダラが
同じ中間表現を消費する (REQ-F-068)。
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from . import __version__
from .detect import LEGACY_EXTENSIONS, detect_format, format_from_extension, is_encrypted_ole
from .errors import PasswordProtectedError, UnsupportedFormatError
from .models import ConversionResult, ConvertOptions, DocumentFormat
from .ooxml.zip_reader import SafeZipReader
from .parsers.base import Parser
from .parsers.excel import ExcelParser
from .parsers.powerpoint import PowerPointParser
from .parsers.word import WordParser
from .render import render_document

__all__ = ["convert_bytes", "convert_file"]

_PARSERS: dict[DocumentFormat, type[Parser]] = {
    DocumentFormat.DOCX: WordParser,
    DocumentFormat.XLSX: ExcelParser,
    DocumentFormat.PPTX: PowerPointParser,
}


def convert_file(path: Path | str, options: ConvertOptions | None = None) -> ConversionResult:
    """単一ファイルを変換して結果オブジェクトを返す。

    Raises:
        UnsupportedFormatError: 対応していない形式 (E-002)
        PasswordProtectedError: パスワードで保護されている (E-005)
        CorruptedFileError: ZIP/XML として読めない (E-007)
        FileTooLargeError: ZIP爆弾検査に抵触 (E-008)
        FileNotFoundError / PermissionError: 入力を読めない
    """
    source = Path(path)
    data = source.read_bytes()
    return _convert(data, str(source), source, options or ConvertOptions())


def convert_bytes(
    data: bytes, filename: str, options: ConvertOptions | None = None
) -> ConversionResult:
    """メモリ上の文書を変換する (REQ-F-101)。

    ``filename`` は形式判定の補助と front matter に用いる。パスとして解決しない。
    """
    return _convert(data, filename, Path(filename), options or ConvertOptions())


def _convert(
    data: bytes, source_path: str, path_obj: Path, options: ConvertOptions
) -> ConversionResult:
    if is_encrypted_ole(data):
        raise PasswordProtectedError(
            "パスワードで保護されたファイルは変換できません", path=path_obj
        )

    fmt = detect_format(data)
    if fmt is None:
        suffix = path_obj.suffix.lower()
        if suffix in LEGACY_EXTENSIONS:
            raise UnsupportedFormatError(f"{suffix} は非対応の形式です", path=path_obj)
        raise UnsupportedFormatError(
            f"{suffix or 'このファイル'} は非対応の形式です", path=path_obj
        )

    warnings: list[str] = []
    from_ext = format_from_extension(path_obj.name)
    if from_ext is not None and from_ext is not fmt:
        warnings.append(
            f"拡張子は {path_obj.suffix} ですが、実際の形式は {fmt} です。実形式として変換しました"
        )

    # 現在時刻の取得はここ1箇所のみ。パーサ・レンダラは引数で受け取る (REQ-NF-018)
    converted_at = datetime.now().astimezone()
    sha256 = hashlib.sha256(data).hexdigest()

    with SafeZipReader(data) as reader:
        parser = _PARSERS[fmt]()
        document = parser.parse(reader, source_path, options, converted_at)

    from dataclasses import replace

    meta = replace(
        document.meta,
        source_file=path_obj.name,
        source_size_bytes=len(data),
        source_sha256=sha256,
        converter=f"office2ragknowledge {__version__}",
    )
    document = replace(document, meta=meta, warnings=tuple(document.warnings) + tuple(warnings))

    outputs = render_document(document, options)
    return ConversionResult(
        source_path=path_obj,
        format=fmt,
        outputs=outputs,
        images=document.images,
        warnings=document.warnings,
    )
