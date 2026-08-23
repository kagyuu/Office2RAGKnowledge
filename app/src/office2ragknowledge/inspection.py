"""文書構造の確認 (API-04 / REQ-F-091)。

**``convert_file`` と同じパーサを使う** (別実装を持たない)。

非対応形式・破損・パスワード保護は **例外にせず** ``status`` に格納して返す。
一覧の途中で止まると、他のファイルの情報まで得られなくなるため (P002 §3.5)。
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from .detect import detect_format, is_encrypted_ole
from .errors import CorruptedFileError, FileTooLargeError
from .models import (
    ConvertOptions,
    DocumentFormat,
    DocumentInfo,
    Heading,
    Image,
    Paragraph,
    ShapeText,
    Sheet,
    SlideBreak,
    Table,
)
from .ooxml.zip_reader import SafeZipReader
from .parsers.base import Parser
from .parsers.excel import ExcelParser
from .parsers.powerpoint import PowerPointParser
from .parsers.word import WordParser
from .render import render_document

__all__ = ["inspect_file"]

_PARSERS: dict[DocumentFormat, type[Parser]] = {
    DocumentFormat.DOCX: WordParser,
    DocumentFormat.XLSX: ExcelParser,
    DocumentFormat.PPTX: PowerPointParser,
}

_UNIT_LABELS = {
    DocumentFormat.DOCX: "段落",
    DocumentFormat.XLSX: "シート",
    DocumentFormat.PPTX: "スライド",
}

#: 構造解析用の固定時刻。``inspect`` は出力を書かないため値に意味はないが、
#: パーサが時刻を引数で受け取る契約 (REQ-NF-018) に合わせる。
_FIXED_TIME = datetime(2000, 1, 1, tzinfo=UTC)


def inspect_file(path: Path | str) -> DocumentInfo:
    """変換せずに文書構造を解析する。

    Raises:
        FileNotFoundError / PermissionError: 入力を読めない場合のみ
    """
    source = Path(path)
    data = source.read_bytes()  # 読めなければ OSError が伝播する
    size = len(data)

    if is_encrypted_ole(data):
        return DocumentInfo(
            path=source, size_bytes=size, status="protected", password_protected=True
        )

    try:
        fmt = detect_format(data)
    except (CorruptedFileError, FileTooLargeError):
        return DocumentInfo(path=source, size_bytes=size, status="corrupted")

    if fmt is None:
        return DocumentInfo(path=source, size_bytes=size, status="unsupported")

    options = ConvertOptions(front_matter=False)
    try:
        with SafeZipReader(data) as reader:
            document = _PARSERS[fmt]().parse(reader, source.name, options, _FIXED_TIME)
    except (CorruptedFileError, FileTooLargeError):
        return DocumentInfo(path=source, size_bytes=size, status="corrupted", format=fmt)

    sheets = [b for b in document.blocks if isinstance(b, Sheet)]
    slides = [b for b in document.blocks if isinstance(b, SlideBreak)]
    paragraphs = [b for b in document.blocks if isinstance(b, (Paragraph, Heading))]
    shape_blocks = [b for b in document.blocks if isinstance(b, ShapeText)]
    tables = [b for b in document.blocks if isinstance(b, Table)]
    images = [b for b in document.blocks if isinstance(b, Image)]

    if fmt is DocumentFormat.XLSX:
        unit_count = len(sheets)
        table_count = sum(len(s.regions) for s in sheets)
        shape_with_text = sum(len(s.shapes) for s in sheets)
        shape_total = sum(max(s.shape_count, len(s.shapes)) for s in sheets)
        region_count: int | None = table_count
        formula_missing: int | None = sum(s.formula_without_cache_count for s in sheets)
    else:
        unit_count = len(slides) if fmt is DocumentFormat.PPTX else len(paragraphs)
        table_count = len(tables)
        shape_with_text = len(shape_blocks)
        shape_total = len(shape_blocks)
        region_count = None
        formula_missing = None

    # 推定文字数は **実際にレンダリングして len() を取る** (推定式を使わない)
    outputs = render_document(document, options)
    estimated = len(outputs[0].markdown) if outputs else 0

    return DocumentInfo(
        path=source,
        size_bytes=size,
        status="ok",
        format=fmt,
        password_protected=False,
        unit_count=unit_count,
        unit_label=_UNIT_LABELS[fmt],
        table_count=table_count,
        shape_count=shape_total,
        shape_with_text_count=shape_with_text,
        image_count=len(images),
        estimated_chars=estimated,
        table_region_count=region_count,
        formula_without_cache_count=formula_missing,
    )
