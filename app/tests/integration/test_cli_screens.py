"""T004 結合テスト: CLI の画面と終了コード (SCR-01〜07)。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from office2ragknowledge.cli.main import app
from tests.helpers.make_office import make_docx, make_pptx, make_xlsx

runner = CliRunner()


def inputs(root: Path) -> Path:
    src = root / "in"
    src.mkdir()
    make_docx(src / "a.docx", [("p", "本文")])
    make_xlsx(src / "b.xlsx", {"S1": [["x", "y"]]})
    make_xlsx(src / "c.xlsx", {"S1": [["z"]]})
    make_pptx(src / "d.pptx", [("表紙", [], None)])
    (src / "old.doc").write_bytes(b"legacy")
    return src


# 期待1〜3: SCR-01/02
def test_version_and_help() -> None:
    assert runner.invoke(app, ["--version"]).exit_code == 0
    result = runner.invoke(app, ["convert", "--help"])
    assert result.exit_code == 0
    assert "Excel" in result.output


# 期待6〜9: SCR-04
def test_summary_contents(tmp_path: Path) -> None:
    src = inputs(tmp_path)
    out = tmp_path / "out"
    result = runner.invoke(app, ["convert", str(src), "-o", str(out)])
    assert "変換結果:" in result.output
    assert "出力ファイル:" in result.output
    assert "出力先:" in result.output


def test_output_count_differs_from_input_count(tmp_path: Path) -> None:
    src = inputs(tmp_path)
    out = tmp_path / "out"
    runner.invoke(app, ["convert", str(src), "-o", str(out)])
    files = sorted(p.name for p in out.iterdir())
    # docx 1 + xlsx 2*2 + pptx 1 = 6
    assert len(files) == 6
    assert "b.table.md" in files
    assert "b.grid.md" in files


# 期待13〜15: 終了コード
def test_exit_codes(tmp_path: Path) -> None:
    src = inputs(tmp_path)
    out = tmp_path / "out"
    # ディレクトリ探索で見つかった非対応形式は「スキップ」であり失敗ではない
    # (P002 §9.3)。よって全件成功で 0。
    result = runner.invoke(app, ["convert", str(src), "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert "スキップ 1 件" in result.output
    # 実行前異常は 2
    assert runner.invoke(app, ["convert", str(tmp_path / "none")]).exit_code == 2


def test_explicit_legacy_file_is_reported(tmp_path: Path) -> None:
    """.doc を明示指定した場合は、非対応である旨が案内される。"""
    src = inputs(tmp_path)
    result = runner.invoke(app, ["convert", str(src / "old.doc")])
    assert result.exit_code == 2
    assert ".doc" in result.output


def test_all_success_exit_zero(tmp_path: Path) -> None:
    src = tmp_path / "in"
    src.mkdir()
    make_docx(src / "a.docx", [("p", "本文")])
    result = runner.invoke(app, ["convert", str(src), "-o", str(tmp_path / "out")])
    assert result.exit_code == 0


# 期待16〜19: SCR-05
def test_inspect_columns(tmp_path: Path) -> None:
    src = inputs(tmp_path)
    result = runner.invoke(app, ["inspect", str(src)])
    assert result.exit_code == 0
    for column in ("形式", "図形", "領域", "数式"):
        assert column in result.output


def test_inspect_json_excel_vs_word(tmp_path: Path) -> None:
    src = inputs(tmp_path)
    result = runner.invoke(app, ["inspect", str(src), "--json"])
    payload = json.loads(result.output)
    excel = next(p for p in payload if p["path"].endswith("b.xlsx"))
    word = next(p for p in payload if p["path"].endswith("a.docx"))
    assert excel["table_region_count"] is not None
    assert word["table_region_count"] is None
    assert word["formula_without_cache_count"] is None


# 期待20〜22: SCR-06
def test_error_screen(tmp_path: Path) -> None:
    result = runner.invoke(app, ["convert", str(tmp_path / "none")])
    assert "エラー" in result.output
    assert "対処" in result.output
    assert "Traceback" not in result.output


# 期待23〜25: SCR-07
def test_stdout_is_markdown_only(tmp_path: Path) -> None:
    src = inputs(tmp_path)
    result = runner.invoke(app, ["convert", str(src / "a.docx"), "--stdout"])
    assert result.exit_code == 0
    assert "変換結果:" not in result.output


def test_stdout_excel_requires_single_mode(tmp_path: Path) -> None:
    src = inputs(tmp_path)
    result = runner.invoke(app, ["convert", str(src / "b.xlsx"), "--stdout"])
    assert result.exit_code == 2
    assert "--excel-modes" in result.output


# 期待26〜28: 設定ファイル
def test_config_file_and_cli_precedence(tmp_path: Path) -> None:
    src = inputs(tmp_path)
    config = tmp_path / "cfg.toml"
    config.write_text('[excel]\nmodes = "table"\n', encoding="utf-8")
    out = tmp_path / "out"
    runner.invoke(app, ["convert", str(src / "b.xlsx"), "-o", str(out), "-c", str(config)])
    assert (out / "b.table.md").is_file()
    assert not (out / "b.grid.md").exists()

    out2 = tmp_path / "out2"
    runner.invoke(
        app,
        [
            "convert",
            str(src / "b.xlsx"),
            "-o",
            str(out2),
            "-c",
            str(config),
            "--excel-modes",
            "grid",
        ],
    )
    assert (out2 / "b.grid.md").is_file()
    assert not (out2 / "b.table.md").exists()


def test_unknown_config_key(tmp_path: Path) -> None:
    src = inputs(tmp_path)
    config = tmp_path / "cfg.toml"
    config.write_text("[excel]\nmispelled = 1\n", encoding="utf-8")
    result = runner.invoke(app, ["convert", str(src), "-c", str(config)])
    assert result.exit_code == 2
    assert "mispelled" in result.output


# 期待29: 既存時の挙動
def test_on_exists_skip(tmp_path: Path) -> None:
    src = inputs(tmp_path)
    out = tmp_path / "out"
    runner.invoke(app, ["convert", str(src / "b.xlsx"), "-o", str(out)])
    result = runner.invoke(app, ["convert", str(src / "b.xlsx"), "-o", str(out)])
    assert "スキップ 2 件" in result.output


# 期待30: 並列
def test_parallel_matches_sequential(tmp_path: Path) -> None:
    src = inputs(tmp_path)
    out1, out2 = tmp_path / "o1", tmp_path / "o2"
    runner.invoke(app, ["convert", str(src), "-o", str(out1), "-j", "1"])
    runner.invoke(app, ["convert", str(src), "-o", str(out2), "-j", "2"])
    names1 = sorted(p.name for p in out1.iterdir())
    names2 = sorted(p.name for p in out2.iterdir())
    assert names1 == names2


# 期待32: 日本語
def test_japanese_paths(tmp_path: Path) -> None:
    src = tmp_path / "入力"
    src.mkdir()
    make_xlsx(src / "体制図.xlsx", {"組織": [["部門"]]})
    out = tmp_path / "出力"
    result = runner.invoke(app, ["convert", str(src), "-o", str(out)])
    assert result.exit_code == 0
    assert (out / "体制図.table.md").is_file()


def test_subprocess_entrypoint() -> None:
    """実際のプロセスとして起動できること (エントリポイントの確認)。"""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, "-m", "office2ragknowledge.cli.main", "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )
    assert proc.returncode == 0
    assert "office2rag" in proc.stdout
