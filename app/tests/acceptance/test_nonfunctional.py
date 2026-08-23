"""A004 受け入れテスト: 非機能要件の検証。

冪等性・並列・互換性は **合否判定の対象**。
性能・メモリは **記録のみ** で合否判定に含めない (P001 §10, P006 §9)。
"""

from __future__ import annotations

import sys
import time
import tracemalloc
from pathlib import Path

import pytest

from office2ragknowledge import (
    BatchOptions,
    ConvertOptions,
    ExcelModes,
    ExcelOptions,
    ImageMode,
    convert_batch,
    convert_file,
)
from office2ragknowledge.render.frontmatter import strip_front_matter
from tests.helpers.make_office import make_docx, make_pptx, make_xlsx


def bodies(path: Path, options: ConvertOptions | None = None) -> list[str]:
    result = convert_file(path, options or ConvertOptions())
    return [strip_front_matter(o.markdown) for o in result.outputs]


@pytest.fixture
def samples(tmp_path: Path) -> list[Path]:
    return [
        make_docx(tmp_path / "a.docx", [("h1", "章"), ("p", "本文"), ("bullet", "項目")]),
        make_xlsx(
            tmp_path / "b.xlsx",
            {"表": [["h", "i"], ["1", "2"]], "方眼": [["あ", "い"], [], ["う"]]},
        ),
        make_pptx(tmp_path / "c.pptx", [("表紙", ["要点"], "ノート")]),
    ]


# ============================================================
# 冪等性 (REQ-NF-018) — 合否判定の対象
# ============================================================


# 期待1/2: 3形式で2回変換して一致 (Excel は2出力とも)
def test_idempotent_all_formats(samples: list[Path]) -> None:
    for path in samples:
        first = bodies(path)
        second = bodies(path)
        assert first == second, f"{path.name} の出力が2回で異なります"


# 期待3: ディレクトリ入力の処理順が一致
def test_scan_order_is_stable(samples: list[Path], tmp_path: Path) -> None:
    src = samples[0].parent
    a = convert_batch([src], BatchOptions(output_dir=tmp_path / "o1"))
    b = convert_batch([src], BatchOptions(output_dir=tmp_path / "o2"))
    assert [p.name for p in a.succeeded] == [p.name for p in b.succeeded]


# 期待4: --jobs 4 と --jobs 1 で出力が完全一致
def test_parallel_output_matches_sequential(samples: list[Path], tmp_path: Path) -> None:
    src = samples[0].parent
    o1, o4 = tmp_path / "j1", tmp_path / "j4"
    convert_batch([src], BatchOptions(output_dir=o1, jobs=1))
    convert_batch([src], BatchOptions(output_dir=o4, jobs=4))
    files1 = sorted(o1.iterdir())
    files4 = sorted(o4.iterdir())
    assert [p.name for p in files1] == [p.name for p in files4]
    for a, b in zip(files1, files4, strict=True):
        assert strip_front_matter(a.read_text(encoding="utf-8")) == strip_front_matter(
            b.read_text(encoding="utf-8")
        ), f"{a.name} の内容が並列度によって異なります"


# 期待6: 警告の順序が一致
def test_warning_order_is_stable(tmp_path: Path) -> None:
    path = make_xlsx(
        tmp_path / "w.xlsx",
        {"A": [["v"], ["=A1*2"]], "B": [["v"], ["=A1*3"]]},
    )
    first = convert_file(path).warnings
    second = convert_file(path).warnings
    assert first == second


# 期待7: front matter のキー順が固定
def test_front_matter_key_order_is_stable(samples: list[Path]) -> None:
    def keys(markdown: str) -> list[str]:
        out = []
        for line in markdown.splitlines():
            if line == "---":
                if out:
                    break
                continue
            if line.startswith(" "):
                continue
            out.append(line.split(":", 1)[0])
        return out

    for path in samples:
        result = convert_file(path)
        first = keys(result.outputs[0].markdown)
        second = keys(convert_file(path).outputs[0].markdown)
        assert first == second


# ============================================================
# 並列実行 (REQ-NF-015) — 合否判定の対象
# ============================================================


# 期待8/9: jobs=1 と jobs=4 の双方で正常終了
def test_jobs_one_and_four(samples: list[Path], tmp_path: Path) -> None:
    src = samples[0].parent
    for jobs, name in ((1, "s1"), (4, "s4")):
        result = convert_batch([src], BatchOptions(output_dir=tmp_path / name, jobs=jobs))
        assert len(result.failures) == 0, f"jobs={jobs} で失敗しました"
        assert len(result.succeeded) == 3


# 期待11: 並列時も1件の失敗が他を妨げない
def test_parallel_failure_isolation(samples: list[Path], tmp_path: Path) -> None:
    src = samples[0].parent
    (src / "broken.docx").write_bytes(b"PK\x03\x04broken")
    result = convert_batch([src], BatchOptions(output_dir=tmp_path / "out", jobs=4))
    assert len(result.succeeded) == 3
    assert len(result.failures) == 1


# 期待12: 並列でも進捗は入力単位
def test_parallel_progress_counts_inputs(samples: list[Path], tmp_path: Path) -> None:
    src = samples[0].parent
    calls: list[int] = []
    convert_batch(
        [src],
        BatchOptions(output_dir=tmp_path / "out", jobs=4),
        lambda done, total, name: calls.append(total),
    )
    assert calls and set(calls) == {3}


# ============================================================
# 互換性 (REQ-NF-017/019) — 合否判定の対象
# ============================================================


# 期待13: 開発環境の Python で全機能が動く
def test_runs_on_current_python(samples: list[Path]) -> None:
    assert sys.version_info >= (3, 11), "対応下限を下回る Python です"
    for path in samples:
        assert bodies(path)


# 期待14: Python 3.11 — 実行環境が無いため NOT RUN
@pytest.mark.skipif(
    sys.version_info[:2] != (3, 11),
    reason="Python 3.11 の実行環境が本環境に無いため NOT RUN (P005 §7 R6)",
)
def test_runs_on_python_311(samples: list[Path]) -> None:
    for path in samples:
        assert bodies(path)


# 期待15: 外部バイナリを必要としない
def test_no_external_binaries(samples: list[Path]) -> None:
    """依存は Python パッケージのみ。外部プロセスを起動しない。"""
    import subprocess

    original = subprocess.run
    calls: list[object] = []

    def tracking(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        calls.append(args)
        return original(*args, **kwargs)  # type: ignore[arg-type]

    subprocess.run = tracking  # type: ignore[assignment]
    try:
        for path in samples:
            bodies(path)
    finally:
        subprocess.run = original  # type: ignore[assignment]
    assert calls == [], "外部プロセスが起動されました"


# ============================================================
# 性能・メモリ — 記録のみ (合否判定に含めない)
# ============================================================


def _make_large_excel(path: Path, sheets: int = 10, rows: int = 1000) -> Path:
    data = {f"S{i}": [[f"c{c}" for c in range(5)] for _ in range(rows)] for i in range(sheets)}
    return make_xlsx(path, data)


@pytest.mark.perf
def test_perf_excel_dual_output(tmp_path: Path) -> None:
    """REQ-NF-001: Excel 10シート×1000行を二重出力込みで10秒以内 (記録のみ)。"""
    path = _make_large_excel(tmp_path / "big.xlsx")
    start = time.perf_counter()
    convert_file(path)
    elapsed = time.perf_counter() - start
    print(f"\n[perf] Excel 10シート×1000行 (二重出力): {elapsed:.2f} 秒 (目標 10 秒以内)")


@pytest.mark.perf
def test_perf_dual_vs_single(tmp_path: Path) -> None:
    """REQ-F-068: 二重出力が単一モードの2倍を要しないこと (記録のみ)。"""
    path = _make_large_excel(tmp_path / "big.xlsx", sheets=5, rows=500)
    single = ConvertOptions(excel=ExcelOptions(modes=ExcelModes.TABLE))

    start = time.perf_counter()
    convert_file(path, single)
    t_single = time.perf_counter() - start

    start = time.perf_counter()
    convert_file(path)
    t_both = time.perf_counter() - start

    ratio = t_both / t_single if t_single else 0
    print(
        f"\n[perf] 単一モード {t_single:.2f} 秒 / 二重出力 {t_both:.2f} 秒 "
        f"(比 {ratio:.2f} 倍。目標 2 倍未満)"
    )


@pytest.mark.perf
def test_perf_memory(tmp_path: Path) -> None:
    """REQ-NF-003: メモリ使用量 (記録のみ)。"""
    path = _make_large_excel(tmp_path / "big.xlsx")
    tracemalloc.start()
    convert_file(path, ConvertOptions(images=ImageMode.NONE))
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"\n[perf] ピークメモリ: {peak / 1024 / 1024:.1f} MB (目標 2048 MB 以内)")


@pytest.mark.perf
def test_perf_batch_degradation(tmp_path: Path) -> None:
    """REQ-NF-002: バッチでの1ファイル平均が単独の1.5倍以内 (記録のみ)。"""
    src = tmp_path / "many"
    src.mkdir()
    for i in range(20):
        make_xlsx(src / f"f{i}.xlsx", {"S": [[f"v{r}" for r in range(5)] for _ in range(50)]})
    single_file = next(src.iterdir())

    start = time.perf_counter()
    convert_file(single_file)
    t_single = time.perf_counter() - start

    start = time.perf_counter()
    convert_batch([src], BatchOptions(output_dir=tmp_path / "out", jobs=1))
    t_batch = (time.perf_counter() - start) / 20

    ratio = t_batch / t_single if t_single else 0
    print(
        f"\n[perf] 単独 {t_single * 1000:.0f} ms / バッチ平均 {t_batch * 1000:.0f} ms "
        f"(比 {ratio:.2f} 倍。目標 1.5 倍以内)"
    )
