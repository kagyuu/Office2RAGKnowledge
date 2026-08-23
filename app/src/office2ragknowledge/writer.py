"""変換結果のファイル書き出し (API-06)。

**出力ファイルごとに個別に ``on_exists`` を判定する** (P002 §5.2)。
Excel の二重出力で片方だけが既存の場合、その片方のみスキップし、もう片方は
書き出す。「1つでも既存なら全部スキップ」としてはならない。

書き込みは一時ファイルへ書いてから原子的に置換する。変換途中の中断で壊れた
Markdown が正しいファイル名で残ると、RAG が不完全な文書を取り込むため。
"""

from __future__ import annotations

import os
from pathlib import Path

from .errors import OutputError
from .models import ConversionResult, ImageMode, OnExists, WrittenFiles

__all__ = ["write_result"]


def write_result(
    result: ConversionResult,
    out_dir: Path | str,
    on_exists: OnExists = OnExists.SKIP,
    images: ImageMode = ImageMode.NONE,
) -> WrittenFiles:
    """変換結果を Markdown (と画像) として書き出す。

    Raises:
        OutputError: 出力先に書き込めない、または ``on_exists=FAIL`` で既存
    """
    directory = Path(out_dir)
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OutputError(f"出力先に書き込めません: {directory}", path=directory) from exc

    stem = result.source_path.stem
    written: list[Path] = []
    skipped: list[Path] = []

    for output in result.outputs:
        target = directory / f"{stem}{output.filename_suffix}"
        if target.exists():
            if on_exists is OnExists.SKIP:
                skipped.append(target)
                continue
            if on_exists is OnExists.FAIL:
                raise OutputError(f"出力先に同名のファイルが既に存在します: {target}", path=target)
        _atomic_write(target, output.markdown)
        written.append(target)

    image_paths: list[Path] = []
    # 画像は outputs のループの外で1回だけ書き出す (REQ-F-069)
    if images is ImageMode.EXTRACT and result.images:
        assets = directory / f"{stem}_assets"
        try:
            assets.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise OutputError(f"出力先に書き込めません: {assets}", path=assets) from exc
        for image in result.images:
            target = assets / f"{image.index:04d}.{image.extension}"
            if target.exists():
                if on_exists is OnExists.SKIP:
                    skipped.append(target)
                    continue
                if on_exists is OnExists.FAIL:
                    raise OutputError(
                        f"出力先に同名のファイルが既に存在します: {target}", path=target
                    )
            _atomic_write_bytes(target, image.data)
            image_paths.append(target)

    return WrittenFiles(
        markdown_paths=tuple(written),
        image_paths=tuple(image_paths),
        skipped_paths=tuple(skipped),
    )


def _atomic_write(target: Path, text: str) -> None:
    """一時ファイルへ書いてから原子的に置換する。"""
    tmp = target.with_name(f"{target.name}.tmp{os.getpid()}")
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as fp:
            fp.write(text)
        os.replace(tmp, target)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise OutputError(f"出力先に書き込めません: {target}", path=target) from exc


def _atomic_write_bytes(target: Path, data: bytes) -> None:
    tmp = target.with_name(f"{target.name}.tmp{os.getpid()}")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, target)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise OutputError(f"出力先に書き込めません: {target}", path=target) from exc
