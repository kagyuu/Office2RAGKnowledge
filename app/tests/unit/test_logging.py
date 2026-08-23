"""U005-T3 の単体テスト: ログ基盤。

**本文テキストをログに出力してはならない** (REQ-NF-014)。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from office2ragknowledge.logging_setup import LOGGER_NAME, setup_logging


@pytest.fixture(autouse=True)
def _restore_logger():  # type: ignore[no-untyped-def]
    logger = logging.getLogger(LOGGER_NAME)
    original = list(logger.handlers)
    yield
    for handler in list(logger.handlers):
        if handler not in original:
            logger.removeHandler(handler)
            handler.close()


# ケース1: ハンドラが付く
def test_handler_is_added() -> None:
    setup_logging("info", "text", None)
    logger = logging.getLogger(LOGGER_NAME)
    assert any(isinstance(h, logging.StreamHandler) for h in logger.handlers)


# ケース2: ルートロガーにハンドラが追加されない
def test_root_logger_is_untouched() -> None:
    before = list(logging.getLogger().handlers)
    setup_logging("info", "text", None)
    assert logging.getLogger().handlers == before


# ケース3/4: レベル
def test_levels() -> None:
    setup_logging("quiet", "text", None)
    assert logging.getLogger(LOGGER_NAME).level == logging.WARNING
    setup_logging("verbose", "text", None)
    assert logging.getLogger(LOGGER_NAME).level == logging.DEBUG
    setup_logging("info", "text", None)
    assert logging.getLogger(LOGGER_NAME).level == logging.INFO


# ケース5: ファイルにも出力される
def test_log_file(tmp_path: Path) -> None:
    log = tmp_path / "app.log"
    setup_logging("info", "text", log)
    logging.getLogger(LOGGER_NAME).info("テストメッセージ")
    for handler in logging.getLogger(LOGGER_NAME).handlers:
        handler.flush()
    assert "テストメッセージ" in log.read_text(encoding="utf-8")


# ケース6/7: JSON 形式
def test_json_format(tmp_path: Path) -> None:
    log = tmp_path / "app.jsonl"
    setup_logging("info", "json", log)
    logging.getLogger(LOGGER_NAME).info(
        "変換しました", extra={"event": "convert.done", "detail": 3}
    )
    for handler in logging.getLogger(LOGGER_NAME).handlers:
        handler.flush()
    line = log.read_text(encoding="utf-8").strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["event"] == "convert.done"
    assert payload["level"] == "INFO"
    assert "ts" in payload
    assert "code" not in payload, "渡していないフィールドが含まれています"


# ケース8: 標準エラー側に出る (標準出力に混ざらない)
def test_logs_go_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging("info", "text", None)
    logging.getLogger(LOGGER_NAME).info("標準エラーへ")
    captured = capsys.readouterr()
    assert "標準エラーへ" not in captured.out


# ケース9: 日本語が化けない
def test_japanese_message(tmp_path: Path) -> None:
    log = tmp_path / "ja.log"
    setup_logging("info", "text", log)
    logging.getLogger(LOGGER_NAME).info("シート「明細」を処理しました")
    for handler in logging.getLogger(LOGGER_NAME).handlers:
        handler.flush()
    assert "シート「明細」" in log.read_text(encoding="utf-8")


# ケース10: 2回呼んでもハンドラが重複しない
def test_no_duplicate_handlers() -> None:
    setup_logging("info", "text", None)
    first = len(logging.getLogger(LOGGER_NAME).handlers)
    setup_logging("info", "text", None)
    assert len(logging.getLogger(LOGGER_NAME).handlers) == first
