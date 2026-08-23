"""公開 API の戻り値型 (P002 §6.4)。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .document import DocumentMeta
from .media import ExtractedImage
from .options import DocumentFormat, OutputMode

__all__ = [
    "BatchResult",
    "ConversionResult",
    "DocumentInfo",
    "ExtractedImage",
    "FailureInfo",
    "MarkdownOutput",
    "WrittenFiles",
]


@dataclass(frozen=True, slots=True)
class MarkdownOutput:
    """1つの Markdown 出力。

    Excel は既定で2件 (表計算モードと方眼紙モード)、他形式は1件になる。
    """

    markdown: str
    meta: DocumentMeta
    mode: OutputMode | None = None
    """Excel は TABLE / GRID、それ以外は None。"""

    filename_suffix: str = ".md"
    """``.table.md`` / ``.grid.md`` / ``.md``。モードの指定によらず固定 (P002 §5.2)。"""

    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ConversionResult:
    """1ファイルの変換結果。**副作用を持たない** (ファイルを書き出さない)。"""

    source_path: Path
    format: DocumentFormat
    outputs: tuple[MarkdownOutput, ...] = ()
    """1件 (Word/PowerPoint) または 1〜2件 (Excel)。"""

    images: tuple[ExtractedImage, ...] = ()
    """出力間で共有する。Excel の2出力でも重複して持たない (REQ-F-069)。"""

    warnings: tuple[str, ...] = ()

    @property
    def markdown(self) -> str:
        """出力が1件のときにその Markdown を返す。

        Raises:
            ValueError: 出力が1件でない場合。

        複数出力時に先頭を返す実装だと、Excel を渡した利用者が黙って表計算
        モードだけを受け取り、**方眼紙モードの出力を取りこぼす**。取りこぼしを
        黙って起こすより明示的に失敗させる (ADR-009)。
        """
        if len(self.outputs) == 1:
            return self.outputs[0].markdown
        raise ValueError(
            f"この結果には出力が {len(self.outputs)} 件あるため、markdown プロパティでは"
            "一意に取得できません。outputs を参照してください "
            "(Excel は既定で表計算モードと方眼紙モードの2件を返します)。"
        )


@dataclass(frozen=True, slots=True)
class FailureInfo:
    """変換に失敗した1ファイルの記録。"""

    path: Path
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class BatchResult:
    """バッチ変換の結果。

    ``succeeded`` は **入力ファイル単位**、``written_files`` は実際に書き出した
    ファイル。Excel の二重出力があるため両者の件数は一致しない (REQ-F-094)。
    """

    succeeded: tuple[Path, ...] = ()
    skipped: tuple[tuple[Path, str], ...] = ()
    failures: tuple[FailureInfo, ...] = ()
    warnings: tuple[tuple[Path, str], ...] = ()
    written_files: tuple[Path, ...] = ()
    elapsed_seconds: float = 0.0

    @property
    def exit_code(self) -> int:
        """終了コード 0 / 1 を算出する (2 は CLI 層が返す)。"""
        return 1 if self.failures else 0


@dataclass(frozen=True, slots=True)
class DocumentInfo:
    """``inspect`` の結果 (REQ-F-091)。"""

    path: Path
    size_bytes: int
    status: Literal["ok", "unsupported", "protected", "corrupted"]
    format: DocumentFormat | None = None
    password_protected: bool = False
    unit_count: int = 0
    unit_label: str = ""
    table_count: int = 0
    shape_count: int = 0
    shape_with_text_count: int = 0
    image_count: int = 0
    estimated_chars: int = 0
    table_region_count: int | None = None
    """Excel のみ。他形式では None。"""

    formula_without_cache_count: int | None = None
    """Excel のみ。他形式では None。"""


@dataclass(frozen=True, slots=True)
class WrittenFiles:
    """``write_result`` が実際に書き出したファイル。"""

    markdown_paths: tuple[Path, ...] = ()
    image_paths: tuple[Path, ...] = ()
    skipped_paths: tuple[Path, ...] = ()
