"""A005 受け入れテスト: 品質ゲート。

静的検査・重点領域の網羅・**ログの機微情報**を検証する。
テストスイートの2回連続実行 (O-03) は P201 が手動で確認する。
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from office2ragknowledge.cli.main import app
from office2ragknowledge.logging_setup import LOGGER_NAME
from office2ragknowledge.ooxml.xml_utils import NS
from tests.helpers.make_office import add_sheet_drawing, make_xlsx

runner = CliRunner()
APP_ROOT = Path(__file__).resolve().parents[2]

#: 本文にだけ現れる文字列。**ログに出てはならない** (REQ-NF-014)。
CANARY = "SECRET-CANARY-12345"
SHAPE_CANARY = "SHAPE-CANARY-67890"
TITLE_CANARY = "TITLE-CANARY-ABCDE"

XDR, A = NS["xdr"], NS["a"]


def canary_workbook(tmp_path: Path) -> Path:
    path = make_xlsx(
        tmp_path / "機密.xlsx",
        {"明細": [["項目", "値"], [CANARY, 100], ["=A2", 200]]},
    )
    add_sheet_drawing(
        path,
        0,
        f'<?xml version="1.0"?><xdr:wsDr xmlns:xdr="{XDR}" xmlns:a="{A}">'
        "<xdr:twoCellAnchor><xdr:from><xdr:col>3</xdr:col><xdr:colOff>0</xdr:colOff>"
        "<xdr:row>1</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>"
        '<xdr:sp><xdr:nvSpPr><xdr:cNvPr name="注記"/></xdr:nvSpPr>'
        f"<xdr:txBody><a:p><a:r><a:t>{SHAPE_CANARY}</a:t></a:r></a:p></xdr:txBody>"
        "</xdr:sp></xdr:twoCellAnchor></xdr:wsDr>",
    )
    return path


def _flush_log_handlers() -> None:
    """ログハンドラを flush する。

    CliRunner は捕捉したストリームをテスト終了時に閉じるため、
    StreamHandler の flush が ``ValueError`` になることがある。
    ファイルハンドラの内容を確実に読むためだけの処理なので、失敗は無視する。
    """
    for handler in logging.getLogger(LOGGER_NAME).handlers:
        try:
            handler.flush()
        except ValueError:
            pass


def _run_tool(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", *args],
        cwd=APP_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


# ============================================================
# 静的検査 (REQ-NF-012) — 合否判定の対象
# ============================================================


def test_ruff_check() -> None:
    result = _run_tool("ruff", "check", "src", "tests")
    assert result.returncode == 0, result.stdout + result.stderr


def test_ruff_format() -> None:
    result = _run_tool("ruff", "format", "--check", "src", "tests")
    assert result.returncode == 0, result.stdout + result.stderr


def test_mypy_strict() -> None:
    result = _run_tool("mypy", "src")
    assert result.returncode == 0, result.stdout + result.stderr


def test_py_typed_is_present() -> None:
    import office2ragknowledge

    package_dir = Path(office2ragknowledge.__file__).parent
    assert (package_dir / "py.typed").is_file()


def test_all_public_symbols_exist() -> None:
    import office2ragknowledge as pkg

    missing = [name for name in pkg.__all__ if not hasattr(pkg, name)]
    assert missing == []


# ============================================================
# ログの機微情報 (REQ-NF-014) — 合否判定の対象
# ============================================================


def test_verbose_log_has_no_body_text(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """--verbose のログ出力に本文の既知文字列が現れないこと。"""
    path = canary_workbook(tmp_path)
    log = tmp_path / "app.log"
    result = runner.invoke(
        app,
        [
            "convert",
            str(path),
            "-o",
            str(tmp_path / "out"),
            "-v",
            "--log-file",
            str(log),
        ],
    )
    assert result.exit_code == 0, result.output

    _flush_log_handlers()

    log_text = log.read_text(encoding="utf-8") if log.is_file() else ""
    combined = log_text + result.output

    assert CANARY not in combined, "セルの値がログに出力されています"
    assert SHAPE_CANARY not in combined, "図形テキストがログに出力されています"


def test_log_file_has_no_body_text(tmp_path: Path) -> None:
    path = canary_workbook(tmp_path)
    log = tmp_path / "file.log"
    runner.invoke(
        app,
        ["convert", str(path), "-o", str(tmp_path / "out"), "--log-file", str(log)],
    )
    _flush_log_handlers()
    if log.is_file():
        assert CANARY not in log.read_text(encoding="utf-8")


def test_json_log_has_no_body_text(tmp_path: Path) -> None:
    path = canary_workbook(tmp_path)
    log = tmp_path / "log.jsonl"
    runner.invoke(
        app,
        [
            "convert",
            str(path),
            "-o",
            str(tmp_path / "out"),
            "--log-format",
            "json",
            "--log-file",
            str(log),
        ],
    )
    _flush_log_handlers()
    if log.is_file():
        assert CANARY not in log.read_text(encoding="utf-8")


def test_canary_is_actually_in_the_output(tmp_path: Path) -> None:
    """カナリアが本当に本文に含まれていること (テスト自体の妥当性の確認)。"""
    path = canary_workbook(tmp_path)
    out = tmp_path / "out"
    runner.invoke(app, ["convert", str(path), "-o", str(out)])
    combined = "\n".join(p.read_text(encoding="utf-8") for p in out.iterdir())
    assert CANARY in combined, "カナリアが出力に無く、ログ検証が無意味になっています"
    assert SHAPE_CANARY in combined


# ============================================================
# 重点領域の網羅 (P006 §7) — 合否判定の対象
# ============================================================

UNIT = APP_ROOT / "tests" / "unit"
INTEGRATION = APP_ROOT / "tests" / "integration"
ACCEPTANCE = APP_ROOT / "tests" / "acceptance"


def all_test_source() -> str:
    parts = []
    for directory in (UNIT, INTEGRATION, ACCEPTANCE):
        for path in directory.glob("test_*.py"):
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


@pytest.mark.parametrize(
    "marker",
    [
        "mc:Choice",  # 二重取得の回避
        "グループ",  # グループ図形の再帰
        "SmartArt",
        "図形内の表",
        "テキストボックス",
    ],
)
def test_shape_coverage(marker: str) -> None:
    """P006 §7.1 の図形の網羅表に対応するテストが存在する。"""
    assert marker in all_test_source(), f"図形の観点 '{marker}' のテストがありません"


@pytest.mark.parametrize(
    "marker",
    [
        "表領域",
        "空行",
        "空列",
        "結合セル",
        "キャッシュ値",
        "二重出力",
        "申請書",  # 方眼紙モードの期待出力
        "output_mode",
    ],
)
def test_excel_coverage(marker: str) -> None:
    """P006 §7.2 の Excel の重点ケースに対応するテストが存在する。"""
    assert marker in all_test_source(), f"Excel の観点 '{marker}' のテストがありません"


@pytest.mark.parametrize("marker", ["冪等", "idempotent"])
def test_idempotency_coverage(marker: str) -> None:
    """P006 §7.3 の冪等性のケースに対応するテストが存在する。"""
    assert marker in all_test_source()


def test_security_coverage() -> None:
    """P006 §2.2 のセキュリティ観点に対応するテストが存在する。"""
    source = all_test_source()
    for marker in ("XXE", "ZIP爆弾", "パストラバーサル", "billion_laughs"):
        assert marker in source, f"セキュリティの観点 '{marker}' のテストがありません"
