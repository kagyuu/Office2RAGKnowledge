# 成果物まとめ

| 項目 | 内容 |
| --- | --- |
| プロジェクト | Office2RAGKnowledge |
| 版 | **1.1.0** (2026-10-15 に依頼者の指示で 1.0.0 から上げた。PDF 対応 (※CR-001〜CR-003) を含む — 5章) |
| 作成日 | 2026-08-24 / 更新 2026-10-14 (※CR-001・CR-002) / **更新 2026-10-14 (※CR-003 による P302 再実行)** |
| フェーズ | P302 (納品物作成) |
| **リリース判定** | **保留** (根拠は11章。要対応1件: 画像抽出の自動テスト。PDF ライブラリのライセンスは ※CR-003 で解消) |

---

## 1. 概要

Office 文書 (Word / Excel / PowerPoint) と **PDF** (※CR-001・CR-002) を、AI の RAG パイプライン向け Markdown に変換する **CLIツール兼 Python ライブラリ**である。

利用者が最初に挙げた2つの要求が、他ツールとの差になっている。

1. **オートシェープ内のテキストを取りこぼさない** — OCR を使わず、OOXML 上のテキストを回収する (REQ-F-031〜040)。
2. **Excel の二面性に判別なしで両対応する** — 「表計算として使われている」か「方眼紙として使われている」かを**判別せず**、常に両方の Markdown (`.table.md` / `.grid.md`) を1回の解析から出力する (REQ-F-064〜068)。

**※CR-001・CR-002 (2026-10-14)**: PDF を入力に加えた。タグ付き (アクセシビリティ対応) の PDF は論理構造から見出し・入れ子の箇条書き・表・図に変換し、タグなしの PDF は構造を推定せずに段落の並びとして出力する。タグなしの PDF ではページ上下のヘッダー・フッターを除き、段組みを段ごとの読み順に直す。PDF の読み取りには当初、依頼者の指示で PyMuPDF (AGPL-3.0) を用いたが、**※CR-003 で pdfminer.six (MIT) に差し替え、実行時依存はすべて MIT と両立するライセンスになった** (A007 で検査)。

本書は、仕様・テスト・実装の対応、配布資産、実行手順、最終確認結果、未整備事項をまとめ、人間がリリース可否を判断するための資料である。

### 到達状況

| 指標 | 値 | 証跡 |
| --- | --- | --- |
| テスト | **706件合格 / 0件失敗** (Python 3.12) / **707件合格** (Python 3.11)。※CR-003 改修後 | [0747](./test-records/20261014-0747-test-record.md) |
| 検証した Python | **3.11.14 と 3.12.12 の新規 venv で全件合格** (※CR-003 改修後) | [0747](./test-records/20261014-0747-test-record.md) |
| 行カバレッジ | 90% (目標80%。PDF のモジュールは 89〜100%) | [0230](./test-records/20261014-0230-test-record.md) |
| 静的検査 | ruff check / ruff format / mypy strict すべてエラー0件 | 同上 §6 |
| 要求の充足 | **124要求すべて OK** (※CR-003 で REQ-NF-021 を追加) | [P004](./P004-traceability-matrix.md) |
| 配布物 | wheel / sdist を再ビルドし、クリーン環境での動作と、PyMuPDF 版との出力の比較 (A/B) を確認済み | [0752](./test-records/20261014-0752-test-record.md) |
| Docker | ビルドと `docker compose run` での変換を確認済み。イメージ 203 MB・ラベル `MIT`・PyMuPDF を含まない (※CR-003) | [0752](./test-records/20261014-0752-test-record.md) §4 |

---

## 2. 参照した成果物

### 存在を確認した文書

| 分類 | ファイル | 備考 |
| --- | --- | --- |
| 要求 | [P001-requirement.md](./P001-requirement.md) | 版1.1。機能要件84件 + 非機能要件19件 |
| UI設計 | [P002-frontend-spec.md](./P002-frontend-spec.md) | 版2.0。CLI 7画面 / 出力体裁 / 公開API / 中間表現 |
| 詳細設計 | [P003-backend-spec.md](./P003-backend-spec.md) | §1 に実測スパイク結果 |
| トレーサビリティ | [P004-traceability-matrix.md](./P004-traceability-matrix.md) | 103/103 OK |
| 実装計画 | [P005-impl-plan.md](./P005-impl-plan.md) | 5スプリント |
| テスト計画 | [P006-test-plan.md](./P006-test-plan.md) | 4テストレベル |
| 実装指示 | [P007-impl-direction.md](./P007-impl-direction.md) + `P007-impl-direction/U001〜U005` | OKF 全5件 `[x]` |
| 結合テスト指示 | [P008-test-direction.md](./P008-test-direction.md) + `P008-test-direction/T001〜T005` | OKF 全5件 `[x]` |
| 受入テスト指示 | [P009-acceptance-direction.md](./P009-acceptance-direction.md) + `P009-acceptance-direction/A001〜A005` | OKF 全5件 `[x]` |
| 設計レビュー | [P010-design-review.md](./P010-design-review.md) / [P011-impact-analysis.md](./P011-impact-analysis.md) | 4件検出 → 是正 → 0件 |
| 実装レビュー | [P201-review-report.md](./P201-review-report.md) | 2件の欠陥を検出 |
| 修正 | [P202-fix-plan.md](./P202-fix-plan.md) + `P202-fix-plan/fixed/F001〜F003` | OKF 全3件 `[x]` |
| 修正結果 | [P202-fix-resolved.md](./P202-fix-plan/P202-fix-resolved.md) / [P202-fix-unresolved.md](./P202-fix-plan/P202-fix-unresolved.md) | **未解決0件** |
| 影響分析 | [P204-impact-analysis.md](./P204-impact-analysis.md) | 他機能への影響なし |
| テスト記録 | [0815](./test-records/20260824-0815-test-record.md) / [0850](./test-records/20260824-0850-test-record.md) / [0855](./test-records/20260824-0855-test-record.md) | P103 / P205 / P302 |
| 恒久文書 | [ADR.md](./ADR.md) (ADR-001〜011) / [ArchitectureHandbook.md](./ArchitectureHandbook.md) | |
| 目次 | [../INDEX.md](../INDEX.md) / [../app/INDEX.md](../app/INDEX.md) | |
| ソース・配布 | `app/pyproject.toml` / `app/src/` (42ファイル) / `app/tests/` (テストモジュール39件・補助を含め47ファイル) / `app/README.md` / `deploy/` / `BUILD_HISTORY.md` | |

### 存在しない文書 (推測で補っていない)

| ファイル | 扱い |
| --- | --- |
| `docs/CR.md` / `docs/P901-cr-direction/` | 変更要求がまだ起票されていないため存在しない。**正常** (Refactor 未実行) |
| `docs/ADR_master.md` | 廃止された ADR が無いため存在しない。**正常** |
| `docs/.stop-report.md` | 停止条件に該当していないため存在しない。**正常** |
| `VERSION` | **意図的に作成しない。** Python 標準のバージョン定義 (`app/pyproject.toml` の `project.version`) が既にあり、`SKILL-P302-deliver.md` の優先順位(1)に従う ★ACCEPTED★ (検討: `VERSION` を併置する案 / 不採用理由: 定義が二重化し、更新漏れで2つの値が食い違う / 残存リスク: `VERSION` ファイルを前提とする外部ツールがあれば追加が要る) |

### 実行前チェックの結果

| # | 確認項目 | 結果 |
| --- | --- | --- |
| 1 | P002・P003 の存在 | **あり** |
| 2 | P006 の存在 | **あり** |
| 3 | テスト記録の存在 | **あり** (3件) |
| 4 | P202-fix-resolved / unresolved の存在 | **あり** (未解決0件) |
| 5 | アプリケーション種別の推定 | **可能** (3章) |
| 6 | P302-deliver.md の既存 | **なし** (本書が初版) |
| 7 | フロントエンドのAPI接続前提と配布トポロジーの整合 | **該当なし。** `app/src/office2ragknowledge/` の全42ファイルに HTTP クライアント・サーバの実装が無く (依存は openpyxl / python-docx / python-pptx / lxml / typer / rich の6件のみ)、フロントエンドとバックエンドを分離するトポロジー自体が存在しない。配布形態は**単一プロセスのCLI**であり、オリジンや `BASE_URL` の概念を持たない。トポロジー未決定による N/A ではなく、**トポロジーを確定させたうえでの該当なし**である |
| 8 | 再起動後の正常起動 (初期化の冪等性) | **該当なし (データストア無し)。** 永続化するデータストアを持たず、マイグレーション・初期化処理が存在しない。ただし同一観点 (同じ出力先に対する複数回の実行) は既に **A003 で確認済み**であり、重複して再実行はしない → [A003](./P009-acceptance-direction/A003-rerun-operations.md) / 記録: [0850](./test-records/20260824-0850-test-record.md) §3 (テストスイート2回連続実行で同一結果。観点 O-03) |

チェック7・8はいずれも**仕様変更を要する不整合を検出していない**ため、Closing Step の停止条件には該当しない。

---

## 3. アプリケーション種別と配布方針

### 種別

`SKILL-P302-deliver.md` の分類に照らすと、本アプリは **2 (CLIコマンド)** を主、**4 (ライブラリ)** を従とする。**1 (サービス提供型) には該当しない。**

| 分類 | 該当 | 根拠 |
| --- | --- | --- |
| 1. サービス提供型システム | **×** | 常駐プロセス・ポート待受・HTTPハンドラを一切持たない。`cli/main.py` は変換して終了する |
| 2. CLIコマンド | **◎ (主)** | `pyproject.toml` の `[project.scripts]` が `office2rag` を定義。サブコマンド `convert` / `inspect` を持ち、引数と TOML 設定ファイルを受け取り、ファイルまたは標準出力に Markdown を出す (REQ-F-090〜099) |
| 3. バッチ処理 | **△ (2に包含)** | ディレクトリの再帰一括変換 (`convert {dir} -r`) と並列実行 (`--jobs`) を持ち、運用上はバッチとしても使う。ただし独立した実行スクリプトは持たず、CLI と同一の入口である |
| 4. ライブラリ | **◎ (従)** | `import office2ragknowledge` して `convert_file` / `convert_bytes` / `inspect_file` を呼べる (REQ-F-100〜103)。`py.typed` を同梱 |

### 配布方針

| 方針 | 内容 |
| --- | --- |
| **第一の配布形式** | **Python wheel** (`pip install office2ragknowledge-1.1.0-py3-none-any.whl`)。CLI とライブラリの両方が1つの wheel で配れる。外部バイナリ (LibreOffice・OCRエンジン) を必要としない (REQ-NF-019) |
| **第二の配布形式** | **Docker イメージ** (`deploy/Dockerfile`)。Python 環境を用意できない利用者、および CI パイプラインへの組み込み用 |
| **docker compose の位置づけ** | **常駐サービスではないため `up` で待ち受けない。** `docker compose run --rm convert ...` で都度実行する。この点は `deploy/compose.yml` の先頭コメントにも明記した ★ACCEPTED★ (検討: `up` で常駐させ監視ループを持たせる案 / 不採用理由: 要求に常駐・監視の記述が無く、機能追加になる / 残存リスク: `docker compose up` を試した利用者が「すぐ終了する」ことに戸惑いうる。手順書とファイル冒頭のコメントで明示して緩和した) |
| **バージョン確認** | `office2rag --version` で本体版数と依存ライブラリ版数の両方を表示する (実装済み・実行確認済み) |

---

## 4. 仕様・テスト・テスト実装の対応表

`docs/P004-traceability-matrix.md` に載る **103件の要求ID すべて**を本表で網羅した (下の「網羅性の確認」を参照)。テスト実装のコマンドはいずれも `app/` ディレクトリで実行する。

| 仕様ID/項目 | 要求ID | 仕様内容 | 対応するテスト計画 | 対応するテスト指示 | 対応するテスト実装/実行コマンド | 最新結果 | 証跡 | 状態 | 出荷影響 |
|---|---|---|---|---|---|---|---|---|---|
| SPEC-CORE-001 | REQ-F-001〜010 | 共通変換 (3形式の受付・形式判定・front matter・見出し階層・箇条書き・表・文字エスケープ) | P006 §2.1 F-01〜F-05 | [T003](./P008-test-direction/T003-word-powerpoint.md) / [T004](./P008-test-direction/T004-cli-screens.md) | `pytest tests/integration/test_word_powerpoint.py tests/unit/test_frontmatter.py tests/unit/test_escape.py tests/unit/test_detect.py -v` | PASS | [0850](./test-records/20260824-0850-test-record.md) | OK | - |
| SPEC-WORD-001 | REQ-F-011〜020 | Word 変換 (段落・見出し・表・箇条書き・改頁・脚注・変更履歴・ヘッダフッタ) | P006 §2.1 F-06 | [T003](./P008-test-direction/T003-word-powerpoint.md) | `pytest tests/integration/test_word_powerpoint.py tests/unit/test_word_parser.py -v` | PASS | [0850](./test-records/20260824-0850-test-record.md) | OK | - |
| SPEC-XLS-COMMON | REQ-F-021, 022, 024, 026〜029, 050 | Excel 共通 (シート単位の章立て・非表示シート・結合セル・日付/数値書式・ハイパーリンク・コメント) | P006 §2.1 F-07〜F-09 | [T001](./P008-test-direction/T001-excel-dual-output.md) | `pytest tests/integration/test_excel_dual_output.py tests/unit/test_excel_parser.py -v` | PASS | [0850](./test-records/20260824-0850-test-record.md) | OK | - |
| SPEC-XLS-FORMULA | REQ-F-051〜053 | **要求②** 数式セルのキャッシュ値 (キャッシュがあれば値、無ければ数式文字列、`inspect` で件数表示) | P006 §2.1 F-10 | [T001](./P008-test-direction/T001-excel-dual-output.md) | `pytest tests/unit/test_excel_formula.py tests/unit/test_inspection.py -v` | PASS | [0850](./test-records/20260824-0850-test-record.md) | OK | - |
| SPEC-XLS-TABLE | REQ-F-023, 025, 030, 054〜057 | **要求①③-1** 表計算モード (`## {シート名}` + Markdown Table / 空行・空列による複数表領域の分割 / 上限超過時の退避) | P006 §2.1 F-11 | [T001](./P008-test-direction/T001-excel-dual-output.md) | `pytest tests/unit/test_excel_regions.py tests/unit/test_excel_table_render.py tests/integration/test_excel_dual_output.py -v` | PASS | [0850](./test-records/20260824-0850-test-record.md) | OK | - |
| SPEC-XLS-GRID | REQ-F-058〜063 | **要求③-2** 方眼紙モード (`## {シート名}` + A1から非空白セルを連結 / 空行を空行にしてチャンク区切りにする) | P006 §2.1 F-12 | [T001](./P008-test-direction/T001-excel-dual-output.md) | `pytest tests/unit/test_excel_grid_render.py tests/acceptance/test_core_requirements.py -v` | PASS | [A001](./P009-acceptance-direction/A001-core-requirements.md) / [0850](./test-records/20260824-0850-test-record.md) | OK | - |
| SPEC-XLS-DUAL | REQ-F-064〜068 | **要求③** 判別せず2種類を常に出力 (`.table.md` / `.grid.md`)。1回の解析から両方を生成する | P006 §2.1 F-13 | [T001](./P008-test-direction/T001-excel-dual-output.md) | `pytest tests/acceptance/test_core_requirements.py -k "two_outputs or no_detection or output_mode" -v` | PASS | [A001](./P009-acceptance-direction/A001-core-requirements.md) / [0850](./test-records/20260824-0850-test-record.md) | OK | - |
| SPEC-SHAPE-001 | REQ-F-031〜040 | **要求A** オートシェープ内テキスト (3形式共通・SmartArt・グラフ・テキストボックス・章末への追記・OCRしない) | P006 §2.1 F-14 | [T002](./P008-test-direction/T002-shape-text-e2e.md) | `pytest tests/integration/test_shape_text_e2e.py tests/unit/test_shapes.py tests/unit/test_smartart.py tests/unit/test_charts.py -v` | PASS | [A001](./P009-acceptance-direction/A001-core-requirements.md) / [0850](./test-records/20260824-0850-test-record.md) | OK | - |
| SPEC-PPT-001 | REQ-F-041〜047 | PowerPoint 変換 (スライド単位の章立て・タイトル・本文・ノート・表・非表示スライド) | P006 §2.1 F-15 | [T003](./P008-test-direction/T003-word-powerpoint.md) | `pytest tests/integration/test_word_powerpoint.py tests/unit/test_powerpoint_parser.py -v` | PASS | [0850](./test-records/20260824-0850-test-record.md) | OK | - |
| SPEC-IMG-001 | REQ-F-048, 049, 070 | 画像のうち**代替テキストの抽出・出力有無の指定 (`--images`)・OCRを行わないこと** (`_assets/` への保存は下の副IDへ分離) | P006 §2.1 F-17 | [T003](./P008-test-direction/T003-word-powerpoint.md) | `pytest tests/unit/test_images.py tests/unit/test_markdown_render.py tests/acceptance/test_core_requirements.py::test_no_ocr -v` | PASS | [0850](./test-records/20260824-0850-test-record.md) | OK | - |
| **REQ-F-069-保存** | REQ-F-069 | 画像バイナリの `_assets/` への保存と、二重出力での共有 (親 SPEC-IMG-001 から切り出し) | P006 §2.1 F-17 | [T003](./P008-test-direction/T003-word-powerpoint.md) | **自動テストなし** (`writer.py` の行カバレッジ 55%)。P302 で手動確認のみ実施 | 手動確認は PASS | [0855](./test-records/20260824-0855-test-record.md) §3.2 | **NO_TEST_IMPL** | **要対応** — 実際に `_assets/0001.png` が保存されリンクが張られることは手動で確認したが、**自動テストが無く回帰を検出できない**。回帰テストの追加を推奨 |
| SPEC-CLI-001 | REQ-F-090〜092, 094〜099 | CLI (convert / inspect / --version / --help / 進捗と結果サマリ / --quiet / --verbose / --stdout / 終了コード / TOML設定ファイルと優先順位 / Excelオプション群) | P006 §2.1 F-18〜F-20 | [T004](./P008-test-direction/T004-cli-screens.md) | `pytest tests/integration/test_cli_screens.py tests/unit/test_cli_main.py tests/unit/test_cli_options.py tests/unit/test_config.py -v` | PASS | [0850](./test-records/20260824-0850-test-record.md) / [F001](./P202-fix-plan/fixed/F001-config-precedence.md) / [F002](./P202-fix-plan/fixed/F002-skipped-count.md) | OK | - |
| SPEC-CLI-002 | REQ-F-093 | 原因と対処が判るエラー (E-001〜E-019 のうち **E-004 以外**) | P006 §2.1 F-16 | [T005](./P008-test-direction/T005-errors-security.md) | `pytest tests/unit/test_errors.py tests/unit/test_convert.py tests/unit/test_detect.py tests/integration/test_cli_screens.py -v` | PASS | [0850](./test-records/20260824-0850-test-record.md) | OK | - |
| **REQ-F-093-E004** | REQ-F-093 | E-004 (出力先に書き込めない) の実挙動 (親 SPEC-CLI-002 から切り出し) | P006 §2.1 F-16 | [T005](./P008-test-direction/T005-errors-security.md) | 自動テストは環境依存のため `skipif`。P302 で `icacls /deny` を用いて手動検証 | 手動検証は PASS (終了コード2・所定メッセージ・トレースなし) | [0855](./test-records/20260824-0855-test-record.md) §3.1 | NOT_RUN (自動テスト) | **代替検証** — P302 の手動検証 ([0855](./test-records/20260824-0855-test-record.md) §3.1) で仕様どおりの挙動を確認済み。自動テスト側は Windows の権限操作が環境依存のため `skipif` のまま |
| SPEC-API-001 | REQ-F-100〜103 | ライブラリ API (公開関数・バイト列入力・結果オブジェクト・型ヒントと `py.typed`) | P006 §2.1 F-21 | [A002](./P009-acceptance-direction/A002-usage-scenarios.md) | `pytest tests/acceptance/test_usage_scenarios.py -k "library or convert_bytes or excel_markdown" -v` / `pytest tests/acceptance/test_quality_gates.py -k "public_symbols or py_typed" -v` | PASS | [A002](./P009-acceptance-direction/A002-usage-scenarios.md) / [0850](./test-records/20260824-0850-test-record.md) | OK | - |
| SPEC-NFR-PERF | REQ-NF-001〜003 | 性能 (1ファイル10秒以内・バッチ劣化1.5倍以内・50MBでメモリ2GB以内) | P006 §9 | [A004](./P009-acceptance-direction/A004-nonfunctional.md) | `pytest tests/acceptance/test_nonfunctional.py -m perf -v` | PASS (1.48秒 / 25.1MB。いずれも目標の1/6以下) | [0850](./test-records/20260824-0850-test-record.md) §4 | OK | - |
| SPEC-NFR-ERR | REQ-NF-004, 005 | クラッシュせず必ずエラー終了する・スタックトレースを露出しない | P006 §2.2 N-04 | [T005](./P008-test-direction/T005-errors-security.md) / [A002](./P009-acceptance-direction/A002-usage-scenarios.md) | `pytest tests/acceptance/test_usage_scenarios.py::test_error_messages_are_japanese_without_traceback tests/unit/test_errors.py -v` | PASS | [0850](./test-records/20260824-0850-test-record.md) | OK | - |
| SPEC-NFR-SEC | REQ-NF-006〜009 | セキュリティ (ZIP爆弾の上限・XXE無効化・パストラバーサル検出・マクロを実行しない) | P006 §2.2 N-05〜N-08 | [T005](./P008-test-direction/T005-errors-security.md) | `pytest tests/unit/test_zip_reader.py tests/unit/test_xml_utils.py tests/acceptance/test_quality_gates.py::test_security_coverage -v` | PASS | [0850](./test-records/20260824-0850-test-record.md) | OK | - |
| SPEC-NFR-NET | REQ-NF-010 | 変換中に外部通信を行わない | P006 §2.2 N-09 | [A004](./P009-acceptance-direction/A004-nonfunctional.md) | `pytest tests/acceptance/test_nonfunctional.py::test_no_external_binaries -v` + P302 でソケット生成を禁止した状態での実変換 | PASS | [0855](./test-records/20260824-0855-test-record.md) §3.3 | OK | - |
| SPEC-NFR-ARCH | REQ-NF-011 | 中間表現を経由する三層構造 (パーサ → models → レンダラ。依存は一方向) | P006 §2.2 N-10 | [A005](./P009-acceptance-direction/A005-quality-gates.md) | `pytest tests/unit/test_models.py tests/unit/test_render_dispatch.py -v` / [ADR-004](./ADR.md) | PASS | [0850](./test-records/20260824-0850-test-record.md) | OK | - |
| SPEC-NFR-QUAL | REQ-NF-012 | 保守性 (ruff / mypy strict / 行カバレッジ80%以上) | P006 §8 | [A005](./P009-acceptance-direction/A005-quality-gates.md) | `pytest tests/acceptance/test_quality_gates.py -v` | PASS (カバレッジ 88%) | [0850](./test-records/20260824-0850-test-record.md) §5・§6 | OK | - |
| SPEC-NFR-LOG | REQ-NF-013, 014 | ログ (標準エラーへ出力・形式指定可・**本文テキストを出さない**) | P006 §2.2 N-11 | [A005](./P009-acceptance-direction/A005-quality-gates.md) | `pytest tests/acceptance/test_quality_gates.py -k "log or canary" tests/unit/test_logging.py -v` | PASS (カナリア文字列がログに現れないことを確認) | [0850](./test-records/20260824-0850-test-record.md) | OK | - |
| SPEC-NFR-PAR | REQ-NF-015 | 並列実行 (`--jobs` でワーカー数を指定でき、結果が逐次実行と一致する) | P006 §2.2 N-03 | [A004](./P009-acceptance-direction/A004-nonfunctional.md) | `pytest tests/acceptance/test_nonfunctional.py -k "parallel or jobs" -v` | PASS | [0850](./test-records/20260824-0850-test-record.md) | OK | - |
| SPEC-NFR-I18N | REQ-NF-016 | 日本語・機種依存文字の正しい扱い (ファイル名・本文・出力エンコーディング) | P006 §2.2 N-02 | [A001](./P009-acceptance-direction/A001-core-requirements.md) | `pytest tests/acceptance/test_core_requirements.py::test_japanese_filenames tests/unit/test_escape.py -v` | PASS | [0850](./test-records/20260824-0850-test-record.md) | OK | - |
| SPEC-NFR-PY | REQ-NF-017 | Python 3.11 **以上**で動作する (3.11 そのものでの実行は下の副IDへ分離) | P006 §2.2 N-01 | [A004](./P009-acceptance-direction/A004-nonfunctional.md) | `pytest tests/acceptance/test_nonfunctional.py::test_runs_on_current_python -v` + P302 で 3.13・3.14 の2版で全件実行 | PASS (3.13.14 / 3.14.2 とも539件合格) | [0855](./test-records/20260824-0855-test-record.md) §1 | OK | - |
| **REQ-NF-017-311** | REQ-NF-017 | **Python 3.11 そのもの**での実行時動作 (親 SPEC-NFR-PY から切り出し) | P006 §2.2 N-01 | [A004](./P009-acceptance-direction/A004-nonfunctional.md) | 新規 venv (Python 3.11.14) で `pytest -q` (`test_runs_on_python_311` を含む) | **PASS** (693件合格。※CR 改修時に解消) | [0233](./test-records/20261014-0233-test-record.md) §4 | OK | - |
| SPEC-NFR-IDEM | REQ-NF-018 | 冪等性 (同じ入力から同じ出力。`converted_at` を除く全体が一致する) | P006 §2.3 O-01・O-02 | [A003](./P009-acceptance-direction/A003-rerun-operations.md) | `pytest tests/acceptance/test_rerun_operations.py -v` / `pytest tests/acceptance/test_nonfunctional.py -k idempotent -v` | PASS | [0850](./test-records/20260824-0850-test-record.md) §3 | OK | - |
| SPEC-NFR-DIST | REQ-NF-019 | `pip install` で導入でき、外部バイナリを必要としない (P004 が **P302 へ委譲**と明記した項目) | P006 §2.2 N-01 | [A004](./P009-acceptance-direction/A004-nonfunctional.md) | `pytest tests/acceptance/test_nonfunctional.py::test_no_external_binaries -v` + P302 で wheel をクリーン環境に導入して実行 | PASS (依存6件のみ。外部バイナリの導入なし。※CR 改修後は依存7件 (PyMuPDF を追加。wheel に MuPDF を同梱) で同様に確認 [0233](./test-records/20261014-0233-test-record.md) §2) | [0855](./test-records/20260824-0855-test-record.md) §2 | OK | - |
| SPEC-DIST-DOCKER | - | Docker / docker compose による配布。**要求に対応する項目が無い** (`SKILL-P302-deliver.md` の配布資産整備方針にもとづき追加したため、要求IDは `-`) | - | - | `cd deploy && docker compose build` / `docker compose run --rm convert --version` / `docker compose run --rm convert convert /work/in -o /work/out` | **PASS** (※CR 改修時に解消。`network_mode: none` で変換成功) | [0233](./test-records/20261014-0233-test-record.md) §3 | OK | - |
| **SPEC-PDF-CORE** ※CR-001 | REQ-F-110〜121, REQ-NF-020 | PDF 入力 (形式判定・タグ付き/タグなしの判定・見出し/リスト/表/段落・図表内テキスト・代替テキスト・スキャン警告・メタデータ・暗号化/破損/展開爆弾) | P006 §2.1 F-18〜F-20, §2.2 N-18, §7.5 | [T006](./P008-test-direction/T006-pdf-conversion.md) / [A006](./P009-acceptance-direction/A006-pdf-acceptance.md) | `pytest tests/unit/test_pdf_*.py tests/integration/test_pdf_conversion.py tests/acceptance/test_pdf_acceptance.py -v` | PASS | [0230](./test-records/20261014-0230-test-record.md) | OK | - |
| **SPEC-PDF-LAYOUT** ※CR-002 | REQ-F-122〜128 | PDF のヘッダー・フッター除去 (`--headers-footers` で無効化)・段組みの読み順・Artifact の除外・構造ツリー順・stats の記録 | P006 §2.1 F-21, §7.5 | [T006](./P008-test-direction/T006-pdf-conversion.md) / [A006](./P009-acceptance-direction/A006-pdf-acceptance.md) | `pytest tests/unit/test_pdf_layout.py tests/unit/test_pdf_content.py tests/integration/test_pdf_conversion.py tests/acceptance/test_pdf_acceptance.py -v` | PASS | [0230](./test-records/20261014-0230-test-record.md) | OK | - |
| **SPEC-PDF-LICENSE** ※CR-001・※CR-003 | REQ-NF-019, **REQ-NF-021** | PDF ライブラリと実行時依存のライセンスが MIT と両立すること (※CR-003 で pdfminer.six に差し替え) | P006 §2.2 N-19 | [A007](./P009-acceptance-direction/A007-dependency-licenses.md) | `pytest tests/acceptance/test_dependency_licenses.py -v` | **PASS** (実行時依存 20 件すべて非コピーレフト) | [0747](./test-records/20261014-0747-test-record.md) | OK | - |

### 網羅性の確認

* `docs/P004-traceability-matrix.md` に載る要求IDは **124件** (REQ-F 103件 + REQ-NF 21件。※CR-001・CR-002 で REQ-F-110〜128・REQ-NF-020、※CR-003 で REQ-NF-021 を追加)。
* 上表の「要求ID」列に現れる ID を展開すると、REQ-F-001〜070・REQ-F-090〜103・REQ-F-110〜128・REQ-NF-001〜021 の **124件すべてが現れる** (REQ-F-071〜089 は欠番であり、P004 にも存在しない)。**本表から漏れた要求IDは無い。**
* 親から切り出した副IDは3件 (`REQ-F-069-保存` / `REQ-F-093-E004` / `REQ-NF-017-311`)。いずれも親と同じ要求IDを「要求ID」列に持ち、親行の「仕様内容」欄には切り出した範囲を除いたことを明記した。

### 状態の集計

| 状態 | 件数 | 内訳 |
| --- | --- | --- |
| OK | 30 | (※CR-001・002: REQ-NF-017-311・SPEC-DIST-DOCKER が OK、SPEC-PDF-CORE・SPEC-PDF-LAYOUT を追加 / ※CR-003: SPEC-PDF-LICENSE が OK) |
| NO_TEST_IMPL | 1 | REQ-F-069-保存 |
| NOT_RUN | 1 | REQ-F-093-E004 (自動テストのみ。手動は PASS) |
| BLOCKED | 0 | — |

### 出荷影響の集計

| 出荷影響 | 件数 | 内訳 |
| --- | --- | --- |
| `-` (状態 OK) | 30 | — |
| 代替検証 | 1 | REQ-F-093-E004 → [0855](./test-records/20260824-0855-test-record.md) §3.1 の手動検証でカバー |
| **要対応** | **1** | REQ-F-069-保存。※CR-003 で SPEC-PDF-LICENSE を解消 |
| 本番検証・自明 | 0 | — |

---

## 5. バージョン情報とビルド履歴

### バージョンの正本

| 項目 | 内容 |
| --- | --- |
| **正本** | `app/pyproject.toml` の `project.version` = **1.1.0** (2026-10-15 に 1.0.0 から変更) (Python 標準の定義。`SKILL-P302-deliver.md` の優先順位(1)) |
| 同期先 | `app/src/office2ragknowledge/__init__.py` の `__version__ = "1.1.0"`、`deploy/Dockerfile` のラベル、`deploy/compose.yml` のイメージのタグ |
| 仕様上の定義 | `docs/P002-frontend-spec.md` §3.1 (SCR-01 `--version` の表示内容) |
| `VERSION` ファイル | **作成しない** (2章の理由を参照) |

### 実行モジュールからのバージョン確認

**確認できる。** 実際に実行して確認した ([0855](./test-records/20260824-0855-test-record.md) §2.2)。

```text
$ office2rag --version
office2rag 1.0.0 (office2ragknowledge)
Python 3.14.2 / lxml 6.1.2 / python-docx 1.2.0 / openpyxl 3.1.5 / python-pptx 1.0.2
```

本体版数だけでなく**依存ライブラリの版数も表示する**ため、利用者環境での不具合報告時に切り分けが行える。また、変換した Markdown の front matter にも `converter: "office2ragknowledge 1.0.0"` が記録されるため、**出力物からも生成に使った版数を追える**。

### 版数を 1.1.0 に上げた (2026-10-15)

**依頼者の指示 (「版数をあげてコミットしてください」2026-10-15) により、版数を `1.0.0` から `1.1.0` に上げた。** PDF 入力の追加 (CR-001〜CR-003) は後方互換な機能追加であり、セマンティックバージョニングのマイナー版の更新にあたる。下記の ★FIXME★ (版数の据え置き) は解消した。`docs/P002-frontend-spec.md` §3.2 の表示例も 1.1.0 に合わせた。版数の `0.1.0` への変更 (10.3章 CR候補②) は行っていない。

### ※CR-001・CR-002 改修時の版数 (履歴)

PDF 入力の追加は**後方互換な機能追加**であり、慣例 (セマンティックバージョニング) では `1.1.0` に上げる場面である。しかし本フェーズでは**版数を `1.0.0` のまま据え置いた**。理由は下記の申し送りと同じで、版数の変更は `docs/P002-frontend-spec.md` §3.1・§3.2 の表示例の修正 (仕様変更) を伴い、かつ版数の方針は人間の判断事項として申し送られているためである。**結果として、同じ `1.0.0` で PDF 非対応 (BLD-20260824-0847)・PyMuPDF 版 (BLD-20261014-0232)・pdfminer.six 版 (BLD-20261014-0750。※CR-003) の3種類の生成物が存在する。** 版上げ (推奨: `1.1.0`) の要否を人間が判断されたい (10.3章 CR候補④)。

### 版数についての申し送り ★FIXME★

`SKILL-P302-deliver.md` は「新規にバージョン定義を作成する場合の初期値は `0.1.0` とし、`1.0.0` への移行は人間から明示的な指示があった場合にのみ行う」と定めている。本アプリの `1.0.0` は P102 (実装) の時点で設定された値であり、**人間の明示的な指示にもとづくものではない**。

本フェーズでは `0.1.0` へ変更**しなかった**。理由は、`1.0.0` が `docs/P002-frontend-spec.md` §3.1 の表示仕様に文字列として書かれており、**変更すると設計書の修正 (仕様変更) を伴う**ためである (P302 は仕様変更を行わない)。版数を `0.1.0` に揃えるべきかどうかは人間が判断し、揃える場合は CR として起票することを推奨する (10.3章 CR候補②)。

### ビルド履歴

[../BUILD_HISTORY.md](../BUILD_HISTORY.md) を新規に作成した。

| Build ID | Version | Date/Time | Commit | Result |
| --- | --- | --- | --- | --- |
| BLD-20260824-0847 | 1.0.0 | 2026-08-24 08:47 (JST) | `0923b6d` (**作業ツリー未コミット**) | PASS |
| BLD-20261014-0232 (※CR-001・002) | 1.0.0 | 2026-10-14 02:32 (JST) | `81a04d2` (**作業ツリー未コミット**) | PASS (wheel・sdist・Docker イメージ。PyMuPDF 版) |
| BLD-20261014-0750 (※CR-003) | 1.0.0 | 2026-10-14 07:50 (JST) | `81a04d2` (**作業ツリー未コミット**) | PASS (wheel・sdist・Docker イメージ。pdfminer.six 版) |
| **BLD-20261015-0019** | **1.1.0** | 2026-10-15 00:19 (JST) | 本コミット (下記) | PASS (wheel・sdist・Docker イメージ) |

**Commit 欄には注意が要る。** リポジトリの唯一のコミットは `0923b6d` (Initial commit) であり、`app/` `docs/` `deploy/` を含むアプリケーション一式は**まだ git にコミットされていない** (`git status` 上 untracked)。したがってこの Build ID からビルド対象のソースを一意に復元できない。10.2章に未整備事項として記載した。

---

## 6. 配布資産一覧

### 本フェーズで新規に作成した資産

| ファイル | 内容 | 検証状況 |
| --- | --- | --- |
| [../deploy/Dockerfile](../deploy/Dockerfile) | 2段構成 (builder で wheel を作り、実行イメージには wheel だけを入れる)。`python:3.12-slim` ベース、非 root 実行 (`UID` 引数で切替可)。※CR-001 でラベルの説明に PDF を追加、**※CR-003 で `licenses` を `MIT` に戻した** | **検証済み** (※CR-003 改修時。[0752](./test-records/20261014-0752-test-record.md) §4。イメージ 203 MB) |
| [../deploy/compose.yml](../deploy/compose.yml) | `convert` サービス1件。入力を読み取り専用、出力を書き込み可でマウント。`network_mode: none` (REQ-NF-010 に対応) | **検証済み** (※CR 改修時。`docker compose run` で Word・Excel・PDF を変換) |
| [../deploy/.env.example](../deploy/.env.example) | `INPUT_DIR` / `OUTPUT_DIR` / `CONFIG_FILE` / `UID` の記入例 | — |
| [../BUILD_HISTORY.md](../BUILD_HISTORY.md) | ビルド履歴 | 実ビルドにもとづく |

### 既存の資産 (本フェーズで検証した)

| ファイル / 生成物 | 内容 | 検証状況 |
| --- | --- | --- |
| `app/dist/office2ragknowledge-1.1.0-py3-none-any.whl` | **配布用 wheel** (119.6 KB。1.0.0 の生成物は `app/dist/archive-20260824/` (PDF 非対応)・`archive-20261014-pymupdf/`・`archive-20261014-pdfminer-1.0.0/` に退避) | **検証済み** — クリーンな venv に導入し `--version` / `convert` (PDF を含む) / `inspect` の動作を確認 |
| `app/dist/office2ragknowledge-1.1.0.tar.gz` | sdist (174.1 KB) | ビルド成功を確認 |
| `app/pyproject.toml` | パッケージ定義・依存7件 (※CR-003 で `pymupdf` を `pdfminer.six` に差し替え)・開発時依存に `pypdf[crypto]`・`office2rag` エントリポイント・ruff/mypy/pytest 設定 | **検証済み** |
| [../app/README.md](../app/README.md) | 導入と使い方 | — |
| [../app/INDEX.md](../app/INDEX.md) | ソースツリーの目次 | — |

### 設定ファイルの例

TOML 設定ファイル (REQ-F-098) は、既定で `./office2rag.toml` を読む。`--config` で明示指定もできる。

```toml
[convert]
output_dir = "./out"
recursive = true
jobs = 4
images = "extract"          # none | link | extract

[excel]
modes = "both"              # both | table | grid
max_table_regions = 100
formulas = true             # 計算結果を持たない数式セルに数式文字列を出す

[log]
level = "info"              # quiet | info | verbose
format = "text"             # text | json
```

優先順位は **CLIオプション > 設定ファイル > 既定値** である (REQ-F-098)。これは P201 で欠陥 F001 として検出し、修正済みである ([P202-fix-resolved.md](./P202-fix-plan/P202-fix-resolved.md))。

---

## 7. 起動・実行手順

### 7.1 CLI 実行手順 (推奨。wheel 版)

本手順は **P302 で実際に実行して確認した** ([0855](./test-records/20260824-0855-test-record.md) §2.2)。

```bash
# 1. 配布物を取得する
#    app/dist/office2ragknowledge-1.1.0-py3-none-any.whl を入手する
#    (自分でビルドする場合: cd app && python -m build --wheel --outdir dist)

# 2. 依存関係をインストールする (仮想環境を推奨。Python 3.11 以上)
python -m venv .venv
.venv/Scripts/activate          # Windows。Linux/macOS は source .venv/bin/activate
pip install office2ragknowledge-1.1.0-py3-none-any.whl

# 3. バージョンを確認する
office2rag --version

# 4. ヘルプを確認する
office2rag --help
office2rag convert --help

# 5. サンプル入力で実行する
#    5a. 変換前に中身を見積もる (図形の数・表領域の数・数式セルの数が判る)
office2rag inspect ./in -r

#    5b. ディレクトリを再帰的に一括変換する
office2rag convert ./in -r -o ./out

#    5c. 1ファイルだけ標準出力に出す (パイプ処理向け)
office2rag convert ./in/report.docx --stdout | your-rag-indexer

# 6. 出力結果を確認する
ls ./out
```

出力例:

```text
report.md
申請書.table.md      ← Excel を表計算として読んだ Markdown
申請書.grid.md       ← Excel を方眼紙として読んだ Markdown
```

**Excel は1ファイルから2つの Markdown が出る**点に注意する (要求③)。片方だけが要る場合は `--excel-modes table` または `--excel-modes grid` を指定する。`--stdout` で Excel を扱う場合は、出力先が1つしかないため**モードの単一指定が必須**である (指定が無いと E-017 で終了する)。

### 7.2 ライブラリとしての利用手順

```python
from pathlib import Path
from office2ragknowledge import ConvertOptions, convert_file

result = convert_file(Path("申請書.xlsx"), ConvertOptions())

for output in result.outputs:            # Excel は2件、Word/PowerPoint は1件
    print(output.mode, len(output.text))  # mode は "table" / "grid" / None
    Path(output.suggested_name).write_text(output.text, encoding="utf-8")

for warning in result.warnings:          # 変換時の警告 (取りこぼしの可能性など)
    print(warning)
```

* `convert_file` は**ファイルを書き出さない**。書き出しは呼び出し側の責務である (A002 で確認済み)。
* バイト列を直接渡す `convert_bytes` もあり、Web アプリのアップロード処理から使える。
* ライブラリとして使う場合、**既定ではログを出力しない** (利用側のログ設定を汚さない)。

### 7.3 Docker での実行手順 (**※CR 改修時に検証済み**)

> 2026-10-14 に WSL2 + Docker 29.7.2 で、下記の `build`・`--version`・`convert` を実行して確認した ([0233](./test-records/20261014-0233-test-record.md) §3)。`inspect` は wheel 版で確認している。
>
> **ライセンス (※CR-003)**: イメージ内のアプリの実行時依存はすべて MIT と両立するライセンスである (PyMuPDF を含まない。ラベル `licenses` = `MIT`)。

```bash
cd deploy
cp .env.example .env
# .env を編集し、INPUT_DIR に変換したい文書のディレクトリ、OUTPUT_DIR に出力先を書く

docker compose build

# 変換 (本アプリは常駐しないので up ではなく run を使う)
docker compose run --rm convert convert /work/in -r -o /work/out

# 事前確認
docker compose run --rm convert inspect /work/in -r

# バージョン確認
docker compose run --rm convert --version
```

`docker compose up` は使わない。本アプリは待ち受けるサービスではなく、実行して終了する CLI だからである (3章参照)。

### 7.4 異常終了時の扱い (バッチ運用)

| 終了コード | 意味 | 再実行の可否 |
| --- | --- | --- |
| **0** | 全件成功 | 再実行しても同じ結果になる (冪等。REQ-NF-018) |
| **1** | 一部が失敗 (残りは変換済み) | **そのまま再実行してよい。** 既定では既存の出力を上書きし、成功済みのファイルは同じ内容で再生成される |
| **2** | 実行前異常 (入力パス不正・設定エラー・出力先に書けないなど。1件も処理していない) | 原因を解消してから再実行する |

* 失敗したファイルがあっても**バッチ全体は止まらない**。他のファイルの変換は続行される (A002 で確認済み)。
* 中間ファイルや一時ファイルは残らない (A003 `test_no_temp_files_remain` で確認済み)。

---

## 8. テスト実行手順

前提: `cd app` で実行する。開発用の依存を含めて導入する (`pip install -e ".[dev]"`)。※CR-001: 開発時依存に `pypdf[crypto]` が含まれる (テスト用の暗号化 PDF の生成に使う)。

| レベル | コマンド | 件数 | 目的 |
| --- | --- | --- | --- |
| **単体テスト** | `pytest tests/unit -v` | 518 (※CR-003 改修後) | モジュール単位の振る舞い |
| **結合テスト** | `pytest tests/integration -v` | 79 (※CR 改修後) | T001〜T006 (スプリント内 / モジュール間) |
| **受け入れ・システムテスト** | `pytest tests/acceptance -v` | 110 (※CR-003 改修後) | A001〜A007 (要求の充足・運用・非機能・品質ゲート・PDF・依存ライセンス) |
| **全件** | `pytest tests -q` | **707 (706 + skip 1。Python 3.11 では skip 0)** | 上記すべて |
| **性能テスト** | `pytest tests/acceptance -m perf -v` | 4 | 既定では `addopts` により除外されている |
| **カバレッジ付き** | `pytest tests -q --cov=office2ragknowledge --cov-report=term-missing` | 707 | 目標80%以上 |
| **静的検査** | `ruff check src tests` / `ruff format --check src tests` / `mypy src` | — | いずれもエラー0件が条件 |

上記のコマンドは**すべて実際に実行して確認している** ([0855](./test-records/20260824-0855-test-record.md) §1)。

### テスト結果の格納先

`docs/test-records/YYYYMMDD-HHMM-test-record.md` に記録する。現在7件ある (初回の P103 / P205 / P302 と、※CR 改修時の P103 (0225) / P201 (0227) / P205 (0230) / P302 (0233))。

### 合格条件

1. `pytest tests` が **失敗0件**であること (スキップは、理由が記録されていれば許容する)。
2. **テストスイートを続けて2回実行しても同じ結果になる**こと (観点 O-03。[0850](./test-records/20260824-0850-test-record.md) §3 で確認済み)。
3. `ruff check` / `ruff format --check` / `mypy src` がいずれもエラー0件であること。
4. 行カバレッジが 80% 以上であること (REQ-NF-012)。

---

## 9. 最終確認結果

### 9.1 実行して確認したこと

| # | 確認内容 | 結果 | 証跡 |
| --- | --- | --- | --- |
| 1 | テストスイート全件 (Python 3.14.2) | **539 passed, 1 skipped** (77.5秒) | [0855](./test-records/20260824-0855-test-record.md) §1 |
| 2 | テストスイート全件 (**Python 3.13.14**、新規 venv) | **539 passed, 1 skipped** (92.5秒) | 同上 |
| 3 | `ruff check` / `ruff format --check` / `mypy src` | すべてエラー0件 | 同上 |
| 4 | wheel / sdist のビルド | 成功 (92.7 KB / 126.7 KB) | 同上 §2.1 |
| 5 | **クリーンな venv に wheel だけを導入して実行** | `--version` / `convert -r` / `inspect` すべて正常。外部バイナリの導入なし | 同上 §2.2 |
| 6 | 変換結果が P001 §7.3 の期待出力と一致するか | **一致** (方眼紙モードの申請書) | 同上 §2.2 |
| 7 | **E-004 (書き込み不可の出力先)** | 終了コード2・所定のメッセージ・トレースなし | 同上 §3.1 |
| 8 | **画像抽出 `--images extract`** | `_assets/0001.png` を保存しリンクを生成。代替テキストも取得 | 同上 §3.2 |
| 9 | **外部通信を行わないこと** | ソケット生成を禁止した状態で3ファイルすべて変換成功 | 同上 §3.3 |

**7〜9 は、P205 が「未検証」として P302 へ引き継いだ4件のうちの3件である。本フェーズで解消した。**

#### ※CR-001・CR-002 改修時 (2026-10-14) に実行して確認したこと

| # | 確認内容 | 結果 | 証跡 |
| --- | --- | --- | --- |
| 10 | テストスイート全件 (Python 3.12.12、2回連続) | **692 passed, 1 skipped** (同じ結果) | [0230](./test-records/20261014-0230-test-record.md) |
| 11 | **テストスイート全件 (Python 3.11.14、新規 venv、2回連続)** | **693 passed** (skip 0) | [0233](./test-records/20261014-0233-test-record.md) §4 |
| 12 | 静的検査・カバレッジ | エラー0件・90% | [0230](./test-records/20261014-0230-test-record.md) |
| 13 | クリーンな venv に wheel だけを導入して PDF を変換 | `--version` に PyMuPDF の版、`convert`・`inspect` 正常 | [0233](./test-records/20261014-0233-test-record.md) §2 |
| 14 | **Docker イメージのビルドと実行** | `build` 成功・`run --version`・`run convert` (ネットワーク無効) 成功 | 同上 §3 |
| 15 | 性能 (既存の `-m perf` 4件と、PDF 50ページの合成データ) | 既存4件合格。PDF 50ページ 0.35〜0.58 秒 (PyMuPDF 版) | [0230](./test-records/20261014-0230-test-record.md) / [0233](./test-records/20261014-0233-test-record.md) §4 |
| 16 | **※CR-003: テストスイート全件 (3.12 / 3.11、新規 venv)** | **706 passed / 707 passed** (3.12 は2回連続で同じ) | [0747](./test-records/20261014-0747-test-record.md) |
| 17 | **※CR-003: 実行時依存のライセンス (A007)** | 20 件すべて非コピーレフト。PyMuPDF を含まない | 同上 |
| 18 | **※CR-003: PDF の性能 (pdfminer.six)** | 50ページ 1.18〜2.07 秒、最大常駐メモリ約 73 MB (目標 10 秒・2 GB) | 同上 |
| 19 | **※CR-003: 差し替え前後の出力の比較 (A/B)** | 7件中6件が完全一致。1件 (ページをまたぐ段落) は pdfminer.six 版のみ正しく連結 | [0752](./test-records/20261014-0752-test-record.md) §3 |
| 20 | **※CR-003: wheel・Docker** | クリーン環境で動作。Docker 203 MB・ラベル `MIT` | 同上 §1・§2・§4 |

* **P302 で見つけて是正したこと**: 新規 venv の構築で、開発時依存 `pypdf` に AES 用の `cryptography` が含まれない宣言漏れが見つかった (それまでの venv にはスパイクの依存として偶然入っていた)。`pypdf[crypto]` に改めた ([0233](./test-records/20261014-0233-test-record.md) §4.1)。アプリケーションと配布物の実行時依存には影響しない。

### 9.2 確認できなかったこと

| # | 内容 | 理由 |
| --- | --- | --- |
| 1 | ~~**Python 3.11 での実行時動作**~~ **→ ※CR 改修時に確認済み (§9.1 #11)** | (当時) 本環境に Python 3.11 が無い (`py -0p` の結果は 3.13 と 3.14 のみ)。`mypy --python-version 3.11` は通過し、3.12+ 専用構文 (PEP 695) も使っていないが、実行時の確認には代えられない |
| 2 | ~~**Docker イメージのビルドと起動**~~ **→ ※CR 改修時に確認済み (§9.1 #14)** | (当時) 本環境に Docker が無い (`docker: command not found`)。`deploy/Dockerfile` / `deploy/compose.yml` は作成したが、**ビルドが通るかどうかも確認していない** |

**上記2点は※CR 改修時 (2026-10-14) に確認し、解消した。**

| # | ※CR 改修時に確認できなかったこと | 理由 |
| --- | --- | --- |
| 3 | **実際の業務 PDF (Word・Acrobat・InDesign 等が出力したタグ付き PDF、スキャン PDF、数百ページの PDF) での変換品質と性能** | テストはすべて本アプリのヘルパが生成した PDF で行った。MuPDF の挙動は PDF の作り方で変わる (ArchitectureHandbook §4-8・§4-13) ため、実データでの確認が望ましい (10.2章⑨) |
| 4 | **Windows での PDF 変換** | 改修と検証は WSL2 (Linux) で行った。PyMuPDF は Windows 用 wheel を提供しているが、Windows 上で本スイートを実行していない (10.2章⑩) |

---

## 10. 未整備事項・人間による確認事項

### 10.1 出荷に影響する事項 (※CR-003 改修後: 要対応 1件)

| # | 事項 | 内容と推奨する対処 |
| --- | --- | --- |
| ~~**①**~~ ※CR-001 | ~~**PDF ライブラリ PyMuPDF のライセンス (AGPL-3.0)** (SPEC-PDF-LICENSE)~~ **→ ※CR-003 で解消** (pdfminer.six (MIT) に差し替え。A007 で検査) | 本アプリは MIT だが、PDF の読み取りに使う PyMuPDF は AGPL-3.0 (または Artifex の商用ライセンス) である。wheel は依存として、Docker イメージは同梱物として PyMuPDF を含むため、**配布・ネットワーク越しの提供には AGPL-3.0 の条件がかかる**。依頼者は MIT を保つことを求めており、**Docling・PDF Inspector (および pdfminer.six) による代替を検討した** ([research/pdf-library-alternatives.md](./research/pdf-library-alternatives.md))。結論: Docling・PDF Inspector は代替にならず、**pdfminer.six への差し替え (CR-003 候補) を推奨**。依存は `pdf/backend.py` に閉じ込めてあり、差し替えの影響はこの1モジュールと依存の宣言に限られる (ADR-012)。**対処**: 代替の検討結果にもとづき、(a) MIT 互換のライブラリに差し替える、(b) Artifex の商用ライセンスを取得する、(c) AGPL-3.0 の条件を受け入れて配布する、のいずれかを人間が決める |
| ~~**①**~~ | ~~**Docker 資産が動作未検証** (SPEC-DIST-DOCKER)~~ **→ ※CR 改修時に解消** | `deploy/Dockerfile` / `deploy/compose.yml` はビルドも起動も行っていない。**対処**: Docker のある環境で `cd deploy && docker compose build` と `docker compose run --rm convert --version` を1度実行する。wheel によるインストール経路自体はクリーン環境で検証済みなので、失敗するとすればベースイメージの選択かマウント設定であり、修正は軽微と見込まれる |
| ~~**②**~~ | ~~**Python 3.11 での実行が未検証** (REQ-NF-017-311)~~ **→ ※CR 改修時に解消** | 要求は「3.11 以上」だが、確認できたのは 3.13 と 3.14 である。**対処**: 3.11 を導入して `pytest tests -q` を1度実行する。これで `test_runs_on_python_311` のスキップも解消する。あるいは、動作保証を 3.13 以上に狭めるなら**要求の変更**にあたるため CR を起票する (10.3章 CR候補①) |
| **③** | **画像抽出に自動テストが無い** (REQ-F-069-保存) | 手動では動作を確認したが (§9.1 #8)、自動テストが無いため回帰を検出できない (`writer.py` の行カバレッジ 55%)。**対処**: 画像を1点含む `.docx` を `tests/helpers/make_office.py` で生成し、`--images extract` で `_assets/` にファイルが出ることを検証するテストを1件追加する。P302 は実装・テストの追加を行わないため、本フェーズでは追加していない |

### 10.2 運用上の申し送り (出荷は妨げない)

| # | 事項 | 内容 |
| --- | --- | --- |
| ④ | **アプリケーション一式が git にコミットされていない** | 唯一のコミットは `0923b6d` (Initial commit) で、`app/` `docs/` `deploy/` はすべて untracked である。ビルド履歴の Commit 欄からソースを復元できない。**納品前にコミットすること** |
| ⑤ | `app/dist/` がリポジトリに残っている | 本フェーズのビルドで生成された。git 管理下に置くかどうかは運用方針次第 (通常は `.gitignore` に加える)。`.gitignore` は現時点で未作成 |
| ⑥ | E-011 の対処メッセージが状況に合わない場合がある | 対象0件のとき「ディレクトリ配下を探索する場合は `-r` を指定してください」と出るが、**`-r` を既に指定していても同じ文言が出る** (`errors.py` の固定文言のため)。実害は無いが利用者を混乱させうる。文言は `docs/P002-frontend-spec.md` §9.1 に定義されているため、変更するなら CR が要る (10.3章 CR候補③) |
| ⑦ | T005 のテスト実装が指示書と別の場所にある | [T005](./P008-test-direction/T005-errors-security.md) は `tests/integration/test_errors_security.py` を指定しているが、**このファイルは存在しない**。検証内容自体は `tests/unit/test_zip_reader.py` `tests/unit/test_xml_utils.py` `tests/unit/test_errors.py` `tests/integration/test_cli_screens.py` `tests/acceptance/test_quality_gates.py` に分散して実装され、すべて合格している (4章 SPEC-CLI-002 / SPEC-NFR-SEC を参照)。**検証の漏れではなく配置の食い違いである**が、T005 に書かれた実行コマンドは現状のままでは動かない |
| ⑨ ※CR | **実際の業務 PDF での確認** | §9.2 #3。代表的な実データ (Word から出力したタグ付き PDF、スキャン PDF、2段組みの論文) で変換結果を目視確認することを推奨する。MCR 辞書形式のタグ付き PDF はタグなしとして変換される既知の挙動がある (Handbook §4-8) |
| ⑩ ※CR | **Windows での PDF 変換の確認** | §9.2 #4。Windows の venv で `pytest tests -q` を1度実行することを推奨する |
| ~~⑪~~ ※CR | ~~**同じ版数 `1.0.0` で内容の異なる生成物がある**~~ **→ 2026-10-15 に 1.1.0 へ上げて解消** (旧生成物は archive に退避) | 5章。PDF 非対応・PyMuPDF 版・pdfminer.six 版の wheel がどれも `1.0.0`。前2者は `app/dist/archive-20260824/`・`archive-20261014-pymupdf/` に退避した。版上げの要否は 10.3章 CR候補④ |
| ⑧ | ★FIXME★ が設計文書に30件残っている | 内訳は [../INDEX.md](../INDEX.md) 7章にある。主なものは性能の目標値 (実測が大きく下回ることを確認済み)、想定利用規模、Excel 出力ファイル名の命名。**いずれも実装済み・テスト済みの内容に関する想定の記録**であり、動作を妨げるものではない |

### 10.3 CR (変更要求) の起票候補

以下は**仕様変更を要する**ため、本フェーズでは対応していない。対応するなら P901 で `docs/P901-cr-direction/CR-NNN.md` として起票する。

| # | CR候補 | 内容 |
| --- | --- | --- |
| **①** | 動作保証する Python の下限の見直し | 3.11 での検証手段が無い状態が続くなら、`requires-python` と REQ-NF-017 を実際に検証できる版 (例: 3.12 以上) に改めるほうが正直である。要求の変更にあたる |
| **②** | 版数を `0.1.0` に揃えるか | 5章の ★FIXME★ を参照。`1.0.0` は人間の指示によらず設定された値であり、ワークフローの既定 (`0.1.0` から始める) と食い違う。揃えるなら `docs/P002-frontend-spec.md` §3.1 の表示仕様の修正を伴う |
| **③** | E-011 の対処メッセージを状況依存にする | 上記⑥。`docs/P002-frontend-spec.md` §9.1 のエラーコード表を「固定文言」から「状況に応じた文言」へ変える設計変更になる |

| ~~**④**~~ ※CR | ~~版数を `1.1.0` に上げるか~~ **→ 2026-10-15 に依頼者の指示で実施** | PDF 入力の追加は後方互換な機能追加である。上げるなら `app/pyproject.toml`・`__init__.py`・`deploy/` のラベルとタグ、`docs/P002-frontend-spec.md` §3.1・§3.2 の表示例を合わせて変える |

### 10.4 ★ACCEPTED★ 済みの既知の制約 (判定材料に数えない)

[ArchitectureHandbook.md](./ArchitectureHandbook.md) §9 に記載済みの、**検討のうえ受け入れた**制約である。リリース判定の根拠には数えないが、利用者への申し送りとして再掲する。

* **SmartArt の階層構造は復元しない** — テキストは回収するが、図形の親子関係は平坦化する。
* **グラフはデータ系列名とカテゴリ名のみを拾う** — 数値データ本体は Markdown 化しない。
* **中間表現では結合セルを展開しない** ([ADR-004](./ADR.md)) — 結合セルの値は左上セルにのみ現れる。表計算モードのレンダラ側で必要な複製を行う。
* ※CR-001・CR-002: **タグなし PDF の表は罫線から復元せず、段組みの誤認がありうる** (罫線の無い表は列ごとに読まれうる)・**縦書きの段組みは対象外**・**PDF の画像バイナリは書き出さない**・**フォントサイズからの見出しの推定はしない** (ADR-013・ADR-014、Handbook §9-14)。
* **方眼紙モードのセル連結に区切り文字を入れない** — 「氏名」「山田太郎」が隣接すると `氏名山田太郎` になる。RAG のチャンク分割では語の境界より意味のまとまりが重要と判断した ([P001](./P001-requirement.md) §7.3 の期待出力どおり)。

---

## 11. リリース判定

### 判定: **保留** (※CR-003 改修後の再判定。2026-10-14)

### 根拠

**保留とする理由 (要対応 1件)**:

| # | 要対応の項目 | なぜ判定を `OK` にできないか |
| --- | --- | --- |
| ① | REQ-F-069-保存 — 画像抽出に自動テストが無い | 初回 (2026-08-24) からの継続。動作は手動で確認したが、回帰を検出する手段が無い |

**※CR-003 で解消したもの**: SPEC-PDF-LICENSE (PyMuPDF の AGPL-3.0)。PDF の読み取りを pdfminer.six (MIT) に差し替え、実行時依存 20 件すべてが MIT と両立することを A007 で確認した。

**それでも `NG` ではない理由**:

* 機能面は**要求124件すべてが充足**しており、**テストは 706件 (3.12) / 707件 (3.11) 全件合格・失敗0件**である。
* CR-001〜CR-003 の受け入れテスト (A006・A007) は全件合格した。
* 残る1件は「動かない」ではなく「回帰を検出できない」であり、対処 (テストを1件追加する) が具体的に判っている。

**判定を `OK` に変えるために必要なこと**: ① 画像抽出の自動テストを加える。(版数は 2026-10-15 に 1.1.0 へ上げた。)

### 4章の対応表との整合

本章が挙げた保留理由1件は、4章の対応表で出荷影響が `要対応` の1行 (REQ-F-069-保存) と**一致している**。

<details><summary>※CR-001・CR-002 改修後 (2026-10-14) の判定 (履歴)</summary>

* 判定: 保留。要対応2件 (SPEC-PDF-LICENSE・REQ-F-069-保存)。SPEC-PDF-LICENSE は ※CR-003 で解消した。

</details>

<details><summary>前回 (2026-08-24) の判定の根拠 (履歴)</summary>


#### 判定: **保留**

#### 根拠

**保留とする理由 (要対応 3件)**:

| # | 要対応の項目 | なぜ判定を `OK` にできないか |
| --- | --- | --- |
| ① | SPEC-DIST-DOCKER — Docker 資産が動作未検証 | 配布資産を作成しておきながらビルドすら確認していない。`SKILL-P302-deliver.md` は「Docker が利用できない環境では資産を整備してよいが、動作確認していないことを明記し、**リリース判定は原則として `保留`** とする」と定めており、これに該当する |
| ② | REQ-NF-017-311 — Python 3.11 での実行が未検証 | 要求は「3.11 以上」である。3.13・3.14 で全件合格しているが、要求が明示した下限そのものは確認できていない。「環境を用意できなかった」ものであり、原理的に確認不能な `本番検証` には該当しない |
| ③ | REQ-F-069-保存 — 画像抽出に自動テストが無い | 動作は手動で確認したが、回帰を検出する手段が無い |

**それでも `NG` ではない理由**:

* 機能面は**要求103件すべてが充足**しており ([P004](./P004-traceability-matrix.md))、**テストは539件全件合格・失敗0件**である。未解決の修正障害も無い ([P202-fix-unresolved.md](./P202-fix-plan/P202-fix-unresolved.md))。
* 主たる配布形式である **wheel は、クリーンな環境で実際に動くことを確認済み**である。要対応①は第二の配布形式 (Docker) の話であり、wheel での利用は妨げられない。
* 要対応3件はいずれも**「動かない」ではなく「確認していない / 回帰を検出できない」**である。3件とも対処方法が具体的に判っており (10.1章)、いずれも短時間で解消できる見込みである。
* 性能は目標を大きく下回り (10秒目標に対し 1.48 秒、2GB目標に対し 25.1 MB)、静的検査もカバレッジも基準を満たしている。

**判定を `OK` に変えるために必要なこと**: 10.1章の①②③を解消する。特に ① と ② は、Docker と Python 3.11 のある環境で各1回コマンドを実行するだけで済む。

#### 4章の対応表との整合

本章が挙げた保留理由3件は、4章の対応表で出荷影響が `要対応` の3行と**一致している**。4章で `OK` としている25行を本章の保留理由には挙げていない。逆に、本章で挙げていない `要対応` の行も無い。

</details>

---

## 付録: このワークフローの完了状況

| Step | フェーズ | 状態 |
| --- | --- | --- |
| Require Development | P001 | 完了 (版1.1。要求①②③とAを反映して再定義) |
| Plan Loop | P002〜P012 | 完了 (P010 第1パスで矛盾4件 → 是正 → 第2パス0件) |
| Overview | P020〜P022 | 完了 |
| Executor | P101〜P104 | 完了 (P103 で 446合格 / 2失敗) |
| Reviewer Loop | P201〜P205 | 完了 (F001〜F003 を修正 → P205 で 539合格 / 0失敗) |
| Closing | P301・P302 | **完了 (本書)** |
| **Refactor (※CR-003)** | P901〜P903 (P002〜P302 の再実行) | **完了** (P010 第1パスで矛盾3件 → 是正 → 第2パス0件。P201 第1回で全件合格のため P202〜P205 は不要)。P904・P905 は本書の後に実施 |
| **Refactor (※CR-001・CR-002)** | P901〜P903 (P002〜P302 の再実行) | **完了** (P010 第1パスで矛盾4件 → 是正 → 第2パス0件。P201 第1回で失敗4件 (テストコード側) → F004〜F006 → 第2回で全件合格)。P904・P905 は本書の後に実施 |

Reviewer Loop の実行回数は **1回**であり、停止条件 (3回) には達していない。
