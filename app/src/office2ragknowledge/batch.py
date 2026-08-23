"""複数ファイルの変換 (API-03)。

**個々のファイルの変換失敗では例外を送出しない** (REQ-F-006)。失敗は
``BatchResult.failures`` に記録して処理を継続する。

並列は **ファイル単位** とする (ADR-005)。Excel の二重出力を分割すると、同じ
中間表現を2プロセスに渡すことになり解析が二重になる。

Windows は ``fork`` を持たず ``spawn`` を使うため、ワーカー関数は
**モジュールのトップレベル** に定義しなければ pickle できない。
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from .convert import convert_file
from .detect import SUPPORTED_EXTENSIONS
from .errors import Office2RagError, OutputError
from .models import BatchOptions, BatchResult, FailureInfo
from .writer import write_result

__all__ = ["convert_batch", "scan_inputs"]

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, str], None]


@dataclass(frozen=True, slots=True)
class _WorkerResult:
    """ワーカーからの戻り値。

    **``Document`` や ``ConversionResult`` を返さない。** 中間表現は大きく、
    pickle のコストが変換自体を上回るため (ADR-005)。
    """

    path: str
    ok: bool
    written: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    code: str = ""
    message: str = ""


def scan_inputs(
    paths: Sequence[Path | str], *, recursive: bool
) -> tuple[list[Path], list[tuple[Path, str]]]:
    """入力パスを探索して、対象ファイルとスキップを返す。

    **結果はパス文字列でソートする** (REQ-NF-018: 2回の実行で順序が一致する)。
    """
    targets: list[Path] = []
    skipped: list[tuple[Path, str]] = []
    seen: set[Path] = set()

    def consider(file: Path) -> None:
        resolved = file.resolve()
        if resolved in seen:
            return
        seen.add(resolved)
        if file.suffix.lower() in SUPPORTED_EXTENSIONS:
            targets.append(file)
        else:
            skipped.append((file, "対応形式ではありません"))

    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            pattern = "**/*" if recursive else "*"
            for child in sorted(path.glob(pattern)):
                if child.is_file():
                    consider(child)
        elif path.is_file():
            consider(path)

    targets.sort(key=lambda p: str(p))
    skipped.sort(key=lambda item: str(item[0]))
    return targets, skipped


def _worker_convert(args: tuple[str, BatchOptions, str | None]) -> _WorkerResult:
    """1ファイルを変換して書き出す。**トップレベル関数であること** (spawn 対応)。"""
    path_str, options, out_dir = args
    path = Path(path_str)
    try:
        result = convert_file(path, options.convert)
        target_dir = Path(out_dir) if out_dir else path.parent
        written = write_result(result, target_dir, options.on_exists, options.convert.images)
        return _WorkerResult(
            path=path_str,
            ok=True,
            written=tuple(str(p) for p in written.markdown_paths),
            skipped=tuple(str(p) for p in written.skipped_paths),
            warnings=tuple(result.warnings),
        )
    except Office2RagError as exc:
        return _WorkerResult(path=path_str, ok=False, code=exc.code, message=exc.message)
    except (OSError, ValueError) as exc:
        return _WorkerResult(
            path=path_str, ok=False, code="E-007", message=f"変換に失敗しました: {exc}"
        )


def convert_batch(
    paths: Sequence[Path | str],
    options: BatchOptions | None = None,
    on_progress: ProgressCallback | None = None,
    pre_skipped: Sequence[tuple[Path, str]] = (),
) -> BatchResult:
    """複数ファイル/ディレクトリを変換する。

    Args:
        paths: ファイルまたはディレクトリ
        options: バッチ設定
        on_progress: 進捗コールバック (完了数, 全数, ファイル名)
        pre_skipped: **呼び出し元が既に探索を済ませている場合の、スキップした
            ファイルと理由。** CLI は事前検証のために自分で探索するため、
            そこで判明したスキップをここへ引き継がないと結果サマリから
            欠落する (REQ-F-094)。省略時は自前の探索結果のみを用いる。

    Raises:
        OutputError: 出力先を作成できない等の実行前異常。この場合1件も処理しない。
    """
    opts = options or BatchOptions()
    started = time.perf_counter()

    targets, skipped = scan_inputs(paths, recursive=opts.recursive)

    # 事前検証: 出力先に書けないなら1件も処理しない
    if opts.output_dir is not None:
        try:
            opts.output_dir.mkdir(parents=True, exist_ok=True)
            probe = opts.output_dir / f".o2rk-probe-{os.getpid()}"
            probe.write_text("", encoding="utf-8")
            probe.unlink()
        except OSError as exc:
            raise OutputError(
                f"出力先に書き込めません: {opts.output_dir}", path=opts.output_dir
            ) from exc

    out_dir = str(opts.output_dir) if opts.output_dir else None
    jobs = opts.jobs if opts.jobs is not None else (os.cpu_count() or 1)
    total = len(targets)
    results: dict[str, _WorkerResult] = {}

    logger.info("バッチ変換を開始します", extra={"event": "batch.start", "detail": total})

    work = [(str(p), opts, out_dir) for p in targets]
    if jobs <= 1 or total <= 1:
        # プールを作らず逐次実行する (プロセス起動コストの回避とデバッグの容易さ)
        for index, item in enumerate(work, start=1):
            outcome = _worker_convert(item)
            results[outcome.path] = outcome
            if on_progress is not None:
                on_progress(index, total, Path(outcome.path).name)
    else:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            futures = {pool.submit(_worker_convert, item): item[0] for item in work}
            for index, future in enumerate(as_completed(futures), start=1):
                outcome = future.result()
                results[outcome.path] = outcome
                if on_progress is not None:
                    on_progress(index, total, Path(outcome.path).name)

    # 完了順ではなく **入力順** に並べ替える (REQ-NF-018)
    succeeded: list[Path] = []
    failures: list[FailureInfo] = []
    warnings: list[tuple[Path, str]] = []
    written_files: list[Path] = []
    skipped_out: list[tuple[Path, str]] = list(pre_skipped) + list(skipped)

    for target in targets:
        found = results.get(str(target))
        if found is None:
            continue
        outcome = found
        if outcome.ok:
            succeeded.append(target)
            written_files.extend(Path(p) for p in outcome.written)
            skipped_out.extend((Path(p), "出力先に既存") for p in outcome.skipped)
            warnings.extend((target, w) for w in outcome.warnings)
        else:
            failures.append(FailureInfo(path=target, code=outcome.code, message=outcome.message))

    elapsed = time.perf_counter() - started
    logger.info(
        "バッチ変換が完了しました",
        extra={"event": "batch.done", "detail": len(succeeded)},
    )
    return BatchResult(
        succeeded=tuple(succeeded),
        skipped=tuple(skipped_out),
        failures=tuple(failures),
        warnings=tuple(warnings),
        written_files=tuple(written_files),
        elapsed_seconds=elapsed,
    )
