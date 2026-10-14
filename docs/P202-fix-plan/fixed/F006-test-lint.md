# F006 — 新規テストコードの lint・整形違反 ※CR-001・CR-002

| 項目 | 内容 |
| --- | --- |
| 由来 | `docs/P201-review-report.md` 「CR-001・CR-002 による再実行 — 第1回」§2 (A005) |
| 対象要求 | REQ-NF-012 |
| 重大度 | 中 (品質ゲートの不合格) |
| 失敗テスト | `tests/acceptance/test_quality_gates.py::test_ruff_check` / `::test_ruff_format` |

## 【症状】

`ruff check` で E501 (行長超過) 5件、`ruff format --check` で未整形3ファイル。

## 【原因】

P103・P201 で新規作成したテストコード (`tests/acceptance/test_pdf_acceptance.py`・`tests/helpers/pdf_samples.py`・`tests/integration/test_pdf_conversion.py`) を、整形と lint にかけずに実行した。

## 【修正内容】

`ruff format src tests` を実行し、自動整形で解消しない長い行 (文字列・式) は分割する。テストの判定内容は変えない。

## 【影響範囲】

テストコード3件の体裁のみ。

## 【対応結果】(P203)

* `ruff format src tests` を実行した (2ファイルを整形)。整形で解消しなかった長い行 (A006 の inspect の呼び出しと判定、`pdf_samples.py` の表の行の生成) を分割した。テストの判定内容は変えていない。
* 確認: `ruff check src tests` → All checks passed / `ruff format --check src tests` → 109 files already formatted / `mypy src` → Success。
