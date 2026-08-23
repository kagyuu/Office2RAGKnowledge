"""Office2RAGKnowledge — Office文書をRAG向けMarkdownに変換する。

公開APIの一覧は ``__all__`` を参照。ライブラリとして import された場合に
利用者のログ設定を壊さないよう、``NullHandler`` のみを付ける。
"""

from __future__ import annotations

import logging

__version__ = "1.0.0"

logging.getLogger("office2ragknowledge").addHandler(logging.NullHandler())

from .batch import convert_batch  # noqa: E402
from .config import load_config  # noqa: E402
from .convert import convert_bytes, convert_file  # noqa: E402
from .detect import detect_format  # noqa: E402
from .errors import (  # noqa: E402
    ConfigError,
    CorruptedFileError,
    FileTooLargeError,
    InputError,
    Office2RagError,
    OutputError,
    PasswordProtectedError,
    UnsupportedFormatError,
)
from .inspection import inspect_file  # noqa: E402
from .models import (  # noqa: E402
    BatchOptions,
    BatchResult,
    ConversionResult,
    ConvertOptions,
    DocumentFormat,
    DocumentInfo,
    ExcelModes,
    ExcelOptions,
    ExtractedImage,
    ImageMode,
    MarkdownOutput,
    OnExists,
    OutputMode,
    ShapeStyle,
    WrittenFiles,
)
from .writer import write_result  # noqa: E402

__all__ = [
    "BatchOptions",
    "BatchResult",
    "ConfigError",
    "ConversionResult",
    "ConvertOptions",
    "CorruptedFileError",
    "DocumentFormat",
    "DocumentInfo",
    "ExcelModes",
    "ExcelOptions",
    "ExtractedImage",
    "FileTooLargeError",
    "ImageMode",
    "InputError",
    "MarkdownOutput",
    "Office2RagError",
    "OnExists",
    "OutputError",
    "OutputMode",
    "PasswordProtectedError",
    "ShapeStyle",
    "UnsupportedFormatError",
    "WrittenFiles",
    "__version__",
    "convert_batch",
    "convert_bytes",
    "convert_file",
    "detect_format",
    "inspect_file",
    "load_config",
    "write_result",
]
