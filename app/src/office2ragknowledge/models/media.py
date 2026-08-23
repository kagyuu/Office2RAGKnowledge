"""抽出した画像のバイナリ (P002 §6.4)。

``document.py`` と ``result.py`` の双方から参照されるため、独立したモジュールに
置いて循環 import を避ける。
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["ExtractedImage"]


@dataclass(frozen=True, slots=True)
class ExtractedImage:
    """抽出した画像。``images=EXTRACT`` のときのみ収集する。"""

    media_ref: str
    data: bytes
    extension: str
    index: int
