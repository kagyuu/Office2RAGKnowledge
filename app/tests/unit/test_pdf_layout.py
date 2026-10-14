"""U006-T3 / U007: タグなし PDF のレイアウト (P003 §7A.6〜7A.9。※CR-001・CR-002)。"""

from __future__ import annotations

from office2ragknowledge.pdf.backend import open_pdf
from office2ragknowledge.pdf.layout import LayoutResult, layout_document
from tests.helpers.make_pdf import Page, Text, build_pdf


def _layout(
    pages: list[Page], *, shapes: bool = True, headers_footers: bool = False
) -> LayoutResult:
    return layout_document(
        open_pdf(build_pdf(pages)), shapes=shapes, headers_footers=headers_footers
    )


def _paragraphs(result: LayoutResult) -> list[str]:
    return [b.text for b in result.blocks if b.kind == "paragraph"]


# --- U006-T3 -----------------------------------------------------------------


def test_close_lines_join_and_wide_gap_splits() -> None:
    page = Page(
        items=[
            Text(50, 760, "一行目の文と", 12),
            Text(50, 746, "その続き。", 12),  # 行送り 14pt → 同じ段落
            Text(50, 700, "次の段落。", 12),  # 大きく空く → 別の段落
        ]
    )
    assert _paragraphs(_layout([page])) == ["一行目の文とその続き。", "次の段落。"]


def test_latin_lines_join_with_space() -> None:
    page = Page(items=[Text(50, 760, "first line", 12), Text(50, 746, "second", 12)])
    assert _paragraphs(_layout([page])) == ["first line second"]


def test_size_change_splits_paragraph() -> None:
    page = Page(items=[Text(50, 760, "大きな表題", 20), Text(50, 738, "本文の行", 12)])
    assert _paragraphs(_layout([page])) == ["大きな表題", "本文の行"]


def test_same_row_fragments_joined_with_space() -> None:
    page = Page(items=[Text(50, 760, "項目", 12), Text(300, 760, "値", 12)])
    assert _paragraphs(_layout([page])) == ["項目 値"]


def test_figure_text_becomes_figure_block() -> None:
    page = Page(
        items=[
            Text(50, 760, "本文です。", 12),
            Text(110, 540, "図の一行目", 10),
            Text(110, 525, "図の二行目", 10),
            Text(50, 400, "後の本文。", 12),
        ],
        rects=[(100, 500, 200, 70)],
    )
    result = _layout([page])
    kinds = [b.kind for b in result.blocks]
    assert kinds == ["paragraph", "figure", "paragraph"]
    assert result.blocks[1].lines == ("図の一行目", "図の二行目")
    assert "図の一行目" not in "".join(_paragraphs(result))


def test_page_frame_and_underline_are_not_figures() -> None:
    page = Page(
        items=[Text(50, 760, "枠の中の本文", 12)],
        rects=[(10, 10, 575, 822), (50, 755, 100, 1)],  # ページ全体の枠と下線
    )
    result = _layout([page])
    assert [b.kind for b in result.blocks] == ["paragraph"]


def test_no_shapes_keeps_figure_text_in_body() -> None:
    page = Page(items=[Text(110, 540, "図の文字", 10)], rects=[(100, 500, 200, 70)])
    result = _layout([page], shapes=False)
    assert [b.kind for b in result.blocks] == ["paragraph"]
    assert _paragraphs(result) == ["図の文字"]


def test_page_change_splits_paragraph() -> None:
    pages = [
        Page(items=[Text(50, 60, "一枚目の最後", 12)]),
        Page(items=[Text(50, 800, "二枚目の最初", 12)]),
    ]
    assert _paragraphs(_layout(pages)) == ["一枚目の最後", "二枚目の最初"]


def test_layout_is_deterministic() -> None:
    page = Page(
        items=[Text(50, 760, "a", 12), Text(300, 760, "b", 12), Text(50, 700, "c", 12)],
        rects=[(280, 740, 60, 40)],
    )
    data = build_pdf([page])
    first = layout_document(open_pdf(data), shapes=True, headers_footers=False)
    second = layout_document(open_pdf(data), shapes=True, headers_footers=False)
    assert first == second


# --- U007-T1: ヘッダー・フッター --------------------------------------------------

from office2ragknowledge.pdf.layout import normalize_repeat_key  # noqa: E402


def _report_pages(n: int, *, cover_title: bool = False) -> list[Page]:
    pages = []
    for i in range(1, n + 1):
        items = [
            Text(50, 815, "社外秘 報告書", 9),
            Text(280, 25, f"- {i} -", 9),
            Text(50, 700, f"{i}ページ目の本文です。", 12),
        ]
        if cover_title and i == 1:
            items.append(Text(50, 790, "表紙だけの題名", 9))
        pages.append(Page(items=items))
    return pages


def test_repeated_header_and_page_number_removed() -> None:
    result = _layout(_report_pages(3))
    text = "\n".join(_paragraphs(result))
    assert "社外秘" not in text and "- 1 -" not in text and "- 3 -" not in text
    assert _paragraphs(result) == [
        "1ページ目の本文です。",
        "2ページ目の本文です。",
        "3ページ目の本文です。",
    ]
    assert result.headers_footers_removed == 6


def test_normalize_repeat_key() -> None:
    assert normalize_repeat_key("- 12 -") == "-#-"
    assert normalize_repeat_key("3 / 10") == "#/#"
    assert normalize_repeat_key("Page 4") == "Page#"
    assert normalize_repeat_key("iv") == "#"
    assert normalize_repeat_key("Ⅳ") == "#"
    assert normalize_repeat_key("１２") == "#"
    assert normalize_repeat_key("社外秘 報告書") == "社外秘報告書"


def test_cover_only_text_in_band_is_kept() -> None:
    result = _layout(_report_pages(3, cover_title=True))
    assert "表紙だけの題名" in "\n".join(_paragraphs(result))


def test_single_page_keeps_band_text() -> None:
    result = _layout(_report_pages(1))
    text = "\n".join(_paragraphs(result))
    assert "社外秘 報告書" in text and "- 1 -" in text
    assert result.headers_footers_removed == 0


def test_headers_footers_option_keeps_them() -> None:
    result = _layout(_report_pages(3), headers_footers=True)
    text = "\n".join(_paragraphs(result))
    assert "社外秘 報告書" in text and "- 2 -" in text
    assert result.headers_footers_removed == 0


def test_same_text_outside_band_is_kept() -> None:
    pages = _report_pages(3)
    pages[1].items.append(Text(50, 500, "社外秘 報告書", 9))
    assert "社外秘 報告書" in _paragraphs(_layout(pages))


def test_odd_even_headers_both_removed() -> None:
    pages = []
    for i in range(1, 5):
        header = "文書名" if i % 2 else "第1章 概要"
        pages.append(Page(items=[Text(50, 815, header, 9), Text(50, 700, f"本文{i}", 12)]))
    result = _layout(pages)
    assert _paragraphs(result) == ["本文1", "本文2", "本文3", "本文4"]
    assert result.headers_footers_removed == 4


# --- U007-T2: 段組み ----------------------------------------------------------


def _two_columns(title: bool = False, figure: bool = False) -> Page:
    items = []
    if title:
        items.append(Text(150, 780, "全幅の表題です", 20))
    for i in range(5):
        y = 740 - 14 * i
        items.append(Text(50, y, f"左{i}の段の行は段の幅いっぱいです", 12))
        items.append(Text(320, y, f"右{i}の段の行も段の幅いっぱいです", 12))
    rects = []
    if figure:
        items.append(Text(60, 600, "全幅の図の中の文字列です", 10))
        rects.append((40, 580, 500, 40))
        for i in range(5):
            y = 540 - 14 * i
            items.append(Text(50, y, f"下左{i}の段の行も幅いっぱいです", 12))
            items.append(Text(320, y, f"下右{i}の段の行も幅いっぱいです", 12))
    return Page(items=items, rects=rects)


def test_two_columns_left_then_right() -> None:
    result = _layout([_two_columns()])
    assert _paragraphs(result) == [
        "".join(f"左{i}の段の行は段の幅いっぱいです" for i in range(5)),
        "".join(f"右{i}の段の行も段の幅いっぱいです" for i in range(5)),
    ]
    assert result.multi_column_pages == 1


def test_title_then_left_then_right() -> None:
    paragraphs = _paragraphs(_layout([_two_columns(title=True)]))
    assert paragraphs[0] == "全幅の表題です"
    assert paragraphs[1].startswith("左0") and paragraphs[2].startswith("右0")


def test_full_width_figure_splits_sections() -> None:
    result = _layout([_two_columns(figure=True)])
    order = [
        b.kind + ":" + (b.text[:3] if b.kind == "paragraph" else b.lines[0][:3])
        for b in result.blocks
    ]
    assert order == [
        "paragraph:左0の",
        "paragraph:右0の",
        "figure:全幅の",
        "paragraph:下左0",
        "paragraph:下右0",
    ]
    assert result.multi_column_pages == 1


def test_three_columns() -> None:
    items = []
    for i in range(4):
        y = 740 - 14 * i
        items += [
            Text(40, y, f"A{i} col txt", 12),
            Text(230, y, f"B{i} col txt", 12),
            Text(420, y, f"C{i} col txt", 12),
        ]
    paragraphs = _paragraphs(_layout([Page(items=items)]))
    assert [p.split()[0] for p in paragraphs] == ["A0", "B0", "C0"]
    assert paragraphs[0] == " ".join(f"A{i} col txt" for i in range(4))


def test_single_column_unchanged() -> None:
    items = [
        Text(50, 760, "通常の段落の一行目で、ページの幅いっぱいに書かれている文章です。", 12),
        Text(62, 746, "字下げした二行目", 12),
        Text(50, 732, "短い行", 12),
        Text(50, 718, "通常の段落の最後の行で、これもページの幅いっぱいに書かれています。", 12),
    ]
    result = _layout([Page(items=items)])
    assert result.multi_column_pages == 0
    assert _paragraphs(result)[0].startswith("通常の段落の一行目")
    assert _paragraphs(result)[0].endswith("書かれています。")


def test_short_side_is_not_a_column() -> None:
    items = [Text(50, 740 - 14 * i, f"左{i}の段の行は段の幅いっぱいです", 12) for i in range(5)]
    items += [Text(320, 740, "右だけ一行", 12), Text(320, 726, "右二行目", 12)]
    assert _layout([Page(items=items)]).multi_column_pages == 0


def test_key_value_form_is_not_columns() -> None:
    items = []
    for i in range(5):
        y = 740 - 14 * i
        items += [
            Text(50, y, f"項目{i}", 12),
            Text(140, y, f"値{i}の内容がここに書かれています", 12),
        ]
    result = _layout([Page(items=items)])
    assert result.multi_column_pages == 0
    assert _paragraphs(result)[0].startswith("項目0 値0")


def test_columns_deterministic() -> None:
    data = build_pdf([_two_columns(title=True, figure=True)])
    a = layout_document(open_pdf(data), shapes=True, headers_footers=False)
    b = layout_document(open_pdf(data), shapes=True, headers_footers=False)
    assert a == b
