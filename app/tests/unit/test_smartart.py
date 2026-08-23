"""U003-T2 の単体テスト: SmartArt のテキスト抽出。

**データモデル側のみを読む** (ADR-006)。描画結果側にも同じテキストがあるが、
両方読むと二重出力になる。
"""

from __future__ import annotations

from pathlib import Path

from office2ragknowledge.ooxml.smartart import extract_smartart
from office2ragknowledge.ooxml.xml_utils import NS
from office2ragknowledge.ooxml.zip_reader import SafeZipReader
from tests.helpers.make_office import zip_from_mapping

DGM, A, R, REL = NS["dgm"], NS["a"], NS["r"], NS["rel"]

RELS = f"""<?xml version="1.0"?>
<Relationships xmlns="{REL}">
  <Relationship Id="rIdDm" Type="http://x/diagramData" Target="../diagrams/data1.xml"/>
  <Relationship Id="rIdDrawing" Type="http://x/diagramDrawing" Target="../diagrams/drawing1.xml"/>
</Relationships>"""


def data_xml(points: list[tuple[str, str, str]], connections: list[tuple[str, str]]) -> str:
    """(modelId, type, text) と (親, 子) から dataN.xml を作る。"""
    pts = "".join(
        f'<dgm:pt modelId="{mid}" type="{ptype}">'
        f"<dgm:t><a:p><a:r><a:t>{text}</a:t></a:r></a:p></dgm:t></dgm:pt>"
        for mid, ptype, text in points
    )
    cxns = "".join(
        f'<dgm:cxn modelId="c{i}" type="parOf" srcId="{src}" destId="{dst}"/>'
        for i, (src, dst) in enumerate(connections)
    )
    return (
        f'<?xml version="1.0"?><dgm:dataModel xmlns:dgm="{DGM}" xmlns:a="{A}">'
        f"<dgm:ptLst>{pts}</dgm:ptLst><dgm:cxnLst>{cxns}</dgm:cxnLst></dgm:dataModel>"
    )


DRAWING_XML = (
    f'<?xml version="1.0"?><dgm:drawing xmlns:dgm="{DGM}" xmlns:a="{A}">'
    "<a:p><a:r><a:t>計画</a:t></a:r></a:p>"
    "<a:p><a:r><a:t>実行</a:t></a:r></a:p>"
    "</dgm:drawing>"
)


def make_pkg(tmp_path: Path, data: str) -> Path:
    return zip_from_mapping(
        tmp_path / "pkg.zip",
        {
            "ppt/slides/slide1.xml": "<sld/>",
            "ppt/slides/_rels/slide1.xml.rels": RELS,
            "ppt/diagrams/data1.xml": data,
            "ppt/diagrams/drawing1.xml": DRAWING_XML,
        },
    )


# ケース1: フラットな3ノード
def test_flat_nodes(tmp_path: Path) -> None:
    data = data_xml([("n1", "node", "計画"), ("n2", "node", "実行"), ("n3", "node", "評価")], [])
    with SafeZipReader(make_pkg(tmp_path, data)) as reader:
        shape = extract_smartart(reader, "ppt/slides/slide1.xml", "rIdDm")
    assert shape is not None
    assert shape.shape_kind == "SmartArt"
    assert [p.runs[0].text for p in shape.paragraphs] == ["計画", "実行", "評価"]
    assert all(p.level == 0 for p in shape.paragraphs)


# ケース2: 親子関係が level に反映される
def test_hierarchy_levels(tmp_path: Path) -> None:
    data = data_xml(
        [("n1", "node", "親"), ("n2", "node", "子"), ("n3", "node", "孫")],
        [("n1", "n2"), ("n2", "n3")],
    )
    with SafeZipReader(make_pkg(tmp_path, data)) as reader:
        shape = extract_smartart(reader, "ppt/slides/slide1.xml", "rIdDm")
    assert shape is not None
    assert [(p.runs[0].text, p.level) for p in shape.paragraphs] == [
        ("親", 0),
        ("子", 1),
        ("孫", 2),
    ]


# ケース3: type="pres" が除外される
def test_pres_nodes_are_excluded(tmp_path: Path) -> None:
    data = data_xml([("n1", "node", "実データ"), ("p1", "pres", "表示専用")], [])
    with SafeZipReader(make_pkg(tmp_path, data)) as reader:
        shape = extract_smartart(reader, "ppt/slides/slide1.xml", "rIdDm")
    assert shape is not None
    texts = [p.runs[0].text for p in shape.paragraphs]
    assert texts == ["実データ"]
    assert "表示専用" not in texts


# ケース4: drawing 側にも同じテキストがあるが二重に抽出されない
def test_drawing_part_is_not_read(tmp_path: Path) -> None:
    data = data_xml([("n1", "node", "計画"), ("n2", "node", "実行")], [])
    with SafeZipReader(make_pkg(tmp_path, data)) as reader:
        shape = extract_smartart(reader, "ppt/slides/slide1.xml", "rIdDm")
    assert shape is not None
    texts = [p.runs[0].text for p in shape.paragraphs]
    assert texts.count("計画") == 1, "描画結果側も読んでいます (二重出力)"
    assert texts.count("実行") == 1


# ケース5: cxnLst が無くても例外にならず level=0
def test_no_connections_falls_back_to_flat(tmp_path: Path) -> None:
    data = (
        f'<?xml version="1.0"?><dgm:dataModel xmlns:dgm="{DGM}" xmlns:a="{A}">'
        '<dgm:ptLst><dgm:pt modelId="n1" type="node">'
        "<dgm:t><a:p><a:r><a:t>単独</a:t></a:r></a:p></dgm:t></dgm:pt></dgm:ptLst>"
        "</dgm:dataModel>"
    )
    with SafeZipReader(make_pkg(tmp_path, data)) as reader:
        shape = extract_smartart(reader, "ppt/slides/slide1.xml", "rIdDm")
    assert shape is not None
    assert shape.paragraphs[0].level == 0


# ケース6: ノードの順序が ptLst の出現順を保つ
def test_node_order_is_preserved(tmp_path: Path) -> None:
    data = data_xml([("n3", "node", "三"), ("n1", "node", "一"), ("n2", "node", "二")], [])
    with SafeZipReader(make_pkg(tmp_path, data)) as reader:
        shape = extract_smartart(reader, "ppt/slides/slide1.xml", "rIdDm")
    assert shape is not None
    assert [p.runs[0].text for p in shape.paragraphs] == ["三", "一", "二"]


# ケース7: テキストが無ければ None
def test_no_text_returns_none(tmp_path: Path) -> None:
    data = data_xml([("n1", "node", "")], [])
    with SafeZipReader(make_pkg(tmp_path, data)) as reader:
        shape = extract_smartart(reader, "ppt/slides/slide1.xml", "rIdDm")
    assert shape is None


# ケース8: shape_kind が SmartArt
def test_shape_kind(tmp_path: Path) -> None:
    data = data_xml([("n1", "node", "text")], [])
    with SafeZipReader(make_pkg(tmp_path, data)) as reader:
        shape = extract_smartart(reader, "ppt/slides/slide1.xml", "rIdDm")
    assert shape is not None
    assert shape.shape_kind == "SmartArt"


def test_missing_part_returns_none(tmp_path: Path) -> None:
    path = zip_from_mapping(tmp_path / "pkg.zip", {"ppt/slides/slide1.xml": "<sld/>"})
    with SafeZipReader(path) as reader:
        assert extract_smartart(reader, "ppt/slides/slide1.xml", "rIdMissing") is None
