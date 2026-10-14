あなたはExecutor(実装担当)です。実施後は、結果(PASS/FAIL/BLOCKED/NOT RUN)を記録したうえで、Reviewer Loopの「停止条件」に該当しない限り、自動的に次のテストタスクへ進んでください。

# 【テストID】A007 — 実行時依存のライセンス ※CR-003により追加

## 【目的】

* 配布物の実行時依存 (推移的な依存を含む) に、本アプリの MIT ライセンスと両立しないライセンス (AGPL・GPL) が含まれないことを、導入した環境のパッケージのメタデータから自動で確認する (REQ-NF-021)。
* CR-003 の期待する振る舞いのうち、依存とライセンスに関わるものを確認する。

## 【参照テスト計画】

* `docs/P006-test-plan.md` §2.2 N-19
* `docs/P001-requirement.md` REQ-NF-021
* `docs/P901-cr-direction/CR-003.md` の「期待する振る舞い」

## 【前提条件】

* `pip install -e ".[dev]"` で導入した環境で実行する (開発時依存 (pytest 等) は検査の対象にしない。実行時依存の木だけを辿る)。

## 【実行手順と期待結果】

| # | 確認 | 手順 | 期待結果 | CR-003 の項目 |
| --- | --- | --- | --- | --- |
| 1 | 実行時依存のライセンス | `importlib.metadata` で `office2ragknowledge` の `Requires-Dist` (extra の指定が無いもの) を推移的に辿り、各パッケージの `License-Expression`・`License`・分類子 `License ::` を集める | どのパッケージにも `AGPL`・`GPL` (`LGPL` を含む)・`Affero` の語が無い | #1 |
| 2 | 依存の網羅 | 同上で辿ったパッケージの一覧 | `pdfminer.six` が含まれ、`pymupdf` (`PyMuPDF`) が含まれない | #2 |
| 3 | ライセンス情報の欠落 | 同上 | すべてのパッケージにライセンス情報 (上記3種のいずれか) がある。欠落があれば一覧を出して失敗にする (確認できないものを合格扱いにしない) | #1 |
| 4 | バージョン画面 | `office2rag --version` | 依存ライブラリの表示に `pdfminer.six` が出て、`PyMuPDF` が出ない | #6 |
| 5 | Docker イメージのラベル | `deploy/Dockerfile` を読む | `org.opencontainers.image.licenses="MIT"` | #9 |
| 6 | MCR 形式のタグ付き PDF | MCR 辞書形式でタグ付けした PDF を `convert_bytes` で変換する | `pdf_structure: "tagged"` で、見出しが `#` として出る | #4 |

## 【実行コマンド】

* `pytest tests/acceptance/test_dependency_licenses.py -v` (`app/` で実行)

## 【結果記録先】

* `docs/test-records/YYYYMMDD-HHMM-test-record.md`
