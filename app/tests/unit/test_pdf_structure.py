"""U006-T2: 被覆率の判定と構造木の統合 (P003 §7A.3。※CR-001)。"""

from __future__ import annotations

from office2ragknowledge.pdf.backend import open_pdf
from office2ragknowledge.pdf.model import PdfChar, PdfPage, PdfSource, StructInfo
from office2ragknowledge.pdf.structure import StructNode, TextRun, build_tree, classify
from office2ragknowledge.pdf.text import text_of
from tests.helpers.make_pdf import Elem, Page, Text, build_pdf


def _source(paths: list[tuple[int, ...] | None], has_tree: bool = True) -> PdfSource:
    chars = tuple(
        PdfChar("a", i * 10.0, 0, i * 10.0 + 10, 10, 10, path) for i, path in enumerate(paths)
    )
    page = PdfPage(1, 595, 842, chars, ((0, len(chars)),) if chars else ())
    return PdfSource(pages=(page,), has_struct_tree=has_tree)


def _text(node: StructNode) -> str:
    chars: list[PdfChar] = []
    for item in node.items:
        if isinstance(item, TextRun):
            chars.extend(item.chars)
    return text_of(chars)


def test_classify() -> None:
    assert classify(_source([(0,)] * 4)) == (True, False)
    assert classify(_source([(0,), (0,), None, None])) == (True, False)  # ちょうど 50%
    assert classify(_source([(0,), None, None, None])) == (False, True)
    assert classify(_source([(0,)] * 4, has_tree=False)) == (False, False)
    assert classify(_source([])) == (False, False)


def test_classify_ignores_spaces() -> None:
    chars = (
        PdfChar("a", 0, 0, 10, 10, 10, (0,)),
        PdfChar(" ", 10, 0, 20, 10, 10, None),
        PdfChar(" ", 20, 0, 30, 10, 10, None),
    )
    page = PdfPage(1, 595, 842, chars, ((0, 3),))
    assert classify(PdfSource(pages=(page,), has_struct_tree=True)) == (True, False)


def test_paragraph_spanning_pages_is_one_node() -> None:
    pages = [
        Page(items=[Text(50, 750, "前半の", 12, mcid=0)]),
        Page(items=[Text(50, 750, "後半です", 12, mcid=0)]),
    ]
    tree = Elem("Document", [Elem("P", [(0, 0), (1, 0)])])
    roots = build_tree(open_pdf(build_pdf(pages, tree)))
    assert len(roots) == 1 and roots[0].tag == "Document"
    paragraphs = [i for i in roots[0].items if isinstance(i, StructNode)]
    assert len(paragraphs) == 1
    assert _text(paragraphs[0]) == "前半の後半です"


def test_mixed_content_order() -> None:
    pages = [
        Page(
            items=[
                Text(50, 750, "前", 12, mcid=0),
                Text(80, 750, "中", 12, mcid=1),
                Text(110, 750, "後", 12, mcid=2),
            ]
        )
    ]
    tree = Elem("Document", [Elem("P", [(0, 0), Elem("Span", [(0, 1)]), (0, 2)])])
    roots = build_tree(open_pdf(build_pdf(pages, tree)))
    para = roots[0].items[0]
    assert isinstance(para, StructNode) and para.tag == "P"
    kinds = [type(i).__name__ for i in para.items]
    assert kinds == ["TextRun", "StructNode", "TextRun"]


def test_chars_outside_structure_are_dropped() -> None:
    pages = [
        Page(items=[Text(50, 800, "Hdr", 10, artifact="Header"), Text(50, 750, "本文", 12, mcid=0)])
    ]
    roots = build_tree(open_pdf(build_pdf(pages, Elem("Document", [Elem("P", [(0, 0)])]))))
    all_text = "".join(
        c.text
        for node in roots
        for i in node.items
        if isinstance(i, StructNode)
        for t in i.items
        if isinstance(t, TextRun)
        for c in t.chars
    )
    assert all_text == "本文"


def test_missing_struct_info_falls_back() -> None:
    chars = (PdfChar("a", 0, 0, 10, 10, 10, (0, 5)),)
    page = PdfPage(1, 595, 842, chars, ((0, 1),))
    roots = build_tree(
        PdfSource(pages=(page,), struct={(0,): StructInfo("Document")}, has_struct_tree=True)
    )
    child = roots[0].items[0]
    assert isinstance(child, StructNode) and child.tag == "NonStruct"


def test_textless_figure_with_alt_is_inserted_in_order() -> None:
    pages = [Page(items=[Text(50, 780, "前", 12, mcid=0), Text(50, 700, "後", 12, mcid=1)])]
    tree = Elem(
        "Document", [Elem("P", [(0, 0)]), Elem("Figure", [], alt="写真"), Elem("P", [(0, 1)])]
    )
    roots = build_tree(open_pdf(build_pdf(pages, tree)))
    tags = [i.tag for i in roots[0].items if isinstance(i, StructNode)]
    assert tags == ["P", "Figure", "P"]
    figure = [i for i in roots[0].items if isinstance(i, StructNode)][1]
    assert figure.info.alt == "写真"


def test_textless_figure_without_alt_is_not_inserted() -> None:
    pages = [Page(items=[Text(50, 780, "前", 12, mcid=0)])]
    tree = Elem("Document", [Elem("P", [(0, 0)]), Elem("Figure", [])])
    roots = build_tree(open_pdf(build_pdf(pages, tree)))
    assert [i.tag for i in roots[0].items if isinstance(i, StructNode)] == ["P"]


def test_items_follow_k_order_not_drawing_order() -> None:
    """描画順と /K の順が異なっても /K の順に並ぶ (※CR-003。Handbook §4-15)。"""
    items = [Text(50, 760, "上にある", 12, mcid=1), Text(50, 400, "下にある", 12, mcid=0)]
    tree = Elem("Document", [Elem("P", [(0, 0)]), Elem("P", [(0, 1)])])
    roots = build_tree(open_pdf(build_pdf([Page(items=items)], tree)))
    texts = [_text(n) for n in roots[0].items if isinstance(n, StructNode)]
    assert texts == ["下にある", "上にある"]


def test_text_and_children_follow_k_order() -> None:
    items = [
        Text(80, 750, "中", 12, mcid=1),
        Text(50, 750, "前", 12, mcid=0),
        Text(110, 750, "後", 12, mcid=2),
    ]
    tree = Elem("Document", [Elem("P", [(0, 0), Elem("Span", [(0, 1)]), (0, 2)])])
    roots = build_tree(open_pdf(build_pdf([Page(items=items)], tree)))
    para = roots[0].items[0]
    assert isinstance(para, StructNode)
    order = []
    for item in para.items:
        if isinstance(item, TextRun):
            order.append(text_of(list(item.chars)))
        else:
            order.append(_text(item))
    assert order == ["前", "中", "後"]


def test_nodes_without_kid_index_keep_appearance_order() -> None:
    chars = (
        PdfChar("b", 0, 0, 10, 10, 10, (0, 1)),
        PdfChar("a", 0, 20, 10, 30, 10, (0, 0)),
    )
    page = PdfPage(1, 595, 842, chars, ((0, 2),))
    src = PdfSource(pages=(page,), struct={(0,): StructInfo("Document")}, has_struct_tree=True)
    roots = build_tree(src)
    # 子要素の経路は /K の位置を持つので、子要素どうしは /K の順に並ぶ
    assert [i.path for i in roots[0].items if isinstance(i, StructNode)] == [(0, 0), (0, 1)]
