"""YAML front matter の生成 (P002 §5.3 / REQ-F-007, REQ-F-066)。

**キーの出現順は P001 §7.1 の記載順に固定する** (冪等性のため)。
値が取得できない項目はキーごと省略し、``null`` を出力しない。

YAML ライブラリを使わず自前で組み立てる。依存を増やさず、キー順と省略の制御を
完全に握るため。
"""

from __future__ import annotations

from datetime import datetime

from ..models import DocumentMeta, OutputMode

__all__ = ["render_front_matter", "strip_front_matter"]


def _quote(value: str) -> str:
    """YAML のダブルクォート文字列にする。"""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    escaped = escaped.replace("\n", "\\n").replace("\r", "")
    return f'"{escaped}"'


def _iso(value: datetime) -> str:
    return value.isoformat()


def render_front_matter(meta: DocumentMeta, mode: OutputMode | None) -> str:
    """front matter を組み立てて返す。末尾は改行で終わる。

    Args:
        meta: 出力するメタデータ
        mode: Excel の出力モード。``None`` なら ``output_mode`` キーを省略する
    """
    lines: list[str] = ["---"]

    lines.append(f"source_file: {_quote(meta.source_file)}")
    lines.append(f"source_path: {_quote(meta.source_path)}")
    lines.append(f"source_format: {_quote(str(meta.source_format))}")
    if meta.pdf_structure is not None:
        lines.append(f"pdf_structure: {_quote(meta.pdf_structure)}")
    if mode is not None:
        lines.append(f"output_mode: {_quote(str(mode))}")
    lines.append(f"source_size_bytes: {meta.source_size_bytes}")
    if meta.source_sha256:
        lines.append(f"source_sha256: {_quote(meta.source_sha256)}")
    if meta.title:
        lines.append(f"title: {_quote(meta.title)}")
    if meta.author:
        lines.append(f"author: {_quote(meta.author)}")
    if meta.created_at is not None:
        lines.append(f"created_at: {_quote(_iso(meta.created_at))}")
    if meta.modified_at is not None:
        lines.append(f"modified_at: {_quote(_iso(meta.modified_at))}")
    lines.append(f"converted_at: {_quote(_iso(meta.converted_at))}")
    lines.append(f"converter: {_quote(meta.converter)}")

    if meta.stats:
        lines.append("stats:")
        for key, value in meta.stats.items():
            lines.append(f"  {key}: {value}")

    if meta.warnings:
        lines.append("warnings:")
        for warning in meta.warnings:
            lines.append(f"  - {_quote(warning)}")

    lines.append("---")
    return "\n".join(lines) + "\n"


def strip_front_matter(markdown: str) -> str:
    """先頭の front matter ブロックを除去して本文を返す。

    front matter を持たない文字列に適用しても壊れない。冪等性の比較で
    ``converted_at`` を回避するために用いる。
    """
    if not markdown.startswith("---\n"):
        return markdown
    end = markdown.find("\n---\n", 3)
    if end == -1:
        return markdown
    return markdown[end + len("\n---\n") :].lstrip("\n")
