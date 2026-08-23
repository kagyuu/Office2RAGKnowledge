"""変換オプションと列挙型 (P002 §6.2)。

すべて不変 (frozen) とする。並列ワーカーへ受け渡す際の安全性と、
REQ-NF-018 の冪等性 (途中で設定が変わらないこと) を型で担保するため。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Literal

__all__ = [
    "BatchOptions",
    "Config",
    "ConvertOptions",
    "DocumentFormat",
    "ExcelModes",
    "ExcelOptions",
    "ImageMode",
    "LogOptions",
    "OnExists",
    "OutputMode",
    "ShapeStyle",
]


class ExcelModes(StrEnum):
    """Excel の出力モードの指定 (入力としての指定。BOTH を取りうる)。"""

    BOTH = "both"
    TABLE = "table"
    GRID = "grid"


class OutputMode(StrEnum):
    """個々の出力が属するモード (出力の実体。BOTH を取らない)。

    front matter の ``output_mode`` に出力される。
    """

    TABLE = "table"
    GRID = "grid"


class ShapeStyle(StrEnum):
    """図形テキストブロックの体裁 (P002 §5.7)。"""

    QUOTE = "quote"
    HEADING = "heading"
    PLAIN = "plain"


class ImageMode(StrEnum):
    """画像バイナリの出力有無 (REQ-F-049)。"""

    NONE = "none"
    EXTRACT = "extract"


class OnExists(StrEnum):
    """出力先に同名ファイルがある場合の挙動 (REQ-F-005)。"""

    SKIP = "skip"
    OVERWRITE = "overwrite"
    FAIL = "fail"


class DocumentFormat(StrEnum):
    """対応する入力形式。"""

    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"


@dataclass(frozen=True, slots=True)
class ExcelOptions:
    """Excel 固有の変換設定 (P002 §6.2)。"""

    modes: ExcelModes = ExcelModes.BOTH
    """生成するモード。既定は両方 (REQ-F-064, REQ-F-067)。"""

    grid_separator: str = ""
    """方眼紙モードで同一行のセルを連結する際の区切り文字 (REQ-F-059)。

    既定は空文字。方眼紙用法では1つの文が複数セルに分割されているため、
    区切り文字を挟むと文が分断される。
    """

    table_regions: bool = True
    """表領域の分割検出を行うか (REQ-F-054, REQ-F-056)。"""

    max_table_regions: int = 100
    """検出する表領域数の上限。超えたら分割せず1テーブルにする (REQ-F-057)。"""

    formulas: bool = False
    """数式を値と併記するか。方眼紙モードでは無視される (P002 §5.5.4)。"""

    max_rows: int = 10_000
    """1シートあたりの出力上限行数。0 は無制限 (REQ-F-029)。"""


@dataclass(frozen=True, slots=True)
class ConvertOptions:
    """1ファイルの変換設定 (P002 §6.2)。"""

    excel: ExcelOptions = field(default_factory=ExcelOptions)
    shapes: bool = True
    """オートシェープ内テキストを抽出するか (REQ-F-031)。"""

    shape_style: ShapeStyle = ShapeStyle.QUOTE
    images: ImageMode = ImageMode.NONE
    include_hidden: bool = False
    """非表示シート/行/列/スライドを含めるか (REQ-F-027, REQ-F-045)。"""

    notes: bool = True
    """PowerPoint の発表者ノートを出力するか (REQ-F-044)。"""

    headers_footers: bool = False
    """Word のヘッダー・フッターを出力するか (REQ-F-017)。"""

    comments: bool = False
    """Word のコメントを出力するか (REQ-F-019)。"""

    front_matter: bool = True
    """YAML front matter を出力するか (REQ-F-007)。"""


@dataclass(frozen=True, slots=True)
class BatchOptions:
    """複数ファイルの変換設定 (P002 §6.2)。"""

    convert: ConvertOptions = field(default_factory=ConvertOptions)
    recursive: bool = False
    on_exists: OnExists = OnExists.SKIP
    jobs: int | None = None
    """並列ワーカー数。None は CPU コア数 (REQ-NF-015)。"""

    output_dir: Path | None = None
    """出力先。None は入力ファイルと同じ階層 (REQ-F-004)。"""


@dataclass(frozen=True, slots=True)
class LogOptions:
    """ログの設定 (REQ-NF-013)。"""

    level: Literal["quiet", "info", "verbose"] = "info"
    format: Literal["text", "json"] = "text"
    file: Path | None = None


@dataclass(frozen=True, slots=True)
class Config:
    """設定ファイルと既定値をマージした設定 (API-07 の戻り値)。"""

    convert: ConvertOptions = field(default_factory=ConvertOptions)
    batch: BatchOptions = field(default_factory=BatchOptions)
    log: LogOptions = field(default_factory=LogOptions)
