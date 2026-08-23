"""U005-T2 の単体テスト: convert_batch。"""

from __future__ import annotations

from pathlib import Path

from office2ragknowledge import BatchOptions, ConvertOptions, convert_batch
from office2ragknowledge.models import ExcelModes, ExcelOptions
from tests.helpers.make_office import make_docx, make_pptx, make_xlsx


def make_inputs(root: Path) -> Path:
    src = root / "in"
    (src / "sub").mkdir(parents=True)
    make_docx(src / "a.docx", [("p", "本文")])
    make_xlsx(src / "b.xlsx", {"S1": [["x"]]})
    make_pptx(src / "sub" / "c.pptx", [("表紙", [], None)])
    (src / "note.txt").write_text("対象外", encoding="utf-8")
    return src


def opts(root: Path, **kw: object) -> BatchOptions:
    return BatchOptions(output_dir=root / "out", **kw)  # type: ignore[arg-type]


# ケース1/2: 複数ファイル・ディレクトリ直下
def test_directory_non_recursive(tmp_path: Path) -> None:
    src = make_inputs(tmp_path)
    result = convert_batch([src], opts(tmp_path))
    names = sorted(p.name for p in result.succeeded)
    assert names == ["a.docx", "b.xlsx"]


# ケース3/4: 再帰
def test_recursive(tmp_path: Path) -> None:
    src = make_inputs(tmp_path)
    result = convert_batch([src], opts(tmp_path, recursive=True))
    names = sorted(p.name for p in result.succeeded)
    assert names == ["a.docx", "b.xlsx", "c.pptx"]


# ケース5: 対応しない拡張子がスキップに計上される
def test_unsupported_is_skipped(tmp_path: Path) -> None:
    src = make_inputs(tmp_path)
    result = convert_batch([src], opts(tmp_path))
    assert any(p.name == "note.txt" for p, _ in result.skipped)


# ケース6: 1件失敗しても他が処理される
def test_failure_does_not_stop_batch(tmp_path: Path) -> None:
    src = make_inputs(tmp_path)
    (src / "broken.docx").write_bytes(b"PK\x03\x04broken")
    result = convert_batch([src], opts(tmp_path))
    assert len(result.succeeded) == 2
    assert len(result.failures) == 1
    assert result.exit_code == 1


# ケース7: written_files が入力件数と異なる (Excel の二重出力)
def test_written_files_differ_from_input_count(tmp_path: Path) -> None:
    src = make_inputs(tmp_path)
    result = convert_batch([src], opts(tmp_path))
    assert len(result.succeeded) == 2
    assert len(result.written_files) == 3  # docx 1 + xlsx 2


# ケース8: on_progress が入力件数だけ呼ばれる
def test_progress_counts_inputs(tmp_path: Path) -> None:
    src = make_inputs(tmp_path)
    calls: list[tuple[int, int, str]] = []
    convert_batch([src], opts(tmp_path), lambda d, t, n: calls.append((d, t, n)))
    assert len(calls) == 2
    assert calls[-1][1] == 2


# ケース9: jobs=1 と jobs=2 で順序が一致
def test_job_count_does_not_change_order(tmp_path: Path) -> None:
    src = make_inputs(tmp_path)
    one = convert_batch([src], opts(tmp_path, recursive=True, jobs=1))
    two = convert_batch([src], BatchOptions(output_dir=tmp_path / "out2", recursive=True, jobs=2))
    assert [p.name for p in one.succeeded] == [p.name for p in two.succeeded]


# ケース10: 2回処理して順序が一致 (探索順の決定性)
def test_scan_order_is_deterministic(tmp_path: Path) -> None:
    src = make_inputs(tmp_path)
    first = convert_batch([src], opts(tmp_path, recursive=True))
    second = convert_batch([src], BatchOptions(output_dir=tmp_path / "out2", recursive=True))
    assert [p.name for p in first.succeeded] == [p.name for p in second.succeeded]


# ケース12: 重複したパスは1回だけ処理される
def test_duplicate_paths(tmp_path: Path) -> None:
    src = make_inputs(tmp_path)
    result = convert_batch([src / "a.docx", src / "a.docx"], opts(tmp_path))
    assert len(result.succeeded) == 1


# ケース13: jobs=2 で実際に並列実行される (Windows の spawn 対応)
def test_parallel_execution(tmp_path: Path) -> None:
    src = tmp_path / "in"
    src.mkdir()
    for i in range(4):
        make_xlsx(src / f"f{i}.xlsx", {"S1": [["v"]]})
    result = convert_batch([src], BatchOptions(output_dir=tmp_path / "out", jobs=2))
    assert len(result.succeeded) == 4
    assert len(result.failures) == 0


def test_excel_single_mode_writes_one_file(tmp_path: Path) -> None:
    src = tmp_path / "in"
    src.mkdir()
    make_xlsx(src / "b.xlsx", {"S1": [["x"]]})
    options = BatchOptions(
        output_dir=tmp_path / "out",
        convert=ConvertOptions(excel=ExcelOptions(modes=ExcelModes.GRID)),
    )
    result = convert_batch([src], options)
    assert len(result.written_files) == 1
    assert result.written_files[0].name == "b.grid.md"


# ============================================================
# F002: pre_skipped の引き継ぎ
# ============================================================


def test_pre_skipped_is_merged(tmp_path: Path) -> None:
    """呼び出し元が判明させたスキップが BatchResult に合流する。"""
    src = make_inputs(tmp_path)
    extra = [(src / "old.doc", "対応形式ではありません")]
    result = convert_batch([src / "a.docx"], opts(tmp_path), None, extra)
    names = sorted(p.name for p, _ in result.skipped)
    assert "old.doc" in names


def test_pre_skipped_default_keeps_behaviour(tmp_path: Path) -> None:
    """pre_skipped を渡さない場合の挙動は変わらない。"""
    src = make_inputs(tmp_path)
    result = convert_batch([src], opts(tmp_path))
    assert any(p.name == "note.txt" for p, _ in result.skipped)
