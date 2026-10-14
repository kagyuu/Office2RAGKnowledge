"""U008-T1: 近接する矩形のまとめ (pdf/drawings.py。※CR-003)。"""

from __future__ import annotations

from office2ragknowledge.pdf.drawings import cluster_rects


def test_overlapping_rects_merge() -> None:
    assert cluster_rects([(0, 0, 10, 10), (5, 5, 20, 20)]) == [(0, 0, 20, 20)]


def test_near_rects_merge_within_tolerance() -> None:
    assert cluster_rects([(0, 0, 10, 10), (11.5, 0, 20, 10)]) == [(0, 0, 20, 10)]


def test_far_rects_stay_separate() -> None:
    assert cluster_rects([(0, 0, 10, 10), (30, 0, 40, 10)]) == [(0, 0, 10, 10), (30, 0, 40, 10)]


def test_chain_merges_transitively() -> None:
    rects = [(0, 0, 10, 10), (40, 0, 50, 10), (9, 0, 41, 2)]  # A-C は離れているが B でつながる
    assert cluster_rects(rects) == [(0, 0, 50, 10)]


def test_table_grid_lines_merge() -> None:
    lines = [(0, y, 100, y) for y in (0, 10, 20)] + [(x, 0, x, 20) for x in (0, 50, 100)]
    assert cluster_rects(lines) == [(0, 0, 100, 20)]


def test_empty() -> None:
    assert cluster_rects([]) == []


def test_order_independent() -> None:
    rects = [(0, 0, 10, 10), (30, 30, 40, 40), (5, 5, 12, 12), (100, 0, 110, 5)]
    assert cluster_rects(rects) == cluster_rects(list(reversed(rects)))
    assert cluster_rects(rects) == [(0, 0, 12, 12), (100, 0, 110, 5), (30, 30, 40, 40)]
