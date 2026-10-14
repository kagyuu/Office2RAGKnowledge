"""例外階層とエラーコード表 (P002 §6.5, §9.1)。

すべての例外は ``code`` / ``path`` / ``hint`` を持つ。CLI 層はこれをそのまま
エラー画面 (SCR-06) と失敗一覧 (SCR-04) の表示に用いる。

**例外メッセージの文言は日本語**、``code`` は言語非依存の識別子とする
(将来の多言語化の余地を残すため)。
"""

from __future__ import annotations

from pathlib import Path

__all__ = [
    "ERROR_CATALOG",
    "ConfigError",
    "CorruptedFileError",
    "FileTooLargeError",
    "InputError",
    "Office2RagError",
    "OutputError",
    "PasswordProtectedError",
    "UnsupportedFormatError",
    "catalog_entry",
]


class Office2RagError(Exception):
    """本アプリの例外の基底。"""

    default_code = "E-000"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        path: Path | None = None,
        hint: str = "",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code
        self.path = path
        self.hint = hint or catalog_entry(self.code)[1]

    def __str__(self) -> str:
        return self.message


class InputError(Office2RagError):
    """入力ファイルに起因するエラー。"""


class UnsupportedFormatError(InputError):
    """対応していない形式 (E-002)。"""

    default_code = "E-002"


class PasswordProtectedError(InputError):
    """パスワードで保護されたファイル (E-005)。"""

    default_code = "E-005"


class CorruptedFileError(InputError):
    """ZIP または XML として読み取れない (E-007)。"""

    default_code = "E-007"


class FileTooLargeError(InputError):
    """展開後のサイズが上限を超える (E-008)。ZIP爆弾の防御。"""

    default_code = "E-008"


class OutputError(Office2RagError):
    """出力先に書き込めない (E-004)。"""

    default_code = "E-004"


class ConfigError(Office2RagError):
    """設定ファイルの構文・キー・値が不正 (E-006)。"""

    default_code = "E-006"


#: エラーコード → (種別の表示名, 対処方法の案内)。
#:
#: P002 §9.1 の表に対応する。**E-009 は欠番** であり、実在するのは
#: E-001〜E-008 と E-010〜E-019 の18件である。
ERROR_CATALOG: dict[str, tuple[str, str]] = {
    "E-001": (
        "パス不存在",
        "パスの綴りと、ファイルが存在することを確認してください。",
    ),
    "E-002": (
        "非対応形式",
        "Office で開き、.docx / .xlsx / .pptx 形式で保存し直してください"
        " (PDF はそのまま変換できます)。",
    ),
    "E-003": (
        "読み取り権限不足",
        "ファイルのアクセス権を確認してください。他のアプリで開いている場合は閉じてください。",
    ),
    "E-004": (
        "出力エラー",
        "出力先ディレクトリのアクセス権と空き容量を確認してください。",
    ),
    "E-005": (
        "パスワード保護",
        "Office または PDF の編集ソフトで開いてパスワードを解除し、保存し直してください。",
    ),
    "E-006": (
        "設定エラー",
        "設定ファイルの該当キーを、指定できる値に修正してください。",
    ),
    "E-007": (
        "破損ファイル",
        "ファイルが完全にダウンロード/コピーされているか確認してください。",
    ),
    "E-008": (
        "サイズ超過",
        "意図しない巨大ファイルの可能性があります。ファイルの出所を確認してください。",
    ),
    "E-010": (
        "引数不足",
        "例: office2rag convert ./docs -o ./out",
    ),
    "E-011": (
        "対象0件",
        "ディレクトリ配下を探索する場合は -r を指定してください。",
    ),
    "E-012": (
        "排他指定違反",
        "いずれか一方のみを指定してください。",
    ),
    "E-013": (
        "値不正",
        "指定できる値については --help を参照してください。",
    ),
    "E-014": (
        "stdout 対象複数",
        "単一ファイルを指定するか、--stdout を外して -o で出力先を指定してください。",
    ),
    "E-015": (
        "範囲外",
        "--max-rows は 0〜1048576 の範囲で指定してください。0 を指定すると行数制限なしになります。",
    ),
    "E-016": (
        "範囲外",
        "--jobs は 1〜64 の範囲で指定してください。既定では CPU コア数が使われます。",
    ),
    "E-017": (
        "stdout とExcel複数モード",
        "--excel-modes table (表計算として出力) または --excel-modes grid "
        "(方眼紙として出力) を指定してください。",
    ),
    "E-018": (
        "区切り文字不正",
        "セルを連結する際に挟む短い文字列を指定してください (既定: なし)。",
    ),
    "E-019": (
        "範囲外",
        "--max-table-regions は 1〜10000 の範囲で指定してください。既定は 100 です。",
    ),
}


def catalog_entry(code: str) -> tuple[str, str]:
    """エラーコードから (種別の表示名, 対処方法) を得る。

    未登録のコードでも例外を送出せず、汎用の値を返す。
    """
    return ERROR_CATALOG.get(code, ("エラー", ""))
