"""表計算モードのレンダラ (要求③-1 / REQ-F-021〜030, 055)。

シートごとに章を作り、その配下に Markdown のテーブルを構成する。
**結合セルは範囲内の全セルに複製する** (テーブルの矩形を保つため)。
中間表現は結合を展開していない (INV-09) ため、この複製はレンダラが行う。
"""

from __future__ import annotations

from ..models import Cell, ConvertOptions, MergedRange, Sheet, TableRegion, col_to_letter
from .escape import escape_cell
from .excel_base import ExcelRendererBase

__all__ = ["ExcelTableRenderer"]


class ExcelTableRenderer(ExcelRendererBase):
    """表計算として使われている前提で Markdown 化する。"""

    def _render_sheet_body(self, sheet: Sheet, options: ConvertOptions) -> str:
        index = {(c.row, c.col): c for row in sheet.rows for c in row.cells}
        parts: list[str] = []
        show_headings = len(sheet.regions) >= 2
        for i, region in enumerate(sheet.regions, start=1):
            if show_headings:
                # 領域が1つだけのときは小見出しを出さない (REQ-F-055)
                parts.append(f"### 表 {i} ({region.ref})")
                parts.append("")
            parts.append(self._render_region(region, index, sheet.merged))
            parts.append("")
        return "\n".join(parts).strip("\n")

    def _render_region(
        self,
        region: TableRegion,
        index: dict[tuple[int, int], Cell],
        merged: tuple[MergedRange, ...],
    ) -> str:
        columns = list(range(region.left, region.right + 1))
        rows = list(range(region.top, region.bottom + 1))
        lines: list[str] = []
        for i, r in enumerate(rows):
            values = [escape_cell(self._cell_text(r, c, index, merged)) for c in columns]
            lines.append("| " + " | ".join(values) + " |")
            if i == 0:
                lines.append("| " + " | ".join("---" for _ in columns) + " |")
        return "\n".join(lines)

    @staticmethod
    def _cell_text(
        row: int,
        col: int,
        index: dict[tuple[int, int], Cell],
        merged: tuple[MergedRange, ...],
    ) -> str:
        """セルの表示値を返す。結合範囲内なら左上の値を複製する (REQ-F-030)。"""
        cell = index.get((row, col))
        if cell is not None:
            return cell.text
        for rng in merged:
            if rng.contains(row, col):
                origin = index.get((rng.top, rng.left))
                if origin is not None:
                    return origin.text
                break
        return ""

    def _build_stats(
        self, sheets: list[Sheet], shapes_with_text: int, images: int
    ) -> dict[str, int]:
        return {
            "sheets": len(sheets),
            "tables": sum(len(s.regions) for s in sheets),
            "shapes_with_text": shapes_with_text,
            "images": images,
        }


def region_ref(region: TableRegion) -> str:
    """領域の A1 形式表記 (テストの可読性のために公開する)。"""
    return f"{col_to_letter(region.left)}{region.top}:{col_to_letter(region.right)}{region.bottom}"
