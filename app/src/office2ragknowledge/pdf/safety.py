"""PDF の圧縮ストリームの展開サイズ検査 (REQ-NF-020 / P003 §4.4)。

PDF ライブラリはページの描画時にストリームを丸ごと展開するため、細工された
PDF (数百 KB が数 GB に展開されるもの) でメモリを使い果たしうる。描画の前に
Flate ストリームを上限付きで展開して大きさを数え、上限を超えたら拒否する。
"""

from __future__ import annotations

import zlib
from collections.abc import Iterable

from ..errors import FileTooLargeError

__all__ = ["MAX_STREAM_BYTES", "MAX_TOTAL_STREAM_BYTES", "check_inflated_sizes"]

#: 1ストリームの展開後サイズの上限。
MAX_STREAM_BYTES = 256 * 1024**2

#: 全ストリームの展開後サイズの合計の上限 (ZIP の検査と揃える。P003 §4.2)。
MAX_TOTAL_STREAM_BYTES = 1024**3

_CHUNK = 1024**2


def _inflated_size(raw: bytes, limit: int) -> int | None:
    """``raw`` を展開した大きさを数える。``limit`` を超えた時点で打ち切る。

    zlib として展開できなければ ``None`` (数えない。描画時にライブラリが扱う)。
    戻り値が ``limit`` を超えていれば上限超過である。
    """
    decomp = zlib.decompressobj()
    total = 0
    data = raw
    try:
        while data:
            out = decomp.decompress(data, _CHUNK)
            total += len(out)
            if total > limit:
                return total
            data = decomp.unconsumed_tail
            if not out and not data:
                break
        total += len(decomp.flush())
    except zlib.error:
        return None if total == 0 else total
    return total


def check_inflated_sizes(streams: Iterable[bytes]) -> None:
    """Flate ストリームの展開後サイズを検査する。

    上限は呼び出し時にモジュール定数を参照する (テストで差し替えられるように)。

    Raises:
        FileTooLargeError: 1ストリームまたは合計が上限を超えた (E-008)
    """
    per_stream = MAX_STREAM_BYTES
    total_limit = MAX_TOTAL_STREAM_BYTES
    total = 0
    for raw in streams:
        remaining = total_limit - total
        size = _inflated_size(raw, min(per_stream, remaining))
        if size is None:
            continue
        if size > per_stream or total + size > total_limit:
            raise FileTooLargeError("展開後のサイズが上限を超えています")
        total += size
