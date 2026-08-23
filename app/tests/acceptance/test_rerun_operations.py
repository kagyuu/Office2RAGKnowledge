"""A003 受け入れテスト: 再実行と出力先の運用 (観点 O-01・O-02)。

**同一の出力先に対する2回目の実行**を検証する。単体テスト・結合テストは各テスト
ごとに新しい一時ディレクトリを使うため常に「初回実行」となり、この観点を検出
できない。本テストが唯一の検出手段である (P006 §2.3)。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from office2ragknowledge import (
    BatchOptions,
    ConvertOptions,
    ImageMode,
    OnExists,
    convert_batch,
)
from office2ragknowledge.cli.main import app
from office2ragknowledge.render.frontmatter import strip_front_matter
from tests.helpers.make_office import make_docx, make_pptx, make_xlsx

runner = CliRunner()


@pytest.fixture
def workspace(tmp_path: Path) -> tuple[Path, Path]:
    """入力と、**繰り返し使う** 出力先を用意する。"""
    src = tmp_path / "in"
    src.mkdir()
    make_docx(src / "規程.docx", [("p", "本文")])
    make_pptx(src / "会議.pptx", [("表紙", [], None)])
    make_xlsx(src / "売上.xlsx", {"S1": [["月", "額"], [4, 100]]})
    make_xlsx(src / "名簿.xlsx", {"S1": [["氏名"], ["山田"]]})
    out = tmp_path / "out"
    return src, out


def run(src: Path, out: Path, *extra: str) -> object:
    return runner.invoke(app, ["convert", str(src), "-o", str(out), *extra])


def snapshot(out: Path) -> dict[str, str]:
    return {
        p.name: strip_front_matter(p.read_text(encoding="utf-8"))
        for p in sorted(out.iterdir())
        if p.is_file()
    }


# ============================================================
# O-01: 同一出力先への2回目の実行
# ============================================================


# 期待1: 1回目で全ファイル生成
def test_first_run_creates_all(workspace: tuple[Path, Path]) -> None:
    src, out = workspace
    result = run(src, out)
    assert result.exit_code == 0  # type: ignore[attr-defined]
    # Word 1 + PPT 1 + Excel 2*2 = 6
    assert len(list(out.iterdir())) == 6


# 期待2〜4: 2回目 (skip) で全件スキップ・内容が変わらない
def test_second_run_skips_all(workspace: tuple[Path, Path]) -> None:
    src, out = workspace
    run(src, out)
    before = snapshot(out)

    result = run(src, out, "--on-exists", "skip")
    assert result.exit_code == 0  # type: ignore[attr-defined]
    assert "スキップ 6 件" in result.output  # type: ignore[attr-defined]
    assert snapshot(out) == before, "スキップされたのに内容が変わっています"


# 期待5/6: overwrite で上書きされ、内容が一致する (冪等性)
def test_overwrite_produces_identical_content(workspace: tuple[Path, Path]) -> None:
    src, out = workspace
    run(src, out)
    before = snapshot(out)

    result = run(src, out, "--on-exists", "overwrite")
    assert result.exit_code == 0  # type: ignore[attr-defined]
    assert snapshot(out) == before, "上書き後の内容が1回目と異なります (冪等性違反)"


# 期待7: fail でエラーになる
def test_fail_mode_reports_error(workspace: tuple[Path, Path]) -> None:
    src, out = workspace
    run(src, out)
    result = run(src, out, "--on-exists", "fail")
    assert result.exit_code == 1  # type: ignore[attr-defined]


# 期待8/9: 何度繰り返してもクラッシュしない
def test_repeated_runs_are_stable(workspace: tuple[Path, Path]) -> None:
    src, out = workspace
    run(src, out)
    baseline = snapshot(out)
    for _ in range(3):
        result = run(src, out, "--on-exists", "overwrite")
        assert result.exit_code == 0  # type: ignore[attr-defined]
    assert snapshot(out) == baseline


# ============================================================
# O-02: Excel の二重出力で片方だけが既存の場合
# ============================================================


# 期待10〜12: .table.md のみ残して再実行 → grid だけ書かれる
def test_partial_existing_table_only(workspace: tuple[Path, Path]) -> None:
    src, out = workspace
    run(src, out)
    original_grid = (out / "売上.grid.md").read_text(encoding="utf-8")
    (out / "売上.grid.md").unlink()

    result = run(src, out, "--on-exists", "skip")
    assert result.exit_code == 0  # type: ignore[attr-defined]
    assert (out / "売上.grid.md").is_file(), (
        "片方が既存であるだけで、もう片方まで書き出されませんでした"
    )
    assert (out / "売上.table.md").is_file()
    assert strip_front_matter(
        (out / "売上.grid.md").read_text(encoding="utf-8")
    ) == strip_front_matter(original_grid)


# 期待13: 逆も成立する
def test_partial_existing_grid_only(workspace: tuple[Path, Path]) -> None:
    src, out = workspace
    run(src, out)
    (out / "売上.table.md").unlink()
    run(src, out, "--on-exists", "skip")
    assert (out / "売上.table.md").is_file()


# 期待14: 「片方が既存なら両方スキップ」になっていない
def test_not_all_or_nothing(workspace: tuple[Path, Path]) -> None:
    src, out = workspace
    result_first = convert_batch([src], BatchOptions(output_dir=out))
    assert len(result_first.written_files) == 6

    (out / "売上.grid.md").unlink()
    (out / "名簿.table.md").unlink()
    result_second = convert_batch([src], BatchOptions(output_dir=out, on_exists=OnExists.SKIP))
    written = sorted(p.name for p in result_second.written_files)
    assert written == ["名簿.table.md", "売上.grid.md"]


# ============================================================
# 画像の再実行 / 中断耐性
# ============================================================


# 期待16: 画像抽出モードでも2回の実行で結果が一致する
def test_image_mode_is_stable_across_runs(workspace: tuple[Path, Path]) -> None:
    src, out = workspace
    options = ConvertOptions(images=ImageMode.EXTRACT)
    first = convert_batch([src], BatchOptions(output_dir=out, convert=options))
    second = convert_batch([src], BatchOptions(output_dir=out.parent / "out2", convert=options))
    assert sorted(p.name for p in first.written_files) == sorted(
        p.name for p in second.written_files
    )


# 期待18: 一時ファイルが残らない
def test_no_temp_files_remain(workspace: tuple[Path, Path]) -> None:
    src, out = workspace
    run(src, out)
    run(src, out, "--on-exists", "overwrite")
    leftovers = [p.name for p in out.iterdir() if ".tmp" in p.name]
    assert leftovers == [], f"一時ファイルが残っています: {leftovers}"


# 期待19: 余計なファイルが作られない
def test_no_unexpected_files(workspace: tuple[Path, Path]) -> None:
    src, out = workspace
    run(src, out)
    names = sorted(p.name for p in out.iterdir())
    assert names == [
        "会議.md",
        "名簿.grid.md",
        "名簿.table.md",
        "売上.grid.md",
        "売上.table.md",
        "規程.md",
    ]
