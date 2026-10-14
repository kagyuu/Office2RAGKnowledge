"""結合テスト・受け入れテストで共有するサンプル PDF (T006 / A006。※CR-001・CR-002)。

文字幅は 1em (テスト用フォントの既定幅) なので、12pt の文字は 12pt 幅になる。
座標 ``y`` は PDF の座標系 (ページ下端が 0)。A4 縦 (595 x 842)。
"""

from __future__ import annotations

from tests.helpers.make_pdf import Elem, Page, Text, build_pdf, encrypt_pdf

__all__ = [
    "LEFT_LINES",
    "RIGHT_LINES",
    "broken_pdf",
    "copy_restricted_pdf",
    "locked_pdf",
    "reading_order_pdf",
    "scanned_page_pdf",
    "single_page_pdf",
    "single_column_pdf",
    "tagged_report_pdf",
    "two_column_report_pdf",
]

LEFT_LINES = [f"左の段の{i}行目は段の幅いっぱいです" for i in range(1, 6)]
RIGHT_LINES = [f"右の段の{i}行目も段の幅いっぱいです" for i in range(1, 6)]


def tagged_report_pdf() -> bytes:
    """タグ付き報告書 (T006 の使用データ)。2ページ、各ページに Artifact のヘッダー・フッター。"""
    p1 = [
        Text(50, 815, "報告書 ヘッダー", 9, artifact="Header"),
        Text(50, 770, "第1章 概要", 18, mcid=0),
        Text(50, 740, "本章では、PDF を RAG 向けの Markdown に", 12, mcid=1),
        Text(50, 726, "変換する方法を説明します。", 12, mcid=18),
        Text(50, 690, "1.1 背景", 14, mcid=2),
        Text(70, 660, "項目A", 12, mcid=3),
        Text(90, 645, "子項目A-1", 12, mcid=4),
        Text(110, 630, "孫項目A-1-a", 12, mcid=5),
        Text(70, 615, "項目B", 12, mcid=6),
        Text(50, 580, "区分", 12, mcid=7),
        Text(170, 580, "内容", 12, mcid=8),
        Text(290, 580, "備考", 12, mcid=9),
        Text(50, 565, "結合したセル", 12, mcid=10),
        Text(290, 565, "注", 12, mcid=11),
        Text(50, 550, "通常", 12, mcid=12),
        Text(170, 550, "値", 12, mcid=13),
        Text(290, 550, "なし", 12, mcid=14),
        Text(110, 490, "構成図の中の文字", 10, mcid=15),
        Text(50, 420, "1.1.1 詳細", 12, mcid=16),
        Text(50, 400, "この段落は次のページへ", 12, mcid=17),
        Text(280, 25, "1", 9, artifact="Footer"),
    ]
    p2 = [
        Text(50, 815, "報告書 ヘッダー", 9, artifact="Header"),
        Text(50, 770, "続いています。", 12, mcid=0),
        Text(280, 25, "2", 9, artifact="Footer"),
    ]

    def li(mcid: int, nested: list[Elem]) -> Elem:
        return Elem("LI", [Elem("LBody", [(0, mcid), *nested])])

    nested = Elem("L", [li(4, [Elem("L", [li(5, [])])])])
    table = Elem(
        "Table",
        [
            Elem("THead", [Elem("TR", [Elem("TH", [(0, m)]) for m in (7, 8, 9)])]),
            Elem(
                "TBody",
                [
                    Elem(
                        "TR",
                        [
                            Elem("TD", [(0, 10)], extra=" /A << /O /Table /ColSpan 2 >>"),
                            Elem("TD", [(0, 11)]),
                        ],
                    ),
                    Elem("TR", [Elem("TD", [(0, m)]) for m in (12, 13, 14)]),
                ],
            ),
        ],
    )
    tree = Elem(
        "Document",
        [
            Elem("H1", [(0, 0)]),
            Elem("P", [(0, 1), (0, 18)]),
            Elem("H2", [(0, 2)]),
            Elem("L", [li(3, [nested]), li(6, [])]),
            table,
            Elem("Figure", [(0, 15)], alt="システム構成図"),
            Elem("H3", [(0, 16)]),
            Elem("P", [(0, 17), (1, 0)]),
        ],
    )
    return build_pdf(
        [Page(items=p1, rects=[(100, 470, 200, 50)]), Page(items=p2)],
        tree,
        title="PDF変換の報告書",
        author="山田太郎",
    )


def two_column_report_pdf() -> bytes:
    """タグなし3ページ。上端に文書名、下端に ``- N -``。1ページ目は全幅の表題 + 2段組み。"""
    pages = []
    for n in range(1, 4):
        items = [Text(50, 815, "社外秘 技術報告書", 9), Text(280, 25, f"- {n} -", 9)]
        rects: list[tuple[float, float, float, float]] = []
        if n == 1:
            items.append(Text(150, 760, "段組みの報告書の表題", 20))
            for i, (left, right) in enumerate(zip(LEFT_LINES, RIGHT_LINES, strict=True)):
                y = 720 - 14 * i
                items.append(Text(50, y, left, 12))
                items.append(Text(320, y, right, 12))
        elif n == 2:
            items.append(Text(50, 740, "2ページ目の本文です。", 12))
            items.append(Text(110, 640, "図の一行目", 10))
            items.append(Text(110, 625, "図の二行目", 10))
            rects.append((100, 600, 200, 70))
        else:
            items.append(Text(50, 740, "3ページ目の本文です。", 12))
        pages.append(Page(items=items, rects=rects))
    return build_pdf(pages, title="技術報告書")


def single_page_pdf() -> bytes:
    """タグなし1ページ。上端・下端にもテキストがある (除去されてはならない)。"""
    items = [
        Text(50, 815, "一枚ものの上端", 9),
        Text(50, 760, "本文です。", 12),
        Text(280, 25, "- 1 -", 9),
    ]
    return build_pdf([Page(items=items)])


def single_column_pdf() -> bytes:
    """タグなし1段組み。"""
    items = [
        Text(50, 760 - 14 * i, f"1段組みの{i}行目の文章で、幅いっぱいに書かれています。", 12)
        for i in range(5)
    ]
    return build_pdf([Page(items=items)])


def reading_order_pdf() -> bytes:
    """構造ツリーの順序がページ上の位置と逆のタグ付き PDF (下の要素を先にタグ付け)。"""
    items = [
        Text(50, 760, "ページ上では上にある段落", 12, mcid=1),
        Text(50, 400, "ページ上では下にある段落", 12, mcid=0),
    ]
    tree = Elem("Document", [Elem("P", [(0, 0)]), Elem("P", [(0, 1)])])
    return build_pdf([Page(items=items)], tree)


def scanned_page_pdf() -> bytes:
    """2ページ目が画像のみ (文字なし)。"""
    return build_pdf([Page(items=[Text(50, 760, "1ページ目には文字がある", 12)]), Page(image=True)])


def locked_pdf() -> bytes:
    return encrypt_pdf(build_pdf([Page(items=[Text(50, 760, "秘密", 12)])]), user="secret")


def copy_restricted_pdf() -> bytes:
    return encrypt_pdf(
        build_pdf([Page(items=[Text(50, 760, "コピー禁止の本文", 12)])]), copy_allowed=False
    )


def broken_pdf() -> bytes:
    data = build_pdf([Page(items=[Text(50, 760, "x", 12)])])
    return data[: len(data) // 3]
