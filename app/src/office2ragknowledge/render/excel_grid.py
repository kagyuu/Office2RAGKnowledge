"""方眼紙モードのレンダラ (要求③-2 / REQ-F-058〜063)。

シートごとに章を作り、その配下に **セルの内容を出現順に連結した本文** を構成する。
表としての構造化を行わない。

**結合セルについて何もしない。** 中間表現の ``Cell`` は結合範囲の左上にのみ存在
するため (INV-09)、そのまま連結すれば「1回だけ出力」になる (REQ-F-062)。
表計算モードとの差はここに集約される。
"""

from __future__ import annotations

from ..models import ConvertOptions, Sheet
from .escape import escape_line
from .excel_base import ExcelRendererBase

__all__ = ["ExcelGridRenderer"]


class ExcelGridRenderer(ExcelRendererBase):
    """方眼紙として使われている前提で Markdown 化する。"""

    def _render_sheet_body(self, sheet: Sheet, options: ConvertOptions) -> str:
        separator = options.excel.grid_separator
        lines: list[str] = []
        previous_blank = True  # 先頭の空行を出さない
        for row in sheet.rows:
            if row.is_empty:
                # 空行は空行として出力する = 段落境界 = チャンク区切り (REQ-F-061)
                if not previous_blank:
                    lines.append("")
                    previous_blank = True
                continue
            # 同一行の非空セルを列順に連結する。既定は区切り文字なし (REQ-F-059)。
            # cells は列番号昇順で保証されている (INV-08)。
            joined = separator.join(cell.text for cell in row.cells)
            # エスケープは **連結後の行** に適用する。連結前に適用すると、
            # 行頭でないセルの先頭文字が不要にエスケープされる。
            lines.append(escape_line(joined))
            previous_blank = False
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines)

    def _build_stats(
        self, sheets: list[Sheet], shapes_with_text: int, images: int
    ) -> dict[str, int]:
        # 方眼紙モードでは tables が意味を持たないため出力せず、代わりに lines を出す
        # (P002 §5.3、§1 論点9)
        line_count = sum(sum(1 for row in sheet.rows if not row.is_empty) for sheet in sheets)
        return {
            "sheets": len(sheets),
            "lines": line_count,
            "shapes_with_text": shapes_with_text,
            "images": images,
        }
