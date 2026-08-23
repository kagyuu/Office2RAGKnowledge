"""U005-T1 の単体テスト: write_result。

**出力ファイルごとに個別に on_exists を判定する** (P002 §5.2)。
Excel の二重出力で片方だけが既存の場合、その片方のみスキップする。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from office2ragknowledge import OnExists, OutputError, convert_file, write_result
from tests.helpers.make_office import make_docx, make_xlsx


def excel(tmp_path: Path) -> Path:
    return make_xlsx(tmp_path / "book.xlsx", {"S1": [["a", "b"], ["c", "d"]]})


# ケース1: Word で1ファイル
def test_word_writes_one_file(tmp_path: Path) -> None:
    result = convert_file(make_docx(tmp_path / "doc.docx", [("p", "本文")]))
    out = tmp_path / "out"
    written = write_result(result, out)
    assert [p.name for p in written.markdown_paths] == ["doc.md"]


# ケース2: Excel で2ファイル
def test_excel_writes_two_files(tmp_path: Path) -> None:
    result = convert_file(excel(tmp_path))
    written = write_result(result, tmp_path / "out")
    assert sorted(p.name for p in written.markdown_paths) == [
        "book.grid.md",
        "book.table.md",
    ]


# ケース3: skip で既存がスキップされる
def test_skip_existing(tmp_path: Path) -> None:
    result = convert_file(excel(tmp_path))
    out = tmp_path / "out"
    write_result(result, out)
    second = write_result(result, out, OnExists.SKIP)
    assert second.markdown_paths == ()
    assert len(second.skipped_paths) == 2


# ケース4 (必須): 片方だけ既存のとき、もう片方は書き出される
def test_partial_existing_writes_the_other(tmp_path: Path) -> None:
    result = convert_file(excel(tmp_path))
    out = tmp_path / "out"
    write_result(result, out)
    (out / "book.grid.md").unlink()

    third = write_result(result, out, OnExists.SKIP)
    assert [p.name for p in third.markdown_paths] == ["book.grid.md"]
    assert [p.name for p in third.skipped_paths] == ["book.table.md"]


def test_partial_existing_reverse(tmp_path: Path) -> None:
    result = convert_file(excel(tmp_path))
    out = tmp_path / "out"
    write_result(result, out)
    (out / "book.table.md").unlink()
    again = write_result(result, out, OnExists.SKIP)
    assert [p.name for p in again.markdown_paths] == ["book.table.md"]


# ケース5: overwrite で上書き
def test_overwrite(tmp_path: Path) -> None:
    result = convert_file(excel(tmp_path))
    out = tmp_path / "out"
    write_result(result, out)
    (out / "book.table.md").write_text("汚染", encoding="utf-8")
    write_result(result, out, OnExists.OVERWRITE)
    assert "汚染" not in (out / "book.table.md").read_text(encoding="utf-8")


# ケース6: fail で OutputError
def test_fail_on_existing(tmp_path: Path) -> None:
    result = convert_file(excel(tmp_path))
    out = tmp_path / "out"
    write_result(result, out)
    with pytest.raises(OutputError):
        write_result(result, out, OnExists.FAIL)


# ケース7: 出力先が無ければ作られる
def test_creates_output_dir(tmp_path: Path) -> None:
    result = convert_file(make_docx(tmp_path / "doc.docx", [("p", "本文")]))
    out = tmp_path / "deep" / "nested"
    write_result(result, out)
    assert out.is_dir()


# ケース8: UTF-8 (BOMなし) / LF
def test_encoding_and_newlines(tmp_path: Path) -> None:
    result = convert_file(make_docx(tmp_path / "doc.docx", [("p", "日本語の本文")]))
    out = tmp_path / "out"
    written = write_result(result, out)
    raw = written.markdown_paths[0].read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "BOM が付いています"
    assert b"\r\n" not in raw, "CRLF が含まれています"
    assert "日本語の本文" in raw.decode("utf-8")


# ケース11: 一時ファイルが残らない
def test_no_temp_files_left(tmp_path: Path) -> None:
    result = convert_file(excel(tmp_path))
    out = tmp_path / "out"
    write_result(result, out)
    assert not any(".tmp" in p.name for p in out.iterdir())


# ケース12: markdown_paths が実際に書いたパス
def test_written_paths_exist(tmp_path: Path) -> None:
    result = convert_file(excel(tmp_path))
    written = write_result(result, tmp_path / "out")
    for path in written.markdown_paths:
        assert path.is_file()
