"""安全な ZIP 読み取り (P003 §4.2)。

OOXML ファイルはすべて本モジュールの ``SafeZipReader`` を経由して開く。
ZIP爆弾 (REQ-NF-006) とパストラバーサル (REQ-NF-008) を、
アプリ全体で唯一の入口として防ぐ。

閾値は固定値とし、オプションでの変更を設けない。可変にすると
「上限を上げれば通る」という運用が定着し、防御の意味が失われるため。
"""

from __future__ import annotations

import io
import posixpath
import zipfile
from pathlib import Path
from types import TracebackType

from lxml import etree

from ..errors import CorruptedFileError, FileTooLargeError
from .xml_utils import NS, parse_xml

__all__ = [
    "MAX_COMPRESS_RATIO",
    "MAX_ENTRIES",
    "MAX_ENTRY_BYTES",
    "MAX_TOTAL_BYTES",
    "MAX_TOTAL_RATIO",
    "SafeZipReader",
]

MAX_TOTAL_RATIO = 200
"""展開後サイズの上限 (入力ファイルサイズに対する倍率)。"""

MAX_TOTAL_BYTES = 1024**3
"""展開後サイズの絶対上限 (1 GiB)。"""

MAX_ENTRY_BYTES = 512 * 1024**2
"""単一エントリの上限 (512 MiB)。"""

MAX_COMPRESS_RATIO = 1000
"""単一エントリの圧縮率の上限。ZIP爆弾の典型を弾く。"""

MAX_ENTRIES = 10_000
"""エントリ数の上限。"""


def _is_unsafe_name(name: str) -> bool:
    """エントリ名が出力先の外を指しうるかを判定する (REQ-NF-008)。"""
    if not name:
        return True
    normalized = name.replace("\\", "/")
    if normalized.startswith("/"):
        return True
    # ドライブレター (C:/...) を含む
    if len(normalized) >= 2 and normalized[1] == ":":
        return True
    return any(part == ".." for part in normalized.split("/"))


class SafeZipReader:
    """検査付きの ZIP リーダー。コンテキストマネージャとして使う。"""

    def __init__(self, source: Path | str | bytes, *, source_size: int | None = None) -> None:
        self._source: Path | bytes
        if isinstance(source, bytes):
            self._buffer: io.BytesIO | None = io.BytesIO(source)
            size = source_size if source_size is not None else len(source)
            target: io.BytesIO | Path = self._buffer
            self._source = source
        else:
            self._buffer = None
            path = Path(source)
            size = source_size if source_size is not None else path.stat().st_size
            target = path
            self._source = path
        self._source_size = max(size, 1)
        try:
            self._zip = zipfile.ZipFile(target)
        except zipfile.BadZipFile as exc:
            raise CorruptedFileError("ファイルが破損しているため読み取れません") from exc
        self._validate()

    def _validate(self) -> None:
        infos = self._zip.infolist()
        if len(infos) > MAX_ENTRIES:
            raise FileTooLargeError(
                f"ZIP のエントリ数が上限 ({MAX_ENTRIES}) を超えています: {len(infos)}"
            )
        total = 0
        for info in infos:
            if _is_unsafe_name(info.filename):
                raise CorruptedFileError(
                    f"ファイル内に不正なパスのエントリが含まれています: {info.filename!r}"
                )
            if info.file_size > MAX_ENTRY_BYTES:
                raise FileTooLargeError("展開後のサイズが上限を超えています")
            if info.compress_size > 0:
                ratio = info.file_size / info.compress_size
                if ratio > MAX_COMPRESS_RATIO:
                    raise FileTooLargeError("展開後のサイズが上限を超えています")
            total += info.file_size
        limit = min(self._source_size * MAX_TOTAL_RATIO, MAX_TOTAL_BYTES)
        if total > limit:
            raise FileTooLargeError("展開後のサイズが上限を超えています")

    @property
    def source(self) -> Path | bytes:
        """検査済みの元データ (パスまたはバイト列)。

        openpyxl / python-docx / python-pptx など、独自にファイルを開く
        ライブラリへ渡すために用いる。**検査を経ていない入力を各ライブラリへ
        直接渡さないこと。**
        """
        return self._source

    def names(self) -> list[str]:
        """エントリ名の一覧を返す。"""
        return self._zip.namelist()

    def has(self, name: str) -> bool:
        """エントリが存在するか。"""
        return name in self._zip.namelist()

    def read(self, name: str) -> bytes:
        """エントリを読む。存在しなければ ``CorruptedFileError``。"""
        try:
            info = self._zip.getinfo(name)
        except KeyError as exc:
            raise CorruptedFileError(f"ファイル内に必要なパートが見つかりません: {name}") from exc
        data = self._zip.read(name)
        if len(data) > info.file_size:
            raise FileTooLargeError("展開後のサイズが上限を超えています")
        return data

    def read_xml(self, name: str) -> etree._Element:
        """エントリを安全に解析して要素を返す。"""
        return parse_xml(self.read(name))

    @staticmethod
    def _rels_name(part_name: str) -> str:
        """パートに対応する関係ファイルのパスを返す。"""
        directory = posixpath.dirname(part_name)
        base = posixpath.basename(part_name)
        if directory:
            return posixpath.join(directory, "_rels", f"{base}.rels")
        return f"_rels/{base}.rels"

    def resolve_rels(self, part_name: str) -> dict[str, str]:
        """``part_name`` の関係ファイルを読み、``Id -> 正規化済みTarget`` を返す。

        Target が相対パスの場合は ``part_name`` のディレクトリを基準に正規化する。
        正規化後のパスが ZIP のルートより上に出る場合は ``CorruptedFileError``。
        """
        directory = posixpath.dirname(part_name)
        rels_name = self._rels_name(part_name)
        if not self.has(rels_name):
            return {}
        root = self.read_xml(rels_name)
        result: dict[str, str] = {}
        for rel in root.iter(f"{{{NS['rel']}}}Relationship"):
            rel_id = rel.get("Id")
            target = rel.get("Target")
            if rel_id is None or target is None:
                continue
            if rel.get("TargetMode") == "External":
                # 外部参照は解決しない (REQ-NF-010)
                continue
            if target.startswith("/"):
                resolved = target.lstrip("/")
            else:
                resolved = posixpath.normpath(posixpath.join(directory, target))
            if resolved.startswith("..") or resolved.startswith("/"):
                raise CorruptedFileError(f"ファイル内の参照が不正な位置を指しています: {target!r}")
            result[rel_id] = resolved
        return result

    def rel_type_map(self, part_name: str) -> dict[str, str]:
        """``part_name`` の関係を ``Id -> Type`` で返す。"""
        rels_name = self._rels_name(part_name)
        if not self.has(rels_name):
            return {}
        root = self.read_xml(rels_name)
        return {
            rel.get("Id", ""): rel.get("Type", "")
            for rel in root.iter(f"{{{NS['rel']}}}Relationship")
        }

    def close(self) -> None:
        """開いているリソースを閉じる。"""
        self._zip.close()
        if self._buffer is not None:
            self._buffer.close()

    def __enter__(self) -> SafeZipReader:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
