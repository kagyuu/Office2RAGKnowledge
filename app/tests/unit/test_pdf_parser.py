"""U006-T4: PDF パーサ (P003 §7A.4, §7A.10。※CR-001)。"""

from __future__ import annotations

from datetime import UTC, datetime

from office2ragknowledge.models import (
    ConvertOptions,
    DocumentFormat,
    Heading,
    Image,
    ImageMode,
    ListBlock,
    Paragraph,
    ShapeText,
    Table,
    runs_text,
)
from office2ragknowledge.parsers.pdf import PdfParser
from tests.helpers.make_pdf import Elem, Page, Text, build_pdf, encrypt_pdf

NOW = datetime(2026, 10, 14, tzinfo=UTC)
LIST_DECIMAL = " /A << /O /List /ListNumbering /Decimal >>"


def _parse(data: bytes, options: ConvertOptions | None = None, name: str = "doc.pdf"):  # type: ignore[no-untyped-def]
    return PdfParser().parse(data, name, options or ConvertOptions(), NOW)


def _tagged(items: list[Text], kids: list[Elem], **kw: object) -> bytes:
    return build_pdf([Page(items=items)], Elem("Document", kids), **kw)  # type: ignore[arg-type]


def test_headings_in_document_order() -> None:
    items = [
        Text(50, 780, "第1章", 18, mcid=0),
        Text(50, 740, "第1節", 14, mcid=1),
        Text(50, 700, "第1項", 12, mcid=2),
        Text(50, 660, "本文", 12, mcid=3),
    ]
    doc = _parse(
        _tagged(
            items,
            [Elem("H1", [(0, 0)]), Elem("H2", [(0, 1)]), Elem("H3", [(0, 2)]), Elem("P", [(0, 3)])],
        )
    )
    assert [
        (type(b).__name__, getattr(b, "level", None), runs_text(b.runs)) for b in doc.blocks
    ] == [  # type: ignore[attr-defined]
        ("Heading", 1, "第1章"),
        ("Heading", 2, "第1節"),
        ("Heading", 3, "第1項"),
        ("Paragraph", None, "本文"),
    ]
    assert doc.format is DocumentFormat.PDF
    assert doc.meta.pdf_structure == "tagged"


def test_generic_h_level_from_sect_depth() -> None:
    items = [Text(50, 780, "a", 12, mcid=0), Text(50, 740, "b", 12, mcid=1)]
    kids = [Elem("Sect", [Elem("H", [(0, 0)]), Elem("Sect", [Elem("H", [(0, 1)])])])]
    doc = _parse(_tagged(items, kids))
    assert [b.level for b in doc.blocks if isinstance(b, Heading)] == [2, 3]


def test_title_tag_is_level_1() -> None:
    doc = _parse(_tagged([Text(50, 780, "題", 18, mcid=0)], [Elem("Title", [(0, 0)])]))
    assert isinstance(doc.blocks[0], Heading) and doc.blocks[0].level == 1


def _nested_list(extra: str = "", labels: tuple[str, str, str] | None = None) -> bytes:
    items = [
        Text(70, 780, "項目A", 12, mcid=0),
        Text(90, 760, "子項目", 12, mcid=1),
        Text(110, 740, "孫項目", 12, mcid=2),
        Text(70, 720, "項目B", 12, mcid=3),
    ]
    mcids = len(items)
    lbl: list[Elem] = []
    if labels:
        for i, label in enumerate(labels):
            items.append(Text(50, 780 - 20 * i, label, 12, mcid=mcids + i))
        lbl = [Elem("Lbl", [(0, mcids + i)]) for i in range(3)]

    def li(mcid: int, nested: list[Elem], label: list[Elem]) -> Elem:
        return Elem("LI", [*label, Elem("LBody", [(0, mcid), *nested])])

    grand = Elem("L", [li(2, [], [])])
    child = Elem("L", [li(1, [grand], [])])
    top = Elem("L", [li(0, [child], lbl[:1]), li(3, [], lbl[1:2])], extra=extra)
    return _tagged(items, [top])


def test_nested_list_levels() -> None:
    doc = _parse(_nested_list())
    (lst,) = [b for b in doc.blocks if isinstance(b, ListBlock)]
    assert [(runs_text(i.runs), i.level) for i in lst.items] == [
        ("項目A", 0),
        ("子項目", 1),
        ("孫項目", 2),
        ("項目B", 0),
    ]
    assert not lst.items[0].ordered


def test_list_numbering_attribute() -> None:
    (lst,) = [b for b in _parse(_nested_list(LIST_DECIMAL)).blocks if isinstance(b, ListBlock)]
    assert lst.items[0].ordered and lst.items[3].ordered
    assert not lst.items[1].ordered  # 入れ子のリストは自身の属性で判定する


def test_list_label_detects_ordered_and_label_not_in_text() -> None:
    (lst,) = [
        b
        for b in _parse(_nested_list(labels=("1.", "2.", "3."))).blocks
        if isinstance(b, ListBlock)
    ]
    assert lst.items[0].ordered
    assert runs_text(lst.items[0].runs) == "項目A"
    (lst2,) = [
        b for b in _parse(_nested_list(labels=("•", "•", "•"))).blocks if isinstance(b, ListBlock)
    ]
    assert not lst2.items[0].ordered


def _table() -> bytes:
    items = [
        Text(50 + 60 * i, 780, t, 12, mcid=i) for i, t in enumerate(["見出1", "見出2", "見出3"])
    ]
    items += [
        Text(50, 760, "結合", 12, mcid=3),
        Text(170, 760, "c", 12, mcid=4),
        Text(50, 740, "縦", 12, mcid=5),
        Text(110, 740, "x", 12, mcid=6),
    ]
    head = Elem("THead", [Elem("TR", [Elem("TH", [(0, i)]) for i in range(3)])])
    body = Elem(
        "TBody",
        [
            Elem(
                "TR",
                [
                    Elem("TD", [(0, 3)], extra=" /A << /O /Table /ColSpan 2 >>"),
                    Elem("TD", [(0, 4)]),
                ],
            ),
            Elem("TR", [Elem("TD", [(0, 5)]), Elem("TD", [(0, 6)])]),
        ],
    )
    return _tagged(items, [Elem("Table", [head, body])])


def test_table_with_colspan() -> None:
    (table,) = [b for b in _parse(_table()).blocks if isinstance(b, Table)]
    rows = [[runs_text(c.runs) for c in r.cells] for r in table.rows]
    assert rows == [["見出1", "見出2", "見出3"], ["結合", "結合", "c"], ["縦", "x", ""]]
    assert table.has_header and table.rows[0].is_header
    assert table.rows[1].cells[1].from_merge
    assert len({len(r.cells) for r in table.rows}) == 1  # INV-01


def test_table_rowspan() -> None:
    items = [
        Text(50, 780, "縦結合", 12, mcid=0),
        Text(110, 780, "a", 12, mcid=1),
        Text(110, 760, "b", 12, mcid=2),
    ]
    rows = [
        Elem(
            "TR",
            [Elem("TD", [(0, 0)], extra=" /A << /O /Table /RowSpan 2 >>"), Elem("TD", [(0, 1)])],
        ),
        Elem("TR", [Elem("TD", [(0, 2)])]),
    ]
    (table,) = [
        b for b in _parse(_tagged(items, [Elem("Table", rows)])).blocks if isinstance(b, Table)
    ]
    assert [[runs_text(c.runs) for c in r.cells] for r in table.rows] == [
        ["縦結合", "a"],
        ["縦結合", "b"],
    ]
    assert not table.has_header


def _figure() -> bytes:
    items = [Text(110, 540, "図中の文字", 10, mcid=0), Text(110, 520, "二行目", 10, mcid=1)]
    return _tagged(items, [Elem("Figure", [(0, 0), (0, 1)], alt="構成図")])


def test_figure_alt_and_text() -> None:
    doc = _parse(_figure())
    image = next(b for b in doc.blocks if isinstance(b, Image))
    assert image.alt_text == "構成図" and image.media_ref == ""
    shape = next(b for b in doc.blocks if isinstance(b, ShapeText))
    assert shape.shape_kind == "図"
    assert [runs_text(p.runs) for p in shape.paragraphs] == ["図中の文字", "二行目"]


def test_figure_without_shapes() -> None:
    doc = _parse(_figure(), ConvertOptions(shapes=False))
    assert any(isinstance(b, Image) for b in doc.blocks)
    assert not any(isinstance(b, ShapeText) for b in doc.blocks)


def test_inline_span_joined_into_paragraph() -> None:
    items = [
        Text(50, 780, "前半", 12, mcid=0),
        Text(74, 780, "強調", 12, mcid=1),
        Text(98, 780, "後半", 12, mcid=2),
    ]
    doc = _parse(_tagged(items, [Elem("P", [(0, 0), Elem("Span", [(0, 1)]), (0, 2)])]))
    assert [runs_text(b.runs) for b in doc.blocks if isinstance(b, Paragraph)] == ["前半強調後半"]


def test_artifact_not_output_and_counted() -> None:
    # 被覆率 50% 以上になるよう、本文を Artifact より長くする (ADR-013)
    items = [
        Text(50, 820, "ヘッダー", 10, artifact="Header"),
        Text(50, 780, "本文の段落です。", 12, mcid=0),
        Text(280, 20, "1", 10, artifact="Footer"),
    ]
    doc = _parse(_tagged(items, [Elem("P", [(0, 0)])]))
    text = "".join(runs_text(b.runs) for b in doc.blocks if isinstance(b, Paragraph))
    assert text == "本文の段落です。"
    assert doc.meta.stats["headers_footers_removed"] == 2
    assert doc.meta.stats["multi_column_pages"] == 0


def test_untagged_has_no_headings_or_lists() -> None:
    page = Page(
        items=[
            Text(50, 780, "大きな文字", 24),
            Text(50, 740, "・箇条書き風", 12),
            Text(50, 726, "1. 番号風", 12),
        ]
    )
    doc = _parse(build_pdf([page]))
    assert doc.meta.pdf_structure == "untagged"
    assert not any(isinstance(b, (Heading, ListBlock)) for b in doc.blocks)
    assert all(isinstance(b, Paragraph) for b in doc.blocks)


def test_mcr_form_is_tagged() -> None:
    """MCR 辞書形式のタグ付き PDF が構造どおりに変換される (※CR-003)。"""
    data = build_pdf(
        [Page(items=[Text(50, 780, "見出し", 18, mcid=0)])],
        Elem("Document", [Elem("H1", [(0, 0)])]),
        mcr=True,
    )
    doc = _parse(data)
    assert doc.meta.pdf_structure == "tagged"
    assert isinstance(doc.blocks[0], Heading) and runs_text(doc.blocks[0].runs) == "見出し"
    assert not any("論理構造 (タグ)" in w for w in doc.warnings)


def test_incomplete_tagging_falls_back_with_warning() -> None:
    """構造が本文の一部しか覆わない PDF はタグなし + 警告 (REQ-F-111)。"""
    items = [Text(50, 780, "見", 18, mcid=0), Text(50, 700, "構造に入っていない長い本文です。", 12)]
    doc = _parse(build_pdf([Page(items=items)], Elem("Document", [Elem("H1", [(0, 0)])])))
    assert doc.meta.pdf_structure == "untagged"
    assert any("論理構造 (タグ) が本文の一部しか覆っていない" in w for w in doc.warnings)


def test_scanned_pages_warning() -> None:
    pages = [
        Page(items=[Text(50, 780, "本文", 12)]),
        Page(image=True),
        Page(image=True),
        Page(image=True),
        Page(items=[Text(50, 780, "x", 12)]),
        Page(image=True),
    ]
    doc = _parse(build_pdf(pages))
    assert any(
        w.startswith("ページ 2-4, 6 からテキストを抽出できませんでした") for w in doc.warnings
    )


def test_no_text_at_all_warning() -> None:
    doc = _parse(build_pdf([Page(image=True)]))
    assert any("テキストを抽出できませんでした (スキャン画像" in w for w in doc.warnings)
    assert doc.blocks == ()


def test_copy_restricted_warning() -> None:
    doc = _parse(encrypt_pdf(build_pdf([Page(items=[Text(50, 780, "x", 12)])]), copy_allowed=False))
    assert any("コピーを制限する権限設定" in w for w in doc.warnings)


def test_images_extract_warning() -> None:
    doc = _parse(_figure(), ConvertOptions(images=ImageMode.EXTRACT))
    assert any("PDF の画像は書き出しません" in w for w in doc.warnings)
    assert not any("PDF の画像" in w for w in _parse(_figure()).warnings)


def test_title_and_meta() -> None:
    doc = _parse(
        build_pdf([Page(items=[Text(50, 780, "x", 12)])], title="報告書", author="山田"),
        name="dir/a.pdf",
    )
    assert doc.title == "報告書" and doc.meta.title == "報告書" and doc.meta.author == "山田"
    assert doc.meta.source_file == "a.pdf"
    assert doc.meta.stats["pages"] == 1
    doc2 = _parse(build_pdf([Page(items=[Text(50, 780, "x", 12)])]), name="報告.pdf")
    assert doc2.title == "報告"
