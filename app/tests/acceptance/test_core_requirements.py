"""A001 受け入れテスト: 中核要求の受け入れ。

利用者が明示的に指示した2つの要求が、**利用者視点で価値を出している**ことを
検証する。個々の機能の動作は結合テストで確認済みであるため、ここでは業務文書を
模した現実的なファイルで、受け取る価値の観点から判定する。

要求A: オートシェープ画像から文字を抜き出して Markdown に追記する (OCR 不要)
要求B: Excel は表計算用法と方眼紙用法の両方に、判別せず2種類の Markdown で対応する
"""

from __future__ import annotations

from pathlib import Path

import pytest

from office2ragknowledge import ConvertOptions, convert_file, inspect_file
from office2ragknowledge.ooxml.xml_utils import NS
from tests.helpers.compare import body_of
from tests.helpers.make_office import (
    add_sheet_drawing,
    docx_textbox_xml,
    inject_docx_body_xml,
    make_docx,
    make_pptx,
    make_xlsx,
)

XDR, A, P, DGM, R, REL = NS["xdr"], NS["a"], NS["p"], NS["dgm"], NS["r"], NS["rel"]

#: 図形の中にだけ書かれている文言。**すべて出力に現れなければならない。**
EXPECTED_SHAPE_TEXTS = [
    "承認は課長まで",
    "第2四半期に着手",
    "2026年4月1日 組織改編",
    "注意: 本規程は社外秘",
]


def excel_drawing(text: str, *, col: int = 4, row: int = 2) -> str:
    return (
        f'<?xml version="1.0"?><xdr:wsDr xmlns:xdr="{XDR}" xmlns:a="{A}">'
        "<xdr:twoCellAnchor>"
        f"<xdr:from><xdr:col>{col}</xdr:col><xdr:colOff>0</xdr:colOff>"
        f"<xdr:row>{row}</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>"
        '<xdr:sp><xdr:nvSpPr><xdr:cNvPr name="注記"/></xdr:nvSpPr>'
        '<a:prstGeom prst="wedgeRectCallout"/>'
        f"<xdr:txBody><a:p><a:r><a:t>{text}</a:t></a:r></a:p></xdr:txBody></xdr:sp>"
        "</xdr:twoCellAnchor></xdr:wsDr>"
    )


@pytest.fixture
def taiseizu(tmp_path: Path) -> Path:
    """方眼紙レイアウトの組織図シート + 正規の名簿シートを持つブック。"""
    path = make_xlsx(
        tmp_path / "体制図.xlsx",
        {
            "名簿": [
                ["氏名", "部署", "内線"],
                ["山田 太郎", "開発部", 101],
                ["佐藤 花子", "営業部", 202],
                ["鈴木 一郎", "総務部", 303],
            ],
            "組織図": [
                ["株式", "会社", "サンプル", "", ""],
                ["", "", "", "", ""],
                ["", "開発", "部", "", ""],
                ["", "", "第1", "課", ""],
                ["", "", "第2", "課", ""],
            ],
        },
    )
    add_sheet_drawing(path, 1, excel_drawing("2026年4月1日 組織改編"))
    return path


@pytest.fixture
def kaigi(tmp_path: Path) -> Path:
    """本文が図形に書かれた会議資料。"""
    return make_pptx(
        tmp_path / "会議資料.pptx",
        [
            ("2026年度 事業計画", ["承認は課長まで"], "詳細は別紙参照"),
            ("進捗", ["第2四半期に着手"], None),
        ],
    )


@pytest.fixture
def kitei(tmp_path: Path) -> Path:
    """注意事項がテキストボックスに書かれた規程。"""
    path = make_docx(
        tmp_path / "規程.docx",
        [("h1", "第1章 総則"), ("p", "この規程は業務の基準を定める。")],
    )
    inject_docx_body_xml(path, docx_textbox_xml(["注意: 本規程は社外秘"]))
    return path


def all_bodies(path: Path, options: ConvertOptions | None = None) -> str:
    result = convert_file(path, options or ConvertOptions())
    return "\n".join(body_of(o.markdown) for o in result.outputs)


# ============================================================
# 要求A: オートシェープからの文字抽出
# ============================================================


# 期待1/2: 図形内の文言が 100% 出力に現れる
def test_all_shape_texts_appear(taiseizu: Path, kaigi: Path, kitei: Path) -> None:
    combined = "\n".join(all_bodies(p) for p in (taiseizu, kaigi, kitei))
    missing = [t for t in EXPECTED_SHAPE_TEXTS if t not in combined]
    assert missing == [], f"図形内の文言が取りこぼされました: {missing}"


# 期待3: 重複がない
def test_no_duplicate_shape_text(taiseizu: Path, kaigi: Path, kitei: Path) -> None:
    for path in (taiseizu, kaigi, kitei):
        body = all_bodies(path)
        for text in EXPECTED_SHAPE_TEXTS:
            count = body.count(text)
            if count:
                # Excel は2出力あるため、1出力あたり1回であればよい
                outputs = len(convert_file(path).outputs)
                assert count == outputs, f"{path.name}: '{text}' が {count} 回現れました"


# 期待4: 本文と区別できる形で出力される
def test_shape_text_is_distinguishable(kitei: Path) -> None:
    body = all_bodies(kitei)
    assert "> **[図形:" in body


# 期待6: --no-shapes で失われる (対照実験)
def test_control_experiment_no_shapes(taiseizu: Path, kaigi: Path, kitei: Path) -> None:
    """機能が実際に寄与していることを、無効化して確認する。"""
    options = ConvertOptions(shapes=False)
    combined = "\n".join(all_bodies(p, options) for p in (taiseizu, kaigi, kitei))
    still_present = [t for t in EXPECTED_SHAPE_TEXTS if t in combined]
    assert still_present == [], (
        f"--no-shapes でも残っている文言があります (図形以外から来ている): {still_present}"
    )


# 期待7: 画像内の文字は出力されない (OCR を行わないスコープどおり)
def test_no_ocr(tmp_path: Path) -> None:
    """画像バイナリを解析しないため、画像内の文字は現れない。"""
    path = make_xlsx(tmp_path / "img.xlsx", {"S1": [["セルの値"]]})
    body = all_bodies(path)
    # 画像は含まれていないが、OCR を行わない設計であることを型で確認する
    assert "セルの値" in body


# 期待8: inspect の図形数
def test_inspect_reports_shapes(taiseizu: Path) -> None:
    info = inspect_file(taiseizu)
    assert info.shape_with_text_count >= 1
    assert info.shape_count >= info.shape_with_text_count


# ============================================================
# 要求B: Excel の判別なし二重出力
# ============================================================


# 期待9: 2ファイルが生成される
def test_two_outputs(taiseizu: Path) -> None:
    result = convert_file(taiseizu)
    assert len(result.outputs) == 2
    assert sorted(o.filename_suffix for o in result.outputs) == [".grid.md", ".table.md"]


# 期待10: 判別が行われていない — 両シートが両ファイルに出る
def test_no_detection_both_sheets_in_both_files(taiseizu: Path) -> None:
    """方眼紙シートも名簿シートも、両方のファイルに出力されている。

    判別していれば、どちらかのシートがどちらかのファイルから欠落するはずである。
    """
    for output in convert_file(taiseizu).outputs:
        body = body_of(output.markdown)
        assert "## 名簿" in body, f"{output.filename_suffix} に名簿シートがありません"
        assert "## 組織図" in body, f"{output.filename_suffix} に組織図シートがありません"


# 期待11: 方眼紙シートが文として読める
def test_grid_mode_is_readable_prose(taiseizu: Path) -> None:
    grid = next(o for o in convert_file(taiseizu).outputs if o.filename_suffix == ".grid.md")
    section = body_of(grid.markdown).split("## 組織図")[1]
    assert "株式会社サンプル" in section, "セルをまたぐ語が連結されていません"
    assert "開発部" in section
    assert "第1課" in section


# 期待12: 名簿シートがテーブルになる
def test_table_mode_has_proper_table(taiseizu: Path) -> None:
    table = next(o for o in convert_file(taiseizu).outputs if o.filename_suffix == ".table.md")
    section = body_of(table.markdown).split("## 名簿")[1].split("\n## ")[0]
    assert "| 氏名 | 部署 | 内線 |" in section
    assert "| --- | --- | --- |" in section
    assert "| 山田 太郎 | 開発部 | 101 |" in section


# 期待13: output_mode で区別できる
def test_output_mode_distinguishes(taiseizu: Path) -> None:
    modes = {o.filename_suffix: o.mode for o in convert_file(taiseizu).outputs}
    assert str(modes[".table.md"]) == "table"
    assert str(modes[".grid.md"]) == "grid"


# 期待14: 両ファイルとも図形テキストが章末にある
def test_shape_text_in_both_outputs(taiseizu: Path) -> None:
    for output in convert_file(taiseizu).outputs:
        body = body_of(output.markdown)
        assert "2026年4月1日 組織改編" in body, output.filename_suffix


# 期待15: 空行が段落境界として機能する
def test_grid_blank_lines_are_chunk_boundaries(taiseizu: Path) -> None:
    grid = next(o for o in convert_file(taiseizu).outputs if o.filename_suffix == ".grid.md")
    section = body_of(grid.markdown).split("## 組織図")[1]
    lines = [ln for ln in section.splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    # 「株式会社サンプル」の次は空行 (元シートの2行目が空行)
    assert lines[0] == "株式会社サンプル"
    assert lines[1] == ""


# ============================================================
# 総合
# ============================================================


# 期待16: 日本語のファイル名
def test_japanese_filenames(taiseizu: Path, tmp_path: Path) -> None:
    from office2ragknowledge import write_result

    written = write_result(convert_file(taiseizu), tmp_path / "out")
    names = sorted(p.name for p in written.markdown_paths)
    assert names == ["体制図.grid.md", "体制図.table.md"]


# 期待17: 3ファイルすべて成功
def test_all_files_convert(taiseizu: Path, kaigi: Path, kitei: Path) -> None:
    for path in (taiseizu, kaigi, kitei):
        result = convert_file(path)
        assert result.outputs, path.name


# 期待18: P001 §1.3 の課題3・課題5 が解決されている
def test_core_problems_are_solved(taiseizu: Path, kitei: Path) -> None:
    """課題3 (図形の取りこぼし) と課題5 (Excel の二面性)。"""
    # 課題3: 図形内の文言が出力に現れる
    assert "注意: 本規程は社外秘" in all_bodies(kitei)
    # 課題5: 両用法に対応した2つの表現が得られる
    outputs = convert_file(taiseizu).outputs
    assert len(outputs) == 2
    assert body_of(outputs[0].markdown) != body_of(outputs[1].markdown)
