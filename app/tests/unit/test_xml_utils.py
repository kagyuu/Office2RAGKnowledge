"""U001-T4 の単体テスト: 安全な XML パース。

セキュリティのケース (XXE・十億の笑い) は REQ-NF-007 に直結する。
"""

from __future__ import annotations

import pytest

from office2ragknowledge.errors import CorruptedFileError
from office2ragknowledge.ooxml.xml_utils import NS, iter_text, local_name, parse_xml, qn
from tests.helpers.make_malicious import XXE_XML, billion_laughs_xml


# ケース1: qn が正しい {URI}tag を返す
def test_qn_expands_prefix() -> None:
    assert qn("w:p") == f"{{{NS['w']}}}p"
    assert qn("a:t") == f"{{{NS['a']}}}t"


def test_qn_rejects_unknown_prefix() -> None:
    with pytest.raises(KeyError):
        qn("zzz:tag")


# ケース2: 正常な XML が解析できる
def test_parse_normal_xml() -> None:
    root = parse_xml(b'<?xml version="1.0"?><root><child>text</child></root>')
    assert local_name(root) == "root"
    assert root[0].text == "text"


# ケース3: XXE の実体が展開されない (REQ-NF-007)
def test_xxe_entity_is_not_resolved() -> None:
    try:
        root = parse_xml(XXE_XML)
    except CorruptedFileError:
        return  # 解析自体を拒否するのも正しい防御
    text = "".join(root.itertext())
    assert "root:" not in text
    assert "/bin/" not in text


# ケース4: 十億の笑いでメモリが爆発しない
def test_billion_laughs_does_not_expand() -> None:
    data = billion_laughs_xml(depth=9)
    try:
        root = parse_xml(data)
    except CorruptedFileError:
        return
    text = "".join(root.itertext())
    # 実体が展開されていれば 10^8 文字規模になる
    assert len(text) < 10_000


# ケース5: 壊れた XML が CorruptedFileError になる
def test_broken_xml_raises_corrupted() -> None:
    with pytest.raises(CorruptedFileError):
        parse_xml(b"<root><unclosed>")


# ケース6: local_name が名前空間を除去する
def test_local_name_strips_namespace() -> None:
    root = parse_xml(f'<w:p xmlns:w="{NS["w"]}"/>'.encode())
    assert local_name(root) == "p"


def test_iter_text_concatenates() -> None:
    xml = f'<w:p xmlns:w="{NS["w"]}"><w:r><w:t>あ</w:t></w:r><w:r><w:t>い</w:t></w:r></w:p>'
    root = parse_xml(xml.encode())
    assert iter_text(root, "w:t") == "あい"
