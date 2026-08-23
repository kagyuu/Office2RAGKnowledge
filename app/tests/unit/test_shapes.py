"""U003-T1 の単体テスト: 図形テキスト抽出器 (中核機能)。

**ケース4 (mc:Choice / mc:Fallback の二重取得回避) は必須。**
P003 §1.3 の実測で特定した落とし穴であり、失敗すると利用者の最重要要求である
図形テキストがすべて2回出力される。

テストデータは **XML 文字列を直接与える** (ファイルを作らない。P006 §3.1)。
"""

from __future__ import annotations

from office2ragknowledge.ooxml.shapes import (
    EXCEL_DIALECT,
    PPTX_DIALECT,
    WORD_DIALECT,
    ShapeTextExtractor,
    classify_shape,
)
from office2ragknowledge.ooxml.xml_utils import NS, parse_xml, qn

W, MC, WPS, WPG, A, P, XDR = (
    NS["w"],
    NS["mc"],
    NS["wps"],
    NS["wpg"],
    NS["a"],
    NS["p"],
    NS["xdr"],
)

NSDECL = (
    f'xmlns:w="{W}" xmlns:mc="{MC}" xmlns:wps="{WPS}" xmlns:wpg="{WPG}" '
    f'xmlns:a="{A}" xmlns:p="{P}" xmlns:xdr="{XDR}" '
    'xmlns:v="urn:schemas-microsoft-com:vml"'
)


def word_shape(text_paragraphs: list[str], *, name: str = "テキスト ボックス 1") -> str:
    paras = "".join(f"<w:p><w:r><w:t>{t}</w:t></w:r></w:p>" for t in text_paragraphs)
    return f"""
      <wps:wsp>
        <wps:cNvPr name="{name}"/>
        <wps:cNvSpPr txBox="1"/>
        <wps:txbx><w:txbxContent>{paras}</w:txbxContent></wps:txbx>
      </wps:wsp>
    """


def wrap(inner: str) -> object:
    return parse_xml(f"<root {NSDECL}>{inner}</root>".encode())


# ケース1: 単独の図形
def test_single_shape() -> None:
    root = wrap(word_shape(["図形のテキスト"]))
    shapes, count = ShapeTextExtractor(WORD_DIALECT).extract(root)  # type: ignore[arg-type]
    assert len(shapes) == 1
    assert count == 1
    assert shapes[0].paragraphs[0].runs[0].text == "図形のテキスト"


# ケース2: テキストを持たない図形は ShapeText を作らない (INV-05) が総数には数える
def test_shape_without_text_is_counted_but_not_emitted() -> None:
    root = wrap(
        '<wps:wsp><wps:cNvPr name="空"/><wps:cNvSpPr/>'
        "<wps:txbx><w:txbxContent><w:p/></w:txbxContent></wps:txbx></wps:wsp>"
    )
    shapes, count = ShapeTextExtractor(WORD_DIALECT).extract(root)  # type: ignore[arg-type]
    assert shapes == []
    assert count == 1


# ケース3: グループ図形 (2階層) の再帰と group_path
def test_nested_group_recursion() -> None:
    inner = word_shape(["内側のテキスト"])
    xml = f"""
      <wpg:wgp>
        <wps:cNvPr name="外グループ"/>
        <wpg:wgp>
          <wps:cNvPr name="内グループ"/>
          {inner}
        </wpg:wgp>
      </wpg:wgp>
    """
    shapes, count = ShapeTextExtractor(WORD_DIALECT).extract(wrap(xml))  # type: ignore[arg-type]
    assert len(shapes) == 1
    assert shapes[0].paragraphs[0].runs[0].text == "内側のテキスト"
    assert shapes[0].group_path == ("外グループ", "内グループ")


# ケース4 (必須): mc:Choice と mc:Fallback に同じ内容があっても1件だけ返る
def test_alternate_content_is_not_double_counted() -> None:
    """P003 §1.3 の実測を再現する。

    素朴に ``.//w:txbxContent`` を全件拾うと、同じテキストが2件返る。
    """
    xml = f"""
      <w:p>
        <w:r>
          <mc:AlternateContent>
            <mc:Choice Requires="wps">
              {word_shape(["図形の1段落目", "図形の2段落目"])}
            </mc:Choice>
            <mc:Fallback>
              <w:pict><v:shape><v:textbox><w:txbxContent>
                <w:p><w:r><w:t>図形の1段落目</w:t></w:r></w:p>
                <w:p><w:r><w:t>図形の2段落目</w:t></w:r></w:p>
              </w:txbxContent></v:textbox></v:shape></w:pict>
            </mc:Fallback>
          </mc:AlternateContent>
        </w:r>
      </w:p>
    """
    shapes, _ = ShapeTextExtractor(WORD_DIALECT).extract(wrap(xml))  # type: ignore[arg-type]
    assert len(shapes) == 1, f"図形テキストが二重に抽出されています: {len(shapes)} 件"
    texts = [p.runs[0].text for p in shapes[0].paragraphs]
    assert texts == ["図形の1段落目", "図形の2段落目"]


# ケース5: mc:Choice が無ければ mc:Fallback を辿る
def test_fallback_is_used_when_no_choice() -> None:
    xml = f"""
      <mc:AlternateContent>
        <mc:Fallback>{word_shape(["代替のテキスト"])}</mc:Fallback>
      </mc:AlternateContent>
    """
    shapes, _ = ShapeTextExtractor(WORD_DIALECT).extract(wrap(xml))  # type: ignore[arg-type]
    assert len(shapes) == 1
    assert shapes[0].paragraphs[0].runs[0].text == "代替のテキスト"


# ケース6: Requires="wps" の Choice が優先される
def test_choice_with_known_requires_is_preferred() -> None:
    xml = f"""
      <mc:AlternateContent>
        <mc:Choice Requires="unknown2030">{word_shape(["未知の拡張"])}</mc:Choice>
        <mc:Choice Requires="wps">{word_shape(["既知の拡張"])}</mc:Choice>
      </mc:AlternateContent>
    """
    shapes, _ = ShapeTextExtractor(WORD_DIALECT).extract(wrap(xml))  # type: ignore[arg-type]
    assert len(shapes) == 1
    assert shapes[0].paragraphs[0].runs[0].text == "既知の拡張"


# ケース7: 複数段落が段落ごとに分かれる (REQ-F-040)
def test_multiple_paragraphs_are_kept_separate() -> None:
    root = wrap(word_shape(["1段落目", "2段落目", "3段落目"]))
    shapes, _ = ShapeTextExtractor(WORD_DIALECT).extract(root)  # type: ignore[arg-type]
    texts = [p.runs[0].text for p in shapes[0].paragraphs]
    assert texts == ["1段落目", "2段落目", "3段落目"]


# ケース8: 図形内の表 (REQ-F-039)
def test_table_inside_shape() -> None:
    xml = """
      <p:sp>
        <p:cNvPr name="表入り図形"/>
        <p:txBody><a:p><a:r><a:t>表の説明</a:t></a:r></a:p></p:txBody>
        <a:tbl>
          <a:tr><a:tc><a:t>A</a:t></a:tc><a:tc><a:t>B</a:t></a:tc></a:tr>
          <a:tr><a:tc><a:t>1</a:t></a:tc><a:tc><a:t>2</a:t></a:tc></a:tr>
        </a:tbl>
      </p:sp>
    """
    shapes, _ = ShapeTextExtractor(PPTX_DIALECT).extract(wrap(xml))  # type: ignore[arg-type]
    assert len(shapes) == 1
    assert len(shapes[0].tables) == 1
    table = shapes[0].tables[0]
    assert len(table.rows) == 2
    assert [c.runs[0].text for c in table.rows[0].cells] == ["A", "B"]
    assert table.rows[0].is_header is True


# ケース9: 図形種別の分類
def test_classify_shape() -> None:
    def kind(preset: str) -> str:
        el = parse_xml(f'<p:sp {NSDECL}><a:prstGeom prst="{preset}"/></p:sp>'.encode())
        return classify_shape(el, PPTX_DIALECT)

    assert kind("rect") == "四角形"
    assert kind("roundRect") == "四角形"
    assert kind("ellipse") == "円・楕円"
    assert kind("triangle") == "三角形"
    assert kind("rightArrow") == "矢印"
    assert kind("wedgeRectCallout") == "吹き出し"
    assert kind("someUnknownPreset") == "図形"


def test_classify_textbox() -> None:
    el = parse_xml(f'<wps:wsp {NSDECL}><wps:cNvSpPr txBox="1"/></wps:wsp>'.encode())
    assert classify_shape(el, WORD_DIALECT) == "テキストボックス"


# ケース10: 図形名
def test_shape_name() -> None:
    root = wrap(word_shape(["text"], name="業務フロー図"))
    shapes, _ = ShapeTextExtractor(WORD_DIALECT).extract(root)  # type: ignore[arg-type]
    assert shapes[0].shape_name == "業務フロー図"


def test_shape_name_is_none_when_absent() -> None:
    xml = (
        "<wps:wsp><wps:cNvSpPr/>"
        "<wps:txbx><w:txbxContent><w:p><w:r><w:t>t</w:t></w:r></w:p>"
        "</w:txbxContent></wps:txbx></wps:wsp>"
    )
    shapes, _ = ShapeTextExtractor(WORD_DIALECT).extract(wrap(xml))  # type: ignore[arg-type]
    assert shapes[0].shape_name is None


# ケース11: 3方言それぞれで抽出できる
def test_all_three_dialects() -> None:
    excel_xml = (
        '<xdr:sp><xdr:cNvPr name="s"/><xdr:txBody>'
        "<a:p><a:r><a:t>Excelの図形</a:t></a:r></a:p></xdr:txBody></xdr:sp>"
    )
    pptx_xml = (
        '<p:sp><p:cNvPr name="s"/><p:txBody>'
        "<a:p><a:r><a:t>PowerPointの図形</a:t></a:r></a:p></p:txBody></p:sp>"
    )
    word, _ = ShapeTextExtractor(WORD_DIALECT).extract(wrap(word_shape(["Wordの図形"])))  # type: ignore[arg-type]
    excel, _ = ShapeTextExtractor(EXCEL_DIALECT).extract(wrap(excel_xml))  # type: ignore[arg-type]
    pptx, _ = ShapeTextExtractor(PPTX_DIALECT).extract(wrap(pptx_xml))  # type: ignore[arg-type]
    assert word[0].paragraphs[0].runs[0].text == "Wordの図形"
    assert excel[0].paragraphs[0].runs[0].text == "Excelの図形"
    assert pptx[0].paragraphs[0].runs[0].text == "PowerPointの図形"


# ケース12: 深い入れ子で無限再帰にならない
def test_deep_nesting_is_bounded() -> None:
    xml = word_shape(["深いテキスト"])
    for _ in range(60):
        xml = f"<wpg:wgp><wps:cNvPr name='g'/>{xml}</wpg:wgp>"
    shapes, _ = ShapeTextExtractor(WORD_DIALECT).extract(wrap(xml))  # type: ignore[arg-type]
    # 上限で打ち切られるため抽出されない。例外にならないことが要点。
    assert isinstance(shapes, list)


# ケース13: 空段落が含まれない
def test_empty_paragraphs_are_skipped() -> None:
    xml = (
        '<wps:wsp><wps:cNvPr name="s"/><wps:txbx><w:txbxContent>'
        "<w:p><w:r><w:t>あり</w:t></w:r></w:p>"
        "<w:p/>"
        "<w:p><w:r><w:t>あり2</w:t></w:r></w:p>"
        "</w:txbxContent></wps:txbx></wps:wsp>"
    )
    shapes, _ = ShapeTextExtractor(WORD_DIALECT).extract(wrap(xml))  # type: ignore[arg-type]
    assert len(shapes[0].paragraphs) == 2


# ケース14: anchor は常に None (呼び出し元が設定する)
def test_anchor_is_none_by_default() -> None:
    root = wrap(word_shape(["text"]))
    shapes, _ = ShapeTextExtractor(WORD_DIALECT).extract(root)  # type: ignore[arg-type]
    assert shapes[0].anchor is None


def test_paragraph_level_from_ppr() -> None:
    xml = (
        '<p:sp><p:cNvPr name="s"/><p:txBody>'
        '<a:p><a:pPr lvl="0"/><a:r><a:t>親</a:t></a:r></a:p>'
        '<a:p><a:pPr lvl="1"/><a:r><a:t>子</a:t></a:r></a:p>'
        "</p:txBody></p:sp>"
    )
    shapes, _ = ShapeTextExtractor(PPTX_DIALECT).extract(wrap(xml))  # type: ignore[arg-type]
    assert [p.level for p in shapes[0].paragraphs] == [0, 1]


def test_qn_is_used_consistently() -> None:
    """名前空間の綴り違いが無いことの回帰テスト。"""
    assert qn("w:txbxContent") == f"{{{W}}}txbxContent"
    assert qn("xdr:txBody") == f"{{{XDR}}}txBody"
