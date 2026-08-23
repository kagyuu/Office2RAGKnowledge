"""図形テキストブロックの描画 (REQ-F-038, REQ-F-039)。

3形式に共通の体裁である。Excel では表計算モード・方眼紙モードの両方で同一の
内容を同じ位置 (章の末尾) に出力する (REQ-F-035)。

**図形内の表は引用ブロックの外に出す。** CommonMark/GFM では引用内テーブルの
解釈が処理系によって割れ、RAG 側のパーサ次第で表が壊れるため (P002 §5.7)。
"""

from __future__ import annotations

from ..models import ShapeStyle, ShapeText, Table
from .escape import escape_cell, escape_line

__all__ = ["render_shape_block", "render_shape_blocks"]


def _header_label(shape: ShapeText) -> str:
    """``図形: 四角形 @ B3`` のような見出しラベルを組み立てる。"""
    label = f"図形: {shape.shape_kind}"
    if shape.anchor:
        label += f" @ {shape.anchor}"
    return label


def _group_note(shape: ShapeText) -> str:
    """グループ注記。最も内側のグループ名を用いる。"""
    if not shape.group_path:
        return ""
    return f" (グループ「{shape.group_path[-1]}」内)"


def _body_lines(shape: ShapeText) -> list[str]:
    """図形内の段落を、階層を反映した行の並びにする。"""
    lines: list[str] = []
    has_levels = any(p.level > 0 for p in shape.paragraphs)
    is_list = shape.shape_kind == "SmartArt" or has_levels
    for para in shape.paragraphs:
        text = escape_line("".join(run.text for run in para.runs))
        if is_list:
            indent = "  " * para.level
            lines.append(f"{indent}- {text}")
        else:
            lines.append(text)
    return lines


def _render_table(table: Table) -> str:
    """図形内の表を GFM テーブルにする。"""
    lines: list[str] = []
    for i, row in enumerate(table.rows):
        values = [escape_cell("".join(r.text for r in cell.runs)) for cell in row.cells]
        lines.append("| " + " | ".join(values) + " |")
        if i == 0:
            lines.append("| " + " | ".join("---" for _ in row.cells) + " |")
    return "\n".join(lines)


def render_shape_block(shape: ShapeText, style: ShapeStyle) -> str:
    """1つの図形テキストブロックを描画する。"""
    parts: list[str] = []
    label = _header_label(shape)
    note = _group_note(shape)
    body = _body_lines(shape)

    if body:
        if style is ShapeStyle.QUOTE:
            parts.append(f"> **[{label}]**{note}")
            parts.extend(f"> {line}" for line in body)
        elif style is ShapeStyle.HEADING:
            parts.append(f"#### [図形] {shape.shape_kind}{note}")
            parts.append("")
            parts.extend(body)
        else:  # PLAIN
            parts.extend(body)

    # 図形内の表は引用の外に出す (P002 §5.7)
    for table in shape.tables:
        if parts:
            parts.append("")
        if style is ShapeStyle.QUOTE:
            parts.append(f"> **[{label}] 内の表**")
        elif style is ShapeStyle.HEADING:
            parts.append(f"#### [図形] {shape.shape_kind} 内の表")
        else:
            parts.append(f"{shape.shape_kind} 内の表")
        parts.append("")
        parts.append(_render_table(table))

    return "\n".join(parts)


def render_shape_blocks(shapes: tuple[ShapeText, ...], style: ShapeStyle = ShapeStyle.QUOTE) -> str:
    """複数の図形ブロックを空行で区切って連結する。空なら空文字。"""
    blocks = [render_shape_block(shape, style) for shape in shapes]
    return "\n\n".join(b for b in blocks if b)
