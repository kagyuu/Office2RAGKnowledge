"""中間表現の中核 (P002 §7.3.1, §7.3.2)。

``Document.blocks`` の順序が、そのまま Markdown の出力順序である (INV-04)。
レンダラは並べ替えを行わない。例外は ``Footnote`` と ``anchor is None`` の
``ShapeText`` のみで、これらはレンダラが文書末尾へ移送する。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

from .inline import InlineRun, ListItem, ShapeParagraph, TableRow
from .media import ExtractedImage
from .options import DocumentFormat

__all__ = [
    "Block",
    "Document",
    "DocumentMeta",
    "Footnote",
    "Heading",
    "Image",
    "ListBlock",
    "Paragraph",
    "ShapeText",
    "SlideBreak",
    "Table",
]


@dataclass(frozen=True, slots=True)
class Block:
    """本文ブロックの基底。判別は型パターン (``match``) で行う。"""


@dataclass(frozen=True, slots=True)
class Heading(Block):
    """見出し。``level`` は出力時の ``#`` の数 (1〜6)。"""

    level: int
    runs: tuple[InlineRun, ...] = ()


@dataclass(frozen=True, slots=True)
class Paragraph(Block):
    """通常段落。"""

    runs: tuple[InlineRun, ...] = ()


@dataclass(frozen=True, slots=True)
class ListBlock(Block):
    """連続するリスト項目のまとまり。"""

    items: tuple[ListItem, ...] = ()


@dataclass(frozen=True, slots=True)
class Table(Block):
    """表 (Word / PowerPoint / 図形内)。

    全行の列数は揃っていること (INV-01)。結合セルは値を複製して矩形を保つ。
    """

    rows: tuple[TableRow, ...] = ()
    has_header: bool = True


@dataclass(frozen=True, slots=True)
class ShapeText(Block):
    """オートシェープ内のテキスト。**本アプリの中核** (REQ-F-031〜040)。

    ``paragraphs`` と ``tables`` の少なくとも一方が非空である (INV-05)。
    テキストを持たない図形はブロック化しない。
    """

    shape_kind: str = "図形"
    shape_name: str | None = None
    anchor: str | None = None
    """Excel のセル参照など。位置を特定できない場合は None。"""

    group_path: tuple[str, ...] = ()
    """グループの入れ子名を外側から並べたもの。空なら非グループ。"""

    paragraphs: tuple[ShapeParagraph, ...] = ()
    tables: tuple[Table, ...] = ()


@dataclass(frozen=True, slots=True)
class Image(Block):
    """画像への参照。バイナリ自体は ``ConversionResult.images`` が保持する。"""

    alt_text: str = ""
    media_ref: str = ""
    extension: str = "png"
    index: int = 1
    """文書内の出現順 (1起点)。出力ファイル名の連番に用いる。"""


@dataclass(frozen=True, slots=True)
class Footnote(Block):
    """脚注本文。レンダラが文書末尾にまとめて出力する (INV-04)。"""

    marker: str = "1"
    runs: tuple[InlineRun, ...] = ()


@dataclass(frozen=True, slots=True)
class SlideBreak(Block):
    """PowerPoint のスライド境界。"""

    slide_number: int = 1
    slide_title: str | None = None
    notes: tuple[ShapeParagraph, ...] = ()


@dataclass(frozen=True, slots=True)
class DocumentMeta:
    """front matter の元データ (P001 §7.1)。

    キーの出現順は ``render/frontmatter.py`` が固定する (冪等性のため)。
    """

    source_file: str
    source_path: str
    source_format: DocumentFormat
    source_size_bytes: int
    source_sha256: str
    converter: str
    converted_at: datetime
    title: str | None = None
    author: str | None = None
    created_at: datetime | None = None
    modified_at: datetime | None = None
    stats: Mapping[str, int] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Document:
    """形式非依存のドキュメントモデル。"""

    format: DocumentFormat
    title: str
    meta: DocumentMeta
    blocks: tuple[Block, ...] = ()
    warnings: tuple[str, ...] = ()
    images: tuple[ExtractedImage, ...] = ()
    """抽出した画像バイナリ。``images=EXTRACT`` のときのみ非空。

    パーサが収集し、``ConversionResult.images`` へそのまま渡される。
    Excel の二重出力でも1つの中間表現が保持するため、重複しない (REQ-F-069)。
    """
