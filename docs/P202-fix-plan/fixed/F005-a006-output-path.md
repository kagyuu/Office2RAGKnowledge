# F005 — A006 #14 の出力先のパスの誤り ※CR-002

| 項目 | 内容 |
| --- | --- |
| 由来 | `docs/P201-review-report.md` 「CR-001・CR-002 による再実行 — 第1回」§2 |
| 対象要求 | REQ-F-122 (確認したい振る舞い) / REQ-F-004 (出力先) |
| 重大度 | 低 (テストコードの誤り) |
| 失敗テスト | `tests/acceptance/test_pdf_acceptance.py::test_14_cover_and_single_page` |

## 【症状】

`FileNotFoundError: .../out/sub/one.md`。

## 【原因】

`-r` でサブディレクトリから見つけたファイルは、`-o` を指定すると出力先の**直下に平らに**書き出される (既存仕様。`batch.py` の出力先決定、REQ-F-004)。テストが入力の階層を出力にも保つ前提で `out/sub/one.md` を参照していた。テスト #1 (`rglob`) はこの前提に依存していなかったため合格していた。

## 【修正内容】

`test_14_cover_and_single_page` が `converted / "one.md"` を参照するように改める。#1 の期待 (出力ファイル名の一覧) も、平らに書き出されることを明示的に確かめる形 (`iterdir`) に改める。

## 【影響範囲】

テストコード1件のみ。

## 【対応結果】(P203)

* `app/tests/acceptance/test_pdf_acceptance.py` の `test_14_cover_and_single_page` が `converted / "one.md"` を参照するように改めた。
* `test_1_mixed_batch` も `iterdir()` で出力先の直下を見るように改め、平らに書き出されることを明示的に確かめる形にした。
* 確認: A006 の20件すべて合格 (`docs/test-records/20261014-0230-test-record.md`)。
