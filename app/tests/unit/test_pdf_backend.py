"""U006-T1: PDF の読み取りと安全性 (P003 §4.4, §7A.2。※CR-001)。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from office2ragknowledge.errors import (
    CorruptedFileError,
    FileTooLargeError,
    PasswordProtectedError,
)
from office2ragknowledge.pdf import safety
from office2ragknowledge.pdf.backend import library_version, open_pdf, parse_pdf_date
from tests.helpers.make_pdf import Elem, Page, Text, build_pdf, encrypt_pdf, flate_bomb_pdf


def _tagged() -> bytes:
    pages = [
        Page(
            items=[
                Text(50, 800, "Header", 10, artifact="Header"),
                Text(50, 750, "見出し", 18, mcid=0),
                Text(50, 700, "本文", 12, mcid=1),
            ]
        ),
        Page(items=[Text(50, 750, "続き", 12, mcid=0)]),
    ]
    tree = Elem(
        "Doc",
        [
            Elem("H1", [(0, 0)]),
            Elem("P", [(0, 1), (1, 0)]),
            Elem("L", [], extra=" /A << /O /List /ListNumbering /Decimal >>"),
            Elem("Figure", [], alt="構成図"),
            Elem("TD", [], extra=" /A [<< /O /Table /ColSpan 2 /RowSpan 3 >> 0]"),
        ],
    )
    return build_pdf(pages, tree, title="報告書", author="山田", role_map={"Doc": "Document"})


def test_untagged_chars_and_coordinates() -> None:
    data = build_pdf([Page(items=[Text(50, 800, "AB", 10)])])
    src = open_pdf(data)
    assert len(src.pages) == 1
    page = src.pages[0]
    assert page.number == 1
    assert (page.width, page.height) == (595, 842)
    assert [c.text for c in page.chars] == ["A", "B"]
    first = page.chars[0]
    # 左上原点: y=800 のベースラインは上端から 42pt 付近
    assert first.top < first.bottom < 50
    assert first.path is None
    assert first.size == 10
    assert src.has_struct_tree is False
    assert src.struct == {}


def test_tagged_paths_and_struct_info() -> None:
    src = open_pdf(_tagged())
    assert src.has_struct_tree is True
    p1 = src.pages[0]
    paths = {c.text: c.path for c in p1.chars}
    assert paths["見"] == (0, 0)
    assert paths["本"] == (0, 1)
    # ページをまたぐ要素は同じ経路で現れる (Handbook §4-9)
    assert {c.path for c in src.pages[1].chars} == {(0, 1)}
    assert src.struct[(0,)].tag == "Document"  # RoleMap の適用
    assert src.struct[(0, 0)].tag == "H1"
    assert src.struct[(0, 2)].list_numbering == "Decimal"
    assert src.struct[(0, 3)].alt == "構成図"
    td = src.struct[(0, 4)]
    assert (td.col_span, td.row_span) == (2, 3)


def test_mcr_form_yields_paths() -> None:
    """MCR 辞書形式でも文字に経路が付く (※CR-003。PyMuPDF では付かなかった。Handbook §4-8)。"""
    pages = [Page(items=[Text(50, 750, "見出し", 18, mcid=0), Text(50, 700, "本文", 12, mcid=1)])]
    tree = Elem("Document", [Elem("H1", [(0, 0)]), Elem("P", [(0, 1)])])
    src = open_pdf(build_pdf(pages, tree, mcr=True))
    assert src.has_struct_tree is True
    paths = {c.text: c.path for c in src.pages[0].chars}
    assert paths["見"] == (0, 0) and paths["本"] == (0, 1)


def test_artifact_chars_have_no_path() -> None:
    src = open_pdf(_tagged())
    header = [c for c in src.pages[0].chars if c.text in "Header"]
    assert header and all(c.path is None for c in header)


def test_metadata() -> None:
    meta = open_pdf(_tagged()).metadata
    assert meta.title == "報告書"
    assert meta.author == "山田"
    assert meta.created_at == datetime(2026, 4, 1, 9, 0, tzinfo=timezone(timedelta(hours=9)))
    assert meta.modified_at is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("D:20260401090000+09'00'", datetime(2026, 4, 1, 9, tzinfo=timezone(timedelta(hours=9)))),
        ("D:20260401", datetime(2026, 4, 1)),
        ("D:20260401123000Z", datetime(2026, 4, 1, 12, 30, tzinfo=UTC)),
        (
            "D:20260401123000-05'30",
            datetime(2026, 4, 1, 12, 30, tzinfo=timezone(-timedelta(hours=5, minutes=30))),
        ),
        ("20260401", datetime(2026, 4, 1)),
        ("D:20261340", None),
        ("garbage", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_pdf_date(value: str | None, expected: datetime | None) -> None:
    assert parse_pdf_date(value) == expected


def test_password_protected() -> None:
    data = encrypt_pdf(build_pdf([Page(items=[Text(50, 750, "x")])]), user="secret")
    with pytest.raises(PasswordProtectedError) as info:
        open_pdf(data)
    assert info.value.code == "E-005"


def test_owner_password_only_copy_restricted() -> None:
    data = encrypt_pdf(build_pdf([Page(items=[Text(50, 750, "abc")])]), copy_allowed=False)
    src = open_pdf(data)
    assert src.copy_restricted is True
    assert "".join(c.text for c in src.pages[0].chars) == "abc"


def test_owner_password_only_copy_allowed() -> None:
    data = encrypt_pdf(build_pdf([Page(items=[Text(50, 750, "abc")])]), copy_allowed=True)
    assert open_pdf(data).copy_restricted is False


@pytest.mark.parametrize(
    "data",
    [
        b"%PDF-1.7\n",
        b"%PDF-1.7\ngarbage garbage",
        b"not a pdf at all",
        b"",
    ],
)
def test_corrupted(data: bytes) -> None:
    with pytest.raises(CorruptedFileError) as info:
        open_pdf(data)
    assert info.value.code == "E-007"


def test_truncated_is_corrupted() -> None:
    data = build_pdf([Page(items=[Text(50, 750, "x")])])
    with pytest.raises(CorruptedFileError):
        open_pdf(data[: len(data) // 3])


def test_flate_bomb_per_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(safety, "MAX_STREAM_BYTES", 1024 * 1024)
    with pytest.raises(FileTooLargeError) as info:
        open_pdf(flate_bomb_pdf(2 * 1024 * 1024))
    assert info.value.code == "E-008"


def test_flate_bomb_total(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(safety, "MAX_TOTAL_STREAM_BYTES", 1024 * 1024)
    with pytest.raises(FileTooLargeError):
        open_pdf(flate_bomb_pdf(2 * 1024 * 1024))


def test_flate_within_limit_passes() -> None:
    src = open_pdf(flate_bomb_pdf(64 * 1024))
    assert "".join(c.text for c in src.pages[0].chars) == "bomb"


def test_compressed_content_is_read() -> None:
    data = build_pdf([Page(items=[Text(50, 750, "圧縮")])], compress=True)
    assert "".join(c.text for c in open_pdf(data).pages[0].chars) == "圧縮"


def test_figure_rects_and_images() -> None:
    page = Page(items=[Text(110, 520, "in", 10)], rects=[(100, 500, 100, 50)], image=True)
    src = open_pdf(build_pdf([page]))
    assert len(src.pages[0].figure_rects) >= 1
    x0, top, x1, bottom = src.pages[0].figure_rects[0]
    assert x0 <= 100 and x1 >= 200
    assert src.pages[0].image_count == 1


def test_no_stderr_from_library(capfd: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(CorruptedFileError):
        open_pdf(b"%PDF-1.7\ngarbage garbage")
    data = build_pdf([Page(items=[Text(50, 750, "x")])])
    with pytest.raises(CorruptedFileError):
        open_pdf(data[: len(data) // 3])
    captured = capfd.readouterr()
    assert captured.err == ""
    assert captured.out == ""


def test_library_version() -> None:
    assert library_version().startswith("pdfminer.six ")


def test_trailing_artifact_is_not_in_structure() -> None:
    """MuPDF は構造の後の Artifact を直前の要素に含める。内容ストリームの走査で除く (§4-13)。"""
    items = [
        Text(50, 820, "HH", 10, artifact="Header"),
        Text(50, 780, "body text", 12, mcid=0),
        Text(280, 20, "12", 10, artifact="Footer"),
    ]
    src = open_pdf(
        build_pdf([Page(items=items)], Elem("Document", [Elem("P", [(0, 0)])]), compress=True)
    )
    paths = {c.text: c.path for c in src.pages[0].chars if not c.text.isspace()}
    assert paths["b"] == (0, 0)
    assert paths["1"] is None and paths["2"] is None and paths["H"] is None


def test_kid_index_is_position_in_k() -> None:
    """文字に、その MCID が要素の /K の何番目かが付く (※CR-003。Handbook §4-15)。"""
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
    src = open_pdf(build_pdf(pages, tree))
    info = {c.text: (c.path, c.kid_index) for c in src.pages[0].chars}
    assert info["前"] == ((0, 0), 0)
    assert info["中"] == ((0, 0, 1), 0)
    assert info["後"] == ((0, 0), 2)


def test_unicode_less_glyphs_become_replacement_char() -> None:
    from office2ragknowledge.pdf import backend

    assert backend._CID.match("(cid:123)")
    assert not backend._CID.match("(cid:x)")


def test_text_in_form_xobject_keeps_mcid() -> None:
    """Form XObject の中の文字も MCID と経路を保つ (※CR-003)。

    ライブラリの基底クラスは Form XObject の入れ子に ``_stack`` を使う。マーク付き
    コンテンツの入れ子を同じ名前で持つと、フォームの処理が壊れる (P102 で検出)。
    """
    items = [
        Text(50, 750, "フォームの外", 12, mcid=0),
        Text(50, 700, "フォームの中", 12, mcid=1, in_form=True),
        Text(50, 650, "後ろ", 12, mcid=2),
    ]
    tree = Elem("Document", [Elem("P", [(0, 0)]), Elem("P", [(0, 1)]), Elem("P", [(0, 2)])])
    src = open_pdf(build_pdf([Page(items=items, image=True)], tree))
    paths = {c.text: c.path for c in src.pages[0].chars}
    assert paths["外"] == (0, 0)
    assert paths["中"] == (0, 1)
    assert paths["後"] == (0, 2)
    assert src.pages[0].image_count == 1
