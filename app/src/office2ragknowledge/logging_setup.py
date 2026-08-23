"""ログの構成 (REQ-NF-013, REQ-NF-014, REQ-F-095)。

**この関数は CLI 層からのみ呼ぶ。** ライブラリとして import された場合に、
利用者のログ設定を勝手に変えないためである (``__init__`` で ``NullHandler``
のみを付けている)。

**本文テキストをログに出力してはならない** (REQ-NF-014)。出力してよいのは
ファイルパス・件数・シート名・エラー種別に限る。
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal

__all__ = ["LOGGER_NAME", "JsonFormatter", "setup_logging"]

LOGGER_NAME = "office2ragknowledge"

_LEVELS: dict[str, int] = {
    "quiet": logging.WARNING,
    "info": logging.INFO,
    "verbose": logging.DEBUG,
}

#: 構造化ログに載せる追加フィールド (P003 §12A.4)。
_EXTRA_FIELDS = ("event", "path", "code", "detail")


class JsonFormatter(logging.Formatter):
    """1行1レコードの JSON を出力する。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created).astimezone().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        for field in _EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(
    level: Literal["quiet", "info", "verbose"] = "info",
    fmt: Literal["text", "json"] = "text",
    log_file: Path | None = None,
) -> None:
    """ロガーを構成する。**ルートロガーは触らない。**

    2回呼んでもハンドラが重複しないよう、既存のハンドラを取り除いてから付ける。
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(_LEVELS.get(level, logging.INFO))
    logger.propagate = False

    for handler in list(logger.handlers):
        if not isinstance(handler, logging.NullHandler):
            logger.removeHandler(handler)
            handler.close()

    formatter: logging.Formatter
    if fmt == "json":
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    # 標準エラーへ。標準出力は変換結果とサマリのために空けておく (REQ-NF-013)
    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(formatter)
    logger.addHandler(stream)

    if log_file is not None:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
