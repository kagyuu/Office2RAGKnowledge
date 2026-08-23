"""Excel パーサ (要求②③ / REQ-F-021〜068)。

**openpyxl を1回ロードし、加えて sheet XML への lxml 1パスを併用する**
ハイブリッド方式 (ADR-002)。実測で2回ロード方式より約27%速く、REQ-F-068
(解析は1回のみ) を満たす。

**実装上の最重要点** (P003 §1.2 の実測):
openpyxl が書き出した数式セルの生 XML は ``<c r="B2"><f>A2*2</f><v></v></c>``
であり、``<v>`` 要素は **存在するが中身が空**である。キャッシュ値の有無は
**``<v>`` のテキストが空か否か**で判定しなければならない。要素の有無で判定すると
必ず誤判定する。
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils.datetime import from_excel

from ..models import (
    Cell,
    ConvertOptions,
    Document,
    DocumentFormat,
    DocumentMeta,
    MergedRange,
    Sheet,
    SheetRow,
    col_to_letter,
)
from ..ooxml.xml_utils import NS, qn
from ..ooxml.zip_reader import SafeZipReader
from .base import parse_iso, read_core_properties
from .excel_regions import detect_regions
from .excel_shapes import extract_sheet_shapes

__all__ = ["ExcelParser", "format_cell_value", "parse_cell_ref"]

_CELL_REF = re.compile(r"^([A-Z]+)(\d+)$")


def parse_cell_ref(ref: str) -> tuple[int, int] | None:
    """``"B3"`` を ``(row=3, col=2)`` に変換する。解析できなければ ``None``。"""
    m = _CELL_REF.match(ref.upper())
    if m is None:
        return None
    letters, digits = m.group(1), m.group(2)
    col = 0
    for ch in letters:
        col = col * 26 + (ord(ch) - ord("A") + 1)
    return int(digits), col


def _is_date_format(number_format: str) -> bool:
    fmt = number_format.lower()
    if "general" in fmt:
        return False
    stripped = re.sub(r"\[[^\]]*\]", "", fmt)
    stripped = re.sub(r'"[^"]*"', "", stripped)
    return any(token in stripped for token in ("yy", "mm", "dd", "hh", "ss", "m/d", "d/m"))


def _has_time(number_format: str) -> bool:
    stripped = re.sub(r"\[[^\]]*\]", "", number_format.lower())
    return "h" in stripped or "s" in stripped


def _has_date(number_format: str) -> bool:
    stripped = re.sub(r"\[[^\]]*\]", "", number_format.lower())
    return "y" in stripped or "d" in stripped


def _format_number(value: float) -> str:
    """不要な末尾ゼロを除いた10進表記にする。"""
    if isinstance(value, int) or float(value).is_integer():
        return str(int(value))
    text = f"{value:.10f}".rstrip("0").rstrip(".")
    return text or "0"


def format_cell_value(value: Any, number_format: str) -> str:
    """セルの値に表示形式を適用して文字列にする (REQ-F-026)。

    ロケール依存の通貨書式は網羅せず、記号を抽出できない場合は数値のみを返す
    (ArchitectureHandbook §9-2 の既知の制約)。
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, datetime):
        if _has_date(number_format) and _has_time(number_format):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        if _has_time(number_format) and not _has_date(number_format):
            return value.strftime("%H:%M:%S")
        return value.strftime("%Y-%m-%d")
    if isinstance(value, dt.date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, dt.time):
        return value.strftime("%H:%M:%S")
    if isinstance(value, (int, float)):
        if _is_date_format(number_format):
            try:
                converted = from_excel(value)
            except (ValueError, OverflowError, TypeError):
                converted = None
            if isinstance(converted, (datetime, dt.date, dt.time)):
                return format_cell_value(converted, number_format)
        if "%" in number_format:
            return f"{_format_number(float(value) * 100)}%"
        currency = _extract_currency(number_format)
        text = _format_number(float(value))
        if currency:
            return f"{currency}{text}"
        return text
    return str(value)


_CURRENCY_RE = re.compile(r"(?:\[\$([^\-\]]+)[^\]]*\])|([¥$€£])")


def _extract_currency(number_format: str) -> str:
    m = _CURRENCY_RE.search(number_format)
    if m is None:
        return ""
    return (m.group(1) or m.group(2) or "").strip()


class ExcelParser:
    """``.xlsx`` / ``.xlsm`` を中間表現に変換する。"""

    def parse(
        self,
        reader: SafeZipReader,
        filename: str,
        options: ConvertOptions,
        converted_at: datetime,
    ) -> Document:
        props = read_core_properties(reader)
        # Windows のパス区切りも扱えるよう Path を用いる (posixpath は "\\" を分割しない)
        title = props.get("title") or Path(filename).stem

        # openpyxl は data_only=True で1回だけ開く。数式は lxml 経路から得る。
        workbook = self._load_workbook(reader)
        try:
            sheet_parts = self._resolve_sheet_parts(reader)
            blocks: list[Sheet] = []
            warnings: list[str] = []
            for order, ws in enumerate(workbook.worksheets):
                hidden = ws.sheet_state != "visible"
                if hidden and not options.include_hidden:
                    continue
                part = sheet_parts.get(order)
                formula_map = self._read_formula_map(reader, part) if part else {}
                sheet = self._build_sheet(ws, formula_map, options, hidden=hidden)
                if options.shapes and part:
                    # 図形は打ち切りの影響を受けない (P003 §7.5)
                    shapes, shape_count = extract_sheet_shapes(reader, part)
                    sheet = replace(sheet, shapes=shapes, shape_count=shape_count)
                blocks.append(sheet)
                warnings.extend(self._sheet_warnings(sheet, options))
        finally:
            workbook.close()

        meta = DocumentMeta(
            source_file=Path(filename).name,
            source_path=filename,
            source_format=DocumentFormat.XLSX,
            source_size_bytes=0,
            source_sha256="",
            converter="office2ragknowledge",
            converted_at=converted_at,
            title=title,
            author=props.get("author"),
            created_at=parse_iso(props.get("created")),
            modified_at=parse_iso(props.get("modified")),
            warnings=tuple(warnings),
        )
        return Document(
            format=DocumentFormat.XLSX,
            title=title,
            meta=meta,
            blocks=tuple(blocks),
            warnings=tuple(warnings),
        )

    # -- openpyxl -------------------------------------------------------

    @staticmethod
    def _load_workbook(reader: SafeZipReader) -> Any:
        """ブックを開く。

        ``read_only=False`` とするのは、結合範囲 (``merged_cells``) の取得に
        必要なためである (ADR-007)。メモリ効率より機能要件を優先する。
        """
        import io

        source = reader.source
        target: Any = io.BytesIO(source) if isinstance(source, bytes) else source
        kwargs: dict[str, Any] = {
            "data_only": True,
            "read_only": False,
            "keep_vba": False,
            "keep_links": False,
        }
        try:
            return load_workbook(target, rich_text=False, **kwargs)
        except TypeError:
            # 一部の版は rich_text 引数を持たない
            if isinstance(source, bytes):
                target = io.BytesIO(source)
            return load_workbook(target, **kwargs)

    # -- lxml 経路 ------------------------------------------------------

    @staticmethod
    def _resolve_sheet_parts(reader: SafeZipReader) -> dict[int, str]:
        """シートの並び順 → sheet XML のパートを ``_rels`` で解決する。

        ``sheet1.xml`` の ``1`` はシートの並び順ではない (削除・並べ替えの履歴に
        よる)。ファイル名の数値で対応付けると誤ったシートに紐づく (P003 §7.6)。
        """
        if not reader.has("xl/workbook.xml"):
            return {}
        root = reader.read_xml("xl/workbook.xml")
        rels = reader.resolve_rels("xl/workbook.xml")
        result: dict[int, str] = {}
        sheets_el = root.find(qn("m:sheets"))
        if sheets_el is None:
            return {}
        for order, sheet_el in enumerate(sheets_el.findall(qn("m:sheet"))):
            rel_id = sheet_el.get(f"{{{NS['r']}}}id")
            if rel_id and rel_id in rels:
                result[order] = rels[rel_id]
        return result

    @staticmethod
    def _read_formula_map(reader: SafeZipReader, part: str) -> dict[str, tuple[str, bool]]:
        """sheet XML から ``セル参照 -> (数式, キャッシュ値の有無)`` を作る。

        **キャッシュ値の有無は ``<v>`` のテキストで判定する。**
        openpyxl は ``<v></v>`` (空要素) を書き出すため、要素の有無で判定すると
        必ず誤判定する (P003 §1.2 の実測)。
        """
        if not reader.has(part):
            return {}
        root = reader.read_xml(part)
        f_tag, v_tag, c_tag = qn("m:f"), qn("m:v"), qn("m:c")
        result: dict[str, tuple[str, bool]] = {}
        shared: dict[str, str] = {}
        for cell_el in root.iter(c_tag):
            ref = cell_el.get("r")
            if ref is None:
                continue
            f_el = cell_el.find(f_tag)
            if f_el is None:
                continue
            v_el = cell_el.find(v_tag)
            # ここが要点: 要素の有無ではなくテキストの有無で判定する
            has_cache = v_el is not None and v_el.text not in (None, "")

            text = (f_el.text or "").strip()
            si = f_el.get("si")
            if f_el.get("t") == "shared" and si is not None:
                if text:
                    shared[si] = text
                else:
                    text = shared.get(si, "")
            if not text:
                result[ref] = ("", has_cache)
                continue
            # XML の <f> は先頭の "=" を含まないため前置して正規化する
            formula = text if text.startswith("=") else f"={text}"
            result[ref] = (formula, has_cache)
        return result

    # -- 中間表現の構築 --------------------------------------------------

    def _build_sheet(
        self,
        ws: Any,
        formula_map: dict[str, tuple[str, bool]],
        options: ConvertOptions,
        *,
        hidden: bool,
    ) -> Sheet:
        hidden_rows = self._hidden_rows(ws) if not options.include_hidden else set()
        hidden_cols = self._hidden_cols(ws) if not options.include_hidden else set()

        max_row = int(ws.max_row or 0)
        max_col = int(ws.max_column or 0)
        total_rows = max_row
        limit = options.excel.max_rows
        truncated_at: int | None = None
        # 打ち切りは表領域の検出より前に行う (P003 §7.5)。
        # 検出後に切ると領域が途中で切れて不整合な TableRegion が残る。
        if limit > 0 and max_row > limit:
            truncated_at = limit
            max_row = limit

        rows: list[SheetRow] = []
        missing_cache = 0
        for r in range(1, max_row + 1):
            if r in hidden_rows:
                continue
            cells: list[Cell] = []
            for c in range(1, max_col + 1):
                if c in hidden_cols:
                    continue
                cell = ws.cell(row=r, column=c)
                ref = f"{col_to_letter(c)}{r}"
                formula, has_cache = formula_map.get(ref, ("", True))
                is_formula = bool(formula)
                if is_formula and not has_cache:
                    text = formula
                    missing_cache += 1
                    value_missing = True
                else:
                    text = format_cell_value(cell.value, cell.number_format or "General")
                    value_missing = False
                    if is_formula and options.excel.formulas and text:
                        text = f"{text} ({formula})"
                if not text:
                    continue
                cells.append(
                    Cell(
                        row=r,
                        col=c,
                        text=text,
                        is_formula=is_formula,
                        formula=formula or None,
                        value_missing=value_missing,
                    )
                )
            rows.append(SheetRow(row_index=r, cells=tuple(cells)))

        # INV-07: 使用範囲の最小行〜最大行を欠番なく含める。
        # 上のループは 1 行目から連続して追加しているため欠番は生じない。
        merged = tuple(
            MergedRange(top=rng.min_row, left=rng.min_col, bottom=rng.max_row, right=rng.max_col)
            for rng in sorted(ws.merged_cells.ranges, key=lambda x: (x.min_row, x.min_col))
        )
        regions, abandoned = detect_regions(
            rows,
            merged,
            enabled=options.excel.table_regions,
            max_regions=options.excel.max_table_regions,
        )
        is_empty = not any(row.cells for row in rows)
        return Sheet(
            name=str(ws.title),
            rows=tuple(rows),
            merged=merged,
            regions=regions,
            shapes=(),  # U003 で埋める
            hidden=hidden,
            region_split_abandoned=abandoned,
            truncated_at=truncated_at,
            total_rows=total_rows,
            formula_without_cache_count=missing_cache,
            shape_count=0,
            is_empty=is_empty,
        )

    @staticmethod
    def _hidden_rows(ws: Any) -> set[int]:
        return {idx for idx, dim in ws.row_dimensions.items() if getattr(dim, "hidden", False)}

    @staticmethod
    def _hidden_cols(ws: Any) -> set[int]:
        hidden: set[int] = set()
        for dim in ws.column_dimensions.values():
            if not getattr(dim, "hidden", False):
                continue
            start = getattr(dim, "min", None)
            end = getattr(dim, "max", None)
            if start is None or end is None:
                continue
            hidden.update(range(int(start), int(end) + 1))
        return hidden

    @staticmethod
    def _sheet_warnings(sheet: Sheet, options: ConvertOptions) -> Iterator[str]:
        if sheet.truncated_at is not None:
            yield (
                f"シート「{sheet.name}」は {sheet.truncated_at} 行で打ち切りました "
                f"(全 {sheet.total_rows} 行)"
            )
        if sheet.formula_without_cache_count:
            yield (
                f"シート「{sheet.name}」に計算結果を持たない数式セルが "
                f"{sheet.formula_without_cache_count} 件あり、数式を出力しました"
            )
        if sheet.region_split_abandoned:
            yield (
                f"シート「{sheet.name}」は表領域が "
                f"{options.excel.max_table_regions} 件を超えたため、"
                "分割せず1つの表として出力しました"
            )
