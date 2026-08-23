"""細工ファイルをプログラム生成するヘルパ (P006 §3.1)。

**リポジトリに悪意あるファイルを置かない**ため、テスト実行時に生成する。
"""

from __future__ import annotations

import zipfile
from pathlib import Path

__all__ = [
    "XXE_XML",
    "billion_laughs_xml",
    "make_broken_zip",
    "make_ole_file",
    "make_path_traversal_zip",
    "make_too_many_entries_zip",
    "make_zip_bomb",
]

XXE_XML = b"""<?xml version="1.0"?>
<!DOCTYPE root [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<root xmlns="http://schemas.openxmlformats.org/wordprocessingml/2006/main">&xxe;</root>
"""


def billion_laughs_xml(depth: int = 9) -> bytes:
    """入れ子の実体参照を持つ XML を作る (十億の笑い)。"""
    entities = ['<!ENTITY a0 "lol">']
    for i in range(1, depth):
        refs = "".join(f"&a{i - 1};" for _ in range(10))
        entities.append(f'<!ENTITY a{i} "{refs}">')
    body = f"&a{depth - 1};"
    return (
        '<?xml version="1.0"?>\n<!DOCTYPE root [\n'
        + "\n".join(entities)
        + f"\n]>\n<root>{body}</root>\n"
    ).encode()


def make_zip_bomb(path: Path, entry_size: int = 50 * 1024 * 1024) -> Path:
    """圧縮率が極端に高いエントリを持つ ZIP を作る。"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr("[Content_Types].xml", b"\x00" * entry_size)
    return path


def make_path_traversal_zip(path: Path) -> Path:
    """エントリ名に ``../`` を含む ZIP を作る。"""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("../../evil.xml", "<evil/>")
    return path


def make_absolute_path_zip(path: Path) -> Path:
    """エントリ名が絶対パスの ZIP を作る。"""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("/etc/passwd", "root:x:0:0")
    return path


def make_too_many_entries_zip(path: Path, count: int = 10_050) -> Path:
    """エントリ数が上限を超える ZIP を作る。"""
    with zipfile.ZipFile(path, "w") as zf:
        for i in range(count):
            zf.writestr(f"e{i}.txt", "x")
    return path


def make_broken_zip(path: Path) -> Path:
    """途中で切れた ZIP を作る。"""
    path.write_bytes(b"PK\x03\x04" + b"\x00" * 20)
    return path


def make_ole_file(path: Path) -> Path:
    """OLE 複合ファイル (パスワード保護を模す) のシグネチャを持つファイルを作る。"""
    path.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100)
    return path
