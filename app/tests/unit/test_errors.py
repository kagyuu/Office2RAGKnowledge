"""U001-T3 の単体テスト: 例外階層とエラーコード表。"""

from __future__ import annotations

from pathlib import Path

from office2ragknowledge.errors import (
    ERROR_CATALOG,
    ConfigError,
    CorruptedFileError,
    FileTooLargeError,
    InputError,
    Office2RagError,
    OutputError,
    PasswordProtectedError,
    UnsupportedFormatError,
    catalog_entry,
)

EXPECTED_CODES = {
    UnsupportedFormatError: "E-002",
    PasswordProtectedError: "E-005",
    CorruptedFileError: "E-007",
    FileTooLargeError: "E-008",
    OutputError: "E-004",
    ConfigError: "E-006",
}


# ケース1: 各例外クラスが既定の code を持つ
def test_default_codes() -> None:
    for cls, code in EXPECTED_CODES.items():
        assert cls("メッセージ").code == code


# ケース2: すべて Office2RagError のサブクラス
def test_all_inherit_base() -> None:
    for cls in EXPECTED_CODES:
        assert issubclass(cls, Office2RagError)


# ケース3: InputError 系4クラス
def test_input_error_subclasses() -> None:
    for cls in (
        UnsupportedFormatError,
        PasswordProtectedError,
        CorruptedFileError,
        FileTooLargeError,
    ):
        assert issubclass(cls, InputError)
    assert not issubclass(OutputError, InputError)
    assert not issubclass(ConfigError, InputError)


# ケース4: path と hint が保持される
def test_path_and_hint_are_kept() -> None:
    err = UnsupportedFormatError("だめ", path=Path("a.doc"), hint="変換してください")
    assert err.path == Path("a.doc")
    assert err.hint == "変換してください"
    assert str(err) == "だめ"


# ケース5: ERROR_CATALOG に18コードが登録されている (E-009 は欠番)
def test_catalog_has_eighteen_codes() -> None:
    expected = {f"E-{n:03d}" for n in range(1, 9)} | {f"E-{n:03d}" for n in range(10, 20)}
    assert set(ERROR_CATALOG) == expected
    assert len(ERROR_CATALOG) == 18
    assert "E-009" not in ERROR_CATALOG


# ケース6: 未登録コードで例外を送出しない
def test_catalog_entry_unknown_code() -> None:
    name, hint = catalog_entry("E-999")
    assert isinstance(name, str)
    assert isinstance(hint, str)
    assert name


# ケース7: すべての hint が空でない (REQ-F-093)
def test_all_hints_are_non_empty() -> None:
    for code, (name, hint) in ERROR_CATALOG.items():
        assert name, f"{code} の種別名が空です"
        assert hint, f"{code} の対処方法が空です"


def test_hint_falls_back_to_catalog() -> None:
    """hint を指定しない場合、カタログの値が使われる。"""
    err = UnsupportedFormatError("だめ")
    assert err.hint == ERROR_CATALOG["E-002"][1]
