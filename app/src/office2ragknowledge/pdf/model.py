"""ライブラリ非依存の PDF データ型 (P003 §7A.2)。

``pdf/backend.py`` が PDF ライブラリの出力をこの型に変換する。``pdf/`` の他の
モジュールと ``parsers/pdf.py`` はこの型だけを扱い、PDF ライブラリを知らない
(ADR-012)。ライブラリを差し替えるときは、同じ型を返す backend を書けばよい。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

__all__ = [
    "PdfChar",
    "PdfMetadata",
    "PdfPage",
    "PdfSource",
    "Rect",
    "StructInfo",
    "StructPath",
]

Rect = tuple[float, float, float, float]
"""矩形 (x0, top, x1, bottom)。ページ左上原点・ポイント単位。"""

StructPath = tuple[int, ...]
"""構造要素の経路。ルートからの ``/K`` 配列内の位置の列 (ArchitectureHandbook §4-9)。"""


@dataclass(frozen=True, slots=True)
class PdfChar:
    """1文字。座標はページ左上原点。"""

    text: str
    x0: float
    top: float
    x1: float
    bottom: float
    size: float
    path: StructPath | None = None
    """文字を内包する最も内側の構造要素の経路。構造の外 (Artifact 等) は None。"""

    kid_index: int | None = None
    """その文字の MCID が、構造要素の ``/K`` 配列の何番目にあるか (※CR-003)。

    構造木の中でテキストと子要素を ``/K`` の順に並べるために使う (P003 §7A.3)。
    ライブラリが提供しない場合は None。
    """

    @property
    def center_y(self) -> float:
        return (self.top + self.bottom) / 2


@dataclass(frozen=True, slots=True)
class PdfPage:
    """1ページ分の抽出結果。"""

    number: int
    """1起点のページ番号。"""

    width: float
    height: float
    chars: tuple[PdfChar, ...] = ()
    """ライブラリの構造化テキストの出現順 (概ね内容ストリームの順)。"""

    segments: tuple[tuple[int, int], ...] = ()
    """同じテキストブロックに属する文字の範囲 ``(開始, 終了)`` の並び。"""

    figure_rects: tuple[Rect, ...] = ()
    """近接するベクター描画をまとめた矩形。"""

    image_count: int = 0


@dataclass(frozen=True, slots=True)
class StructInfo:
    """構造要素の属性。経路をキーとする辞書で保持する。"""

    tag: str
    """RoleMap を適用した後の標準タグ名。"""

    alt: str | None = None
    list_numbering: str | None = None
    col_span: int = 1
    row_span: int = 1


@dataclass(frozen=True, slots=True)
class PdfMetadata:
    """文書情報辞書 (無ければ XMP) から得たメタデータ。"""

    title: str | None = None
    author: str | None = None
    created_at: datetime | None = None
    modified_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class PdfSource:
    """1つの PDF 文書の抽出結果。"""

    pages: tuple[PdfPage, ...]
    struct: Mapping[StructPath, StructInfo] = field(default_factory=dict)
    has_struct_tree: bool = False
    metadata: PdfMetadata = field(default_factory=PdfMetadata)
    copy_restricted: bool = False
