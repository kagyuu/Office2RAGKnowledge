# P008 結合テスト定義 兼 結合テスト指示書 — 目次 (OKF形式)

| 項目 | 内容 |
| --- | --- |
| 版 | 1.1 |
| 作成日 | 2026-08-24 |
| インプット | P002 (版2.1) / P003 (版1.1) / P005 (版1.1) / P006 (版1.1) / P007 (版1.1) |
| 改訂 | 1.1 (2026-10-14): ※CR-001・CR-002により T006 を追加 |
| 対象 | **スプリント内 / モジュール間**の結合テスト |
| 実行フェーズ | P103 (結合テスト実行) |

---

## 1. 本書の範囲

* 本書は**モジュール間の連携**を検証する。単体テストは `docs/P007-impl-direction.md` の各タスクに含まれるため、ここでは扱わない。
* **スプリントをまたぐ結合テスト・システムテスト・受け入れテスト**は `docs/P009-acceptance-direction.md` で扱う。本書では扱わない。
* テストコードの配置は `app/tests/integration/`。
* テストデータのライフサイクルは `docs/P006-test-plan.md` §4 に従う (**テスト1件ごとに `tmp_path` で隔離**)。

## 2. 検証する連携

| 連携 | 内容 |
| --- | --- |
| パーサ → 中間表現 → レンダラ | 実ファイルを入力に、生成された Markdown 全体を検証する (ゴールデンファイル方式) |
| CLI → 公開API → ファイル出力 | `CliRunner` またはサブプロセスで CLI を起動し、実際に書き出されたファイルを検証する |
| ZIP/XML基盤 → パーサ | 細工ファイルに対する防御が、パーサ経由でも機能することを検証する |

## 3. テスト一覧 (OKF)

- [x] T001 [Excel二重出力の連携](./P008-test-direction/T001-excel-dual-output.md) — パーサから2ファイル出力までの通し。要求①②③の中心
- [x] T002 [図形テキストの通し検証](./P008-test-direction/T002-shape-text-e2e.md) — 3形式で図形テキストが Markdown に現れること
- [x] T003 [WordとPowerPointの変換](./P008-test-direction/T003-word-powerpoint.md) — ゴールデンファイルによる出力全体の検証
- [x] T004 [CLIの画面と終了コード](./P008-test-direction/T004-cli-screens.md) — SCR-01〜07 と終了コード 0/1/2
- [x] T005 [異常系とセキュリティ](./P008-test-direction/T005-errors-security.md) — E-001〜E-019、ZIP爆弾・XXE・パストラバーサル
- [x] T006 [PDF変換の連携](./P008-test-direction/T006-pdf-conversion.md) — タグ付き/タグなし・ヘッダー/フッター・段組み・inspect・異常系 ※CR-001・CR-002

## 4. 共通の前提

| 項目 | 内容 |
| --- | --- |
| 実行コマンド | `pytest tests/integration -v` (`app/` で実行。**P103・P205 で実行して確認済み**) |
| 作業ディレクトリ | `app/` |
| 出力先 | 各テストの `tmp_path` 配下。**リポジトリを汚さない** |
| ゴールデンファイル | `app/tests/integration/golden/` |
| 比較方法 | `tests/helpers/compare.py` の `assert_markdown_equal(actual, expected)`。**front matter の `converted_at` を除外して比較する** (REQ-NF-018) |
| 失敗時の扱い | **P103 では失敗しても修正せず記録のみ**。修正は Reviewer Loop (P201〜P205) が行う |

## 5. 完了判定

* 各テストが実行され、結果が `docs/test-records/YYYYMMDD-HHMM-test-record.md` に記録されたら該当行を `[x]` にする。
* **合否によらず、実行して記録すれば `[x]` とする** (P103 は失敗を修正しないフェーズであるため)。
