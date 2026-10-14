"""近接するベクター図形の矩形をまとめる (P003 §7A.2 手順5。※CR-003)。

タグなし PDF の図領域 (REQ-F-117) の候補を作る。罫線・枠・図形の部品は細かい
パスの集まりとして描かれるため、重なる、または近接する矩形を推移的にまとめて
1つの外接矩形にする。PDF ライブラリに依存しない。
"""

from __future__ import annotations

from collections.abc import Sequence

from .model import Rect

__all__ = ["cluster_rects"]


def _near(a: Rect, b: Rect, tolerance: float) -> bool:
    return not (
        a[2] + tolerance < b[0]
        or b[2] + tolerance < a[0]
        or a[3] + tolerance < b[1]
        or b[3] + tolerance < a[1]
    )


def cluster_rects(rects: Sequence[Rect], tolerance: float = 2.0) -> list[Rect]:
    """重なる・``tolerance`` 以内に近接する矩形をまとめ、外接矩形の一覧を返す。

    結果は (top, x0, bottom, x1) の順に並べる (入力の順序によらず同じ結果になる)。
    """
    if not rects:
        return []
    items = sorted(rects, key=lambda r: (r[0], r[1], r[2], r[3]))
    parent = list(range(len(items)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    # x0 の昇順に掃き出し、x 方向に重なりうる範囲だけを比べる
    for i, a in enumerate(items):
        for j in range(i + 1, len(items)):
            b = items[j]
            if b[0] > a[2] + tolerance:
                break
            if _near(a, b, tolerance):
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[max(ri, rj)] = min(ri, rj)
    groups: dict[int, list[Rect]] = {}
    for i, r in enumerate(items):
        groups.setdefault(find(i), []).append(r)
    merged = [
        (
            min(r[0] for r in group),
            min(r[1] for r in group),
            max(r[2] for r in group),
            max(r[3] for r in group),
        )
        for group in groups.values()
    ]
    # まとめた結果どうしが新たに近接する場合 (外接矩形が広がったため) は繰り返す
    if len(merged) < len(rects) and any(
        _near(a, b, tolerance) for i, a in enumerate(merged) for b in merged[i + 1 :]
    ):
        return cluster_rects(merged, tolerance)
    return sorted(merged, key=lambda r: (r[1], r[0], r[3], r[2]))
