"""U003-T2 の単体テスト: グラフのラベル抽出 (REQ-F-047)。

**数値データ (c:val) は出力しない。**
"""

from __future__ import annotations

from pathlib import Path

from office2ragknowledge.ooxml.charts import extract_chart
from office2ragknowledge.ooxml.xml_utils import NS
from office2ragknowledge.ooxml.zip_reader import SafeZipReader
from tests.helpers.make_office import zip_from_mapping

C, A, REL = NS["c"], NS["a"], NS["rel"]

RELS = f"""<?xml version="1.0"?>
<Relationships xmlns="{REL}">
  <Relationship Id="rIdChart" Type="http://x/chart" Target="../charts/chart1.xml"/>
</Relationships>"""


def chart_xml(
    title: str = "四半期別売上推移",
    series: tuple[str, ...] = ("国内", "海外"),
    categories: tuple[str, ...] = ("Q1", "Q2", "Q3", "Q4"),
    values: tuple[str, ...] = ("100", "200", "300", "400"),
) -> str:
    title_el = (
        f"<c:title><c:tx><c:rich><a:p><a:r><a:t>{title}</a:t></a:r></a:p></c:rich></c:tx></c:title>"
        if title
        else ""
    )
    cats = "".join(f"<c:pt><c:v>{c}</c:v></c:pt>" for c in categories)
    vals = "".join(f"<c:pt><c:v>{v}</c:v></c:pt>" for v in values)
    sers = ""
    for name in series:
        sers += (
            "<c:ser>"
            f"<c:tx><c:strRef><c:strCache><c:pt><c:v>{name}</c:v></c:pt>"
            "</c:strCache></c:strRef></c:tx>"
            f"<c:cat><c:strRef><c:strCache>{cats}</c:strCache></c:strRef></c:cat>"
            f"<c:val><c:numRef><c:numCache>{vals}</c:numCache></c:numRef></c:val>"
            "</c:ser>"
        )
    return (
        f'<?xml version="1.0"?><c:chartSpace xmlns:c="{C}" xmlns:a="{A}">'
        f"<c:chart>{title_el}<c:plotArea>{sers}</c:plotArea></c:chart></c:chartSpace>"
    )


def make_pkg(tmp_path: Path, chart: str) -> Path:
    return zip_from_mapping(
        tmp_path / "pkg.zip",
        {
            "ppt/slides/slide1.xml": "<sld/>",
            "ppt/slides/_rels/slide1.xml.rels": RELS,
            "ppt/charts/chart1.xml": chart,
        },
    )


def extract(tmp_path: Path, chart: str):  # type: ignore[no-untyped-def]
    with SafeZipReader(make_pkg(tmp_path, chart)) as reader:
        return extract_chart(reader, "ppt/slides/slide1.xml", "rIdChart")


# ケース1: タイトル・系列・カテゴリの3段落
def test_three_paragraphs(tmp_path: Path) -> None:
    shape = extract(tmp_path, chart_xml())
    assert shape is not None
    texts = [p.runs[0].text for p in shape.paragraphs]
    assert texts[0] == "四半期別売上推移"
    assert texts[1] == "系列: 国内, 海外"
    assert texts[2] == "カテゴリ: Q1, Q2, Q3, Q4"


# ケース2: 数値データが出力に含まれない
def test_values_are_not_extracted(tmp_path: Path) -> None:
    shape = extract(tmp_path, chart_xml(values=("9999", "8888")))
    assert shape is not None
    joined = " ".join(p.runs[0].text for p in shape.paragraphs)
    assert "9999" not in joined
    assert "8888" not in joined


# ケース3: カテゴリは最初の系列からのみ取る
def test_categories_from_first_series_only(tmp_path: Path) -> None:
    shape = extract(tmp_path, chart_xml(series=("A", "B")))
    assert shape is not None
    cat_line = next(
        p.runs[0].text for p in shape.paragraphs if p.runs[0].text.startswith("カテゴリ")
    )
    # 2系列あってもカテゴリは4件のまま (重複しない)
    assert cat_line == "カテゴリ: Q1, Q2, Q3, Q4"


# ケース4: タイトルのみ
def test_title_only(tmp_path: Path) -> None:
    shape = extract(tmp_path, chart_xml(series=(), categories=()))
    assert shape is not None
    assert len(shape.paragraphs) == 1
    assert shape.paragraphs[0].runs[0].text == "四半期別売上推移"


# ケース5: すべて空なら None
def test_empty_chart_returns_none(tmp_path: Path) -> None:
    shape = extract(tmp_path, chart_xml(title="", series=(), categories=()))
    assert shape is None


# ケース6: shape_kind が グラフ
def test_shape_kind(tmp_path: Path) -> None:
    shape = extract(tmp_path, chart_xml())
    assert shape is not None
    assert shape.shape_kind == "グラフ"


def test_missing_chart_part_returns_none(tmp_path: Path) -> None:
    path = zip_from_mapping(tmp_path / "pkg.zip", {"ppt/slides/slide1.xml": "<sld/>"})
    with SafeZipReader(path) as reader:
        assert extract_chart(reader, "ppt/slides/slide1.xml", "rIdMissing") is None
