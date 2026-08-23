"""U005-T4/T5 の単体テスト: CLI の画面・検証・終了コード。"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

import office2ragknowledge as pkg
from office2ragknowledge.cli.main import app
from tests.helpers.make_office import make_docx, make_xlsx

runner = CliRunner()


def make_inputs(root: Path) -> Path:
    src = root / "in"
    src.mkdir()
    make_docx(src / "a.docx", [("p", "本文")])
    make_xlsx(src / "b.xlsx", {"S1": [["x", "y"]]})
    return src


# ケース1: --version
def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "office2rag 1.0.0" in result.output
    assert "Python" in result.output


# ケース2: --help
def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "convert" in result.output
    assert "inspect" in result.output


# ケース3: サブコマンドなしで終了コード 2
def test_no_subcommand_exits_2() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 2


# ケース4: 正常変換で終了コード 0
def test_convert_success(tmp_path: Path) -> None:
    src = make_inputs(tmp_path)
    result = runner.invoke(app, ["convert", str(src), "-o", str(tmp_path / "out")])
    assert result.exit_code == 0, result.output


# ケース5: 1件失敗で終了コード 1
def test_convert_partial_failure(tmp_path: Path) -> None:
    src = make_inputs(tmp_path)
    (src / "broken.docx").write_bytes(b"PK\x03\x04broken")
    result = runner.invoke(app, ["convert", str(src), "-o", str(tmp_path / "out")])
    assert result.exit_code == 1
    assert "失敗" in result.output


# ケース6: 引数不正で終了コード 2
def test_invalid_option_exits_2(tmp_path: Path) -> None:
    src = make_inputs(tmp_path)
    result = runner.invoke(app, ["convert", str(src), "--excel-modes", "invalid"])
    assert result.exit_code == 2


def test_missing_path_exits_2(tmp_path: Path) -> None:
    result = runner.invoke(app, ["convert", str(tmp_path / "nope")])
    assert result.exit_code == 2
    assert "見つかりません" in result.output


# ケース7/8: サマリの出力ファイル数
def test_summary_shows_output_file_count(tmp_path: Path) -> None:
    src = make_inputs(tmp_path)
    result = runner.invoke(app, ["convert", str(src), "-o", str(tmp_path / "out")])
    assert "出力ファイル:" in result.output
    assert "成功 2 件" in result.output
    assert "出力ファイル: 3 件" in result.output


# ケース11: --quiet で1行目のみ
def test_quiet(tmp_path: Path) -> None:
    src = make_inputs(tmp_path)
    result = runner.invoke(app, ["convert", str(src), "-o", str(tmp_path / "out"), "-q"])
    assert "変換結果:" in result.output
    assert "出力ファイル:" not in result.output


# ケース12: --stdout が Markdown のみ
def test_stdout_mode(tmp_path: Path) -> None:
    src = make_inputs(tmp_path)
    result = runner.invoke(app, ["convert", str(src / "a.docx"), "--stdout"])
    assert result.exit_code == 0
    assert result.output.startswith("---")
    assert "変換結果:" not in result.output


# ケース: --stdout + Excel + both で E-017
def test_stdout_with_excel_both_is_error(tmp_path: Path) -> None:
    src = make_inputs(tmp_path)
    result = runner.invoke(app, ["convert", str(src / "b.xlsx"), "--stdout"])
    assert result.exit_code == 2
    assert "--excel-modes" in result.output


def test_stdout_with_excel_single_mode_works(tmp_path: Path) -> None:
    src = make_inputs(tmp_path)
    result = runner.invoke(
        app, ["convert", str(src / "b.xlsx"), "--stdout", "--excel-modes", "grid"]
    )
    assert result.exit_code == 0
    assert 'output_mode: "grid"' in result.output


# ケース13/14: inspect
def test_inspect(tmp_path: Path) -> None:
    src = make_inputs(tmp_path)
    result = runner.invoke(app, ["inspect", str(src)])
    assert result.exit_code == 0
    assert "ファイル" in result.output
    assert "領域" in result.output


# ケース15: inspect --json
def test_inspect_json(tmp_path: Path) -> None:
    src = make_inputs(tmp_path)
    result = runner.invoke(app, ["inspect", str(src), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload) == 2
    excel = next(p for p in payload if p["path"].endswith("b.xlsx"))
    word = next(p for p in payload if p["path"].endswith("a.docx"))
    assert excel["table_region_count"] is not None
    assert word["table_region_count"] is None


# ケース16: スタックトレースが出ない
def test_no_traceback_on_error(tmp_path: Path) -> None:
    result = runner.invoke(app, ["convert", str(tmp_path / "nope")])
    assert "Traceback" not in result.output


# ケース18: 日本語ファイル名
def test_japanese_filename(tmp_path: Path) -> None:
    src = tmp_path / "in"
    src.mkdir()
    make_xlsx(src / "体制図.xlsx", {"組織": [["部門", "人数"]]})
    out = tmp_path / "out"
    result = runner.invoke(app, ["convert", str(src), "-o", str(out)])
    assert result.exit_code == 0
    assert (out / "体制図.table.md").is_file()
    assert (out / "体制図.grid.md").is_file()


# ケース19/20: 公開シンボル
def test_public_symbols_exist() -> None:
    missing = [name for name in pkg.__all__ if not hasattr(pkg, name)]
    assert missing == []


def test_key_public_api_is_importable() -> None:
    from office2ragknowledge import (  # noqa: F401
        ConvertOptions,
        convert_batch,
        convert_bytes,
        convert_file,
        inspect_file,
        write_result,
    )
