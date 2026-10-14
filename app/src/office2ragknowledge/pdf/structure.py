"""タグ付きか否かの判定と、文書全体の構造木の統合 (P003 §7A.3。※CR-001)。

PDF の内容はページごとに読まれる。複数ページにまたがる要素は各ページに同じ経路で
現れるため、**経路で要素を同定して1つのノードにまとめる** (ArchitectureHandbook
§4-9)。ノード内の子要素とテキストは、最後に ``/K`` 配列の順に並べ直す (※CR-003。
文字は内容ストリームの描画順に届くため。Handbook §4-15)。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .model import PdfChar, PdfSource, StructInfo, StructPath

__all__ = [
    "MIN_COVERAGE",
    "StructNode",
    "TextRun",
    "build_tree",
    "classify",
    "coverage_counts",
]

#: タグ付きとして扱う本文の被覆率の下限 (ADR-013)。
MIN_COVERAGE = 0.5


@dataclass(frozen=True, slots=True)
class TextRun:
    """構造要素の中の、連続する文字の並び。"""

    chars: tuple[PdfChar, ...]


@dataclass(slots=True)
class StructNode:
    """統合済みの構造要素。``items`` は子要素とテキストを出現順に持つ。"""

    path: StructPath
    info: StructInfo
    items: list[StructNode | TextRun] = field(default_factory=list)

    @property
    def tag(self) -> str:
        return self.info.tag


def coverage_counts(source: PdfSource) -> tuple[int, int]:
    """(空白以外の文字数, そのうち構造要素に属する文字数) を返す。"""
    total = 0
    covered = 0
    for page in source.pages:
        for ch in page.chars:
            if ch.text.isspace():
                continue
            total += 1
            if ch.path is not None:
                covered += 1
    return total, covered


def classify(source: PdfSource) -> tuple[bool, bool]:
    """タグ付きとして扱うかを判定する。

    Returns:
        (タグ付きか, 構造ツリーはあるが被覆率が足りずタグなしに切り替えたか)
    """
    if not source.has_struct_tree:
        return False, False
    total, covered = coverage_counts(source)
    if total == 0:
        return False, False
    if covered / total < MIN_COVERAGE:
        return False, True
    return True, False


def build_tree(source: PdfSource) -> list[StructNode]:
    """ページごとの構造断片を統合し、ルート要素の並びを返す。

    構造の外の文字 (``path is None``) は木に入れない。
    """
    nodes: dict[StructPath, StructNode] = {}
    roots: list[StructNode] = []

    def node_for(path: StructPath) -> StructNode:
        existing = nodes.get(path)
        if existing is not None:
            return existing
        parent = node_for(path[:-1]) if len(path) > 1 else None
        info = source.struct.get(path) or StructInfo(tag="NonStruct")
        node = StructNode(path=path, info=info)
        nodes[path] = node
        (parent.items if parent is not None else roots).append(node)
        return node

    for page in source.pages:
        for start, end in page.segments:
            group: list[PdfChar] = []
            group_key: tuple[StructPath | None, int | None] = (None, None)
            for ch in page.chars[start:end]:
                key = (ch.path, ch.kid_index)
                if group and key != group_key:
                    _append(node_for, group_key[0], group)
                    group = []
                group.append(ch)
                group_key = key
            _append(node_for, group_key[0], group)
    _insert_textless_figures(source, nodes, roots, node_for)
    _sort_by_k_order(roots)
    return roots


def _item_position(item: StructNode | TextRun) -> int | None:
    if isinstance(item, StructNode):
        return item.path[-1]
    return item.chars[0].kid_index if item.chars else None


def _sort_by_k_order(items: list[Any]) -> None:
    """各ノードの ``items`` を ``/K`` 配列の順に並べ直す (P003 §7A.3)。

    ``kid_index`` を持たないテキストがあるノードは並べ直さない (出現順のまま)。
    同じ位置のもの (ページをまたぐ同じ MCID 等) は出現順を保つ (安定な並べ替え)。
    """
    positions = [_item_position(i) for i in items]
    if all(p is not None for p in positions):
        order = sorted(range(len(items)), key=lambda i: positions[i] or 0)
        items[:] = [items[i] for i in order]
    for item in items:
        if isinstance(item, StructNode):
            _sort_by_k_order(item.items)


#: テキストを持たなくても出力に寄与する要素 (代替テキストを持つ図)。
_TEXTLESS_TAGS = frozenset({"Figure", "Formula"})


def _insert_textless_figures(
    source: PdfSource,
    nodes: dict[StructPath, StructNode],
    roots: list[StructNode],
    node_for: Callable[[StructPath], StructNode],
) -> None:
    """画像だけの図 (テキストを持たない) を、代替テキストのために木へ加える。

    ライブラリの構造化テキストは文字を持たない要素を返さないため、自前で辿った
    構造ツリーの属性から補う。兄弟の中の位置は ``/K`` 配列内の位置で決める。
    """
    for path in sorted(source.struct):
        info = source.struct[path]
        if path in nodes or info.tag not in _TEXTLESS_TAGS or not info.alt:
            continue
        parent = node_for(path[:-1]) if len(path) > 1 else None
        siblings = parent.items if parent is not None else roots
        node = StructNode(path=path, info=info)
        nodes[path] = node
        position = next(
            (
                i
                for i, item in enumerate(siblings)
                if isinstance(item, StructNode) and item.path[-1] > path[-1]
            ),
            len(siblings),
        )
        siblings.insert(position, node)


def _append(
    node_for: Callable[[StructPath], StructNode], path: StructPath | None, group: list[PdfChar]
) -> None:
    if path is None or not group:
        return
    node_for(path).items.append(TextRun(tuple(group)))
