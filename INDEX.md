# Office2RAGKnowledge — リポジトリ全体の目次

Office 文書 (Word / Excel / PowerPoint) と PDF (※CR-001・CR-002) を、AI の RAG パイプライン向け Markdown に変換するツール。

| 項目 | 内容 |
| --- | --- |
| 状態 | 全フェーズ P001〜P302 完了。**CR-001・CR-002 (PDF 入力)、CR-003 (PDF ライブラリの MIT 化) の Refactor で P002〜P302 を再実行済み** (P904・P905 の反映確認は [docs/CR.md](./docs/CR.md) の状態を参照) |
| **リリース判定** | **OK** (2026-10-15) — 要対応 0件。画像抽出の自動テストが無い件は依頼者の判断で受容 (★ACCEPTED★)。根拠は [docs/P302-deliver.md](./docs/P302-deliver.md) 11章 |
| 版 | **1.1.0** (2026-10-15 に 1.0.0 から変更。正本は `app/pyproject.toml`。`office2rag --version` で確認可) |
| 更新 | 2026-10-14 (※CR-001・CR-002) |
| テスト | **706件合格 / 0件失敗** (Python 3.12) / **707件合格** (Python 3.11)。※CR-003 改修後 |
| 静的検査 | ruff check / ruff format / mypy strict すべてエラー0件 |
| ライセンス | MIT © 2026 HONDOH Atsushi。実行時依存もすべて MIT と両立するライセンス (※CR-003 で PDF ライブラリを pdfminer.six (MIT) に差し替え。受け入れテスト A007 で検査) |

---

## 1. このアプリが解決すること

読み手は人間ではなく**チャンク分割器と埋め込みモデル**である。視覚的忠実性を捨て、**構造的忠実性**を追う。

他ツールと異なる2点:

1. **オートシェープ内テキストを取りこぼさない** — 日本のビジネス文書は要点や注意事項が図形の中に書かれていることが多い。OCR は使わず OOXML 上のテキストを回収する。
2. **Excel の二面性に判別なしで両対応する** — 「表計算」か「方眼紙」かを判別せず、両方の Markdown を常に出力する。

**PDF** (※CR-001・CR-002): タグ付き PDF は論理構造から見出し・箇条書き・表に、タグなし PDF は段落の並びに変換する。タグなし PDF のヘッダー・フッターを除き、段組みを段ごとに読む。

---

## 2. 最初に読むもの

| 目的 | ファイル |
| --- | --- |
| **使い方を知りたい** | [app/README.md](./app/README.md) |
| **導入・起動の手順** | [docs/P302-deliver.md](./docs/P302-deliver.md) |
| **何を作ったのか (要求)** | [docs/P001-requirement.md](./docs/P001-requirement.md) |
| **なぜその設計にしたか** | [docs/ADR.md](./docs/ADR.md) |
| **改修する前に読むもの** | [docs/ArchitectureHandbook.md](./docs/ArchitectureHandbook.md) |
| **ソースの構成** | [app/INDEX.md](./app/INDEX.md) |

---

## 3. ソースツリー

- [app/INDEX.md](./app/INDEX.md) — アプリケーション本体の目次 (`src/` 42ファイル / `tests/` テストモジュール39件)

---

## 4. 設計文書 (docs/)

### 要求・設計

| ファイル | 内容 |
| --- | --- |
| [P001-requirement.md](./docs/P001-requirement.md) | **システム要件定義書** (版1.1)。機能要件84件・非機能要件19件 |
| [P002-frontend-spec.md](./docs/P002-frontend-spec.md) | **ユーザインタフェース設計書** (版2.0)。CLI 全7画面・出力Markdownの体裁・公開API・中間表現 |
| [P003-backend-spec.md](./docs/P003-backend-spec.md) | **システム詳細設計書**。**§1 に実測にもとづくスパイク結果**・OOXML走査アルゴリズム・セキュリティ実装 |
| [P004-traceability-matrix.md](./docs/P004-traceability-matrix.md) | 要求トレーサビリティマトリクス。**103要求すべてが OK** |

### 計画

| ファイル | 内容 |
| --- | --- |
| [P005-impl-plan.md](./docs/P005-impl-plan.md) | 実装計画書。5スプリントへの分割と依存関係 |
| [P006-test-plan.md](./docs/P006-test-plan.md) | テスト計画書。4レベルの目的・重点領域・テストデータのライフサイクル |

### 実装・テストの指示書

| ファイル | 内容 |
| --- | --- |
| [P007-impl-direction.md](./docs/P007-impl-direction.md) | プログラム実装定義の目次 (**全8スプリント完了**。U006・U007 は ※CR-001・CR-002、U008 は ※CR-003) |
| [P008-test-direction.md](./docs/P008-test-direction.md) | 結合テスト定義の目次 (T001〜T006。**全件完了**。T006 は PDF) |
| [P009-acceptance-direction.md](./docs/P009-acceptance-direction.md) | 受け入れ結合テスト定義の目次 (A001〜A007。**全件完了**。A006 は PDF、A007 は依存ライセンス) |

### レビュー・修正の記録

| ファイル | 内容 |
| --- | --- |
| [P010-design-review.md](./docs/P010-design-review.md) | 設計書横断レビュー。第1パスで4件の矛盾を検出→是正→第2パスで0件 |
| [P011-impact-analysis.md](./docs/P011-impact-analysis.md) | 矛盾点の影響分析 |
| [P201-review-report.md](./docs/P201-review-report.md) | 実装横断レビュー。2件の欠陥を検出 |
| [P202-fix-plan.md](./docs/P202-fix-plan.md) | 修正計画 (F001〜F006。**全件修正済み**。F004〜F006 は ※CR 改修時のテストコードの修正) |
| [P202-fix-resolved.md](./docs/P202-fix-plan/P202-fix-resolved.md) | 解決済みの修正障害一覧 (F001〜F003 の症状・原因・修正・検証) |
| [P202-fix-unresolved.md](./docs/P202-fix-plan/P202-fix-unresolved.md) | 未解決の修正障害一覧。**未解決は0件** |
| [P204-impact-analysis.md](./docs/P204-impact-analysis.md) | 修正の影響分析。他機能を壊していないことの確認 |

### 恒久文書

| ファイル | 内容 |
| --- | --- |
| [ADR.md](./docs/ADR.md) | **アーキテクチャ決定記録** (ADR-001〜011・013〜015。013〜015 は PDF)。判断とその理由 |
| [ADR_master.md](./docs/ADR_master.md) | 廃止した ADR の退避先 (ADR-012: PyMuPDF の採用。※CR-003 で廃止) |
| [ArchitectureHandbook.md](./docs/ArchitectureHandbook.md) | **技術ハンドブック**。§4 の落とし穴と §9 の既知の制約は改修前に必読 |
| [P101-impl-context.md](./docs/P101-impl-context.md) | 実装担当向けの文脈要約 |

### 納品

| ファイル | 内容 |
| --- | --- |
| [P302-deliver.md](./docs/P302-deliver.md) | **納品物まとめ・配布手順** |

### 変更要求 (Refactor) ※CR-001・CR-002

| ファイル | 内容 |
| --- | --- |
| [CR.md](./docs/CR.md) | **CR の状態の台帳** (CR-001〜CR-003) |
| [P901-cr-direction/CR-003.md](./docs/P901-cr-direction/CR-003.md) | 変更要求: PDF 読み取りライブラリを MIT 互換 (pdfminer.six) に差し替える |
| [P903-cr-records/CR-003.md](./docs/P903-cr-records/CR-003.md) | 対処記録 (CR-003) |
| [P901-cr-direction/CR-001.md](./docs/P901-cr-direction/CR-001.md) | 変更要求: PDF 入力の追加 (論理構造があれば章立て・箇条書き) |
| [P901-cr-direction/CR-002.md](./docs/P901-cr-direction/CR-002.md) | 変更要求: PDF のヘッダー・フッター除去と段組みの読み順補正 |
| [P903-cr-records/CR-001.md](./docs/P903-cr-records/CR-001.md) / [CR-002.md](./docs/P903-cr-records/CR-002.md) | 対処記録 (スコープ決定・変更内容・反映確認・ADR 更新確認) |
| [P001-requirement_20261014_CR-001.md](./docs/P001-requirement_20261014_CR-001.md) / [_CR-002](./docs/P001-requirement_20261014_CR-002.md) | P902 で退避した要件定義書の原本 |
| [research/pdf-library-alternatives.md](./docs/research/pdf-library-alternatives.md) | **PDF ライブラリの代替検討** (Docling・PDF Inspector・pdfminer.six。MIT を保つため) |

### テスト記録 (docs/test-records/)

| ファイル | 内容 |
| --- | --- |
| [20260824-0815-test-record.md](./docs/test-records/20260824-0815-test-record.md) | P103 結合テスト実行記録 (446合格 / 2失敗) |
| [20260824-0850-test-record.md](./docs/test-records/20260824-0850-test-record.md) | **P205 再実行記録 (539合格 / 0失敗)**。性能・カバレッジの実測値を含む |
| [20260824-0855-test-record.md](./docs/test-records/20260824-0855-test-record.md) | **P302 納品前最終確認記録**。wheel のクリーン環境での動作確認、Python 3.13/3.14 の2版での全件実行、E-004・画像抽出・外部通信なしの追試 |
| [20261014-0225-test-record.md](./docs/test-records/20261014-0225-test-record.md) | ※CR: P103 結合テスト実行記録 (T006 で1件失敗。テスト指示の食い違い) |
| [20261014-0227-test-record.md](./docs/test-records/20261014-0227-test-record.md) | ※CR: P201 第1回 (失敗4件。いずれもテストコード側) |
| [20261014-0230-test-record.md](./docs/test-records/20261014-0230-test-record.md) | **※CR: P205 再実施記録 (692合格 / 0失敗)**。PDF の性能の計測を含む |
| [20261014-0233-test-record.md](./docs/test-records/20261014-0233-test-record.md) | ※CR-001・002: P302 納品前最終確認。wheel・Docker の動作確認、Python 3.11 での全件実行、開発時依存の是正 |
| [20261014-0745-test-record.md](./docs/test-records/20261014-0745-test-record.md) | ※CR-003: P103 結合テスト (79件合格) |
| [20261014-0747-test-record.md](./docs/test-records/20261014-0747-test-record.md) | **※CR-003: P201 (706 / 707件合格)**。依存ライセンス (A007)・PDF の性能 (pdfminer.six) |
| [20261014-0752-test-record.md](./docs/test-records/20261014-0752-test-record.md) | **※CR-003: P302 納品前最終確認**。wheel・Docker (203 MB・MIT)・差し替え前後の出力の比較 (A/B) |

---

## 5. 配布資産

**導入・実行の手順は [docs/P302-deliver.md](./docs/P302-deliver.md) 7章にある。**

| 資産 | 場所 | 検証状況 |
| --- | --- | --- |
| **配布用 wheel** | `app/dist/office2ragknowledge-1.1.0-py3-none-any.whl` | **検証済み** — クリーンな venv に導入して動作を確認 (※CR-003: pdfminer.six 版に再ビルド。旧版は `app/dist/archive-20260824/`・`archive-20261014-pymupdf/`) |
| sdist | `app/dist/office2ragknowledge-1.1.0.tar.gz` | ビルド成功を確認 |
| Python パッケージ定義 | [app/pyproject.toml](./app/pyproject.toml) (依存7件 (※CR-003 で pdfminer.six)・外部バイナリ不要) | 検証済み |
| CLI コマンド | `office2rag` (導入後に利用可能。`convert` / `inspect`) | 検証済み |
| Dockerfile | [deploy/Dockerfile](./deploy/Dockerfile) | **検証済み** (※CR-003 改修時に再ビルド。203 MB・ラベル `licenses` = `MIT`) |
| docker compose | [deploy/compose.yml](./deploy/compose.yml) | **検証済み** (※CR 改修時に `docker compose run` で変換) |
| 環境変数の例 | [deploy/.env.example](./deploy/.env.example) | — |
| ビルド履歴 | [BUILD_HISTORY.md](./BUILD_HISTORY.md) | 実ビルドにもとづく |

`docker compose up` では使わない。本アプリは常駐サービスではなく、`docker compose run --rm convert ...` で都度実行する CLI である。

---

## 6. 開発の進め方

本リポジトリは `.claude/skills/spec-driven-dev` の仕様駆動開発ワークフローに沿って構築されている。

* 改修は **CR (変更要求)** として `docs/P901-cr-direction/` に起票し、`docs/CR.md` の台帳で状態を追う。
* 起票済みの CR: **CR-001・CR-002** (PDF 入力)、**CR-003** (PDF ライブラリの MIT 化)。状態は [docs/CR.md](./docs/CR.md) を参照。
* 実装に着手する前に [ArchitectureHandbook.md](./docs/ArchitectureHandbook.md) §4 (落とし穴) と [ADR.md](./docs/ADR.md) を読むこと。

---

## 7. 人間が確認すべき箇所 (★FIXME★)

自動生成の過程で、Agent が想定で補った箇所には `★FIXME★` を付けている。**設計判断として意識的に選んだ割り切りには `★ACCEPTED★` を付けており、こちらは確認不要である。**

| 文書 | ★FIXME★ の件数 | 主な内容 |
| --- | --- | --- |
| P001 | 11 | 性能の目標値 (実測で大幅に下回ることを確認済み)、想定利用規模、Excel 出力ファイル名の命名、**※CR-001: PDF ライブラリ PyMuPDF のライセンス (§8.3)** |
| P003 | 13 | ADR番号の暫定参照 (P021 で解消済み)、通貨書式の網羅性、SmartArt の階層復元、**※CR-001: PyMuPDF のライセンス (§14 指摘6)** |
| P002 | 2 | 図形プリセットの分類の網羅性 |
| P006 | 2 | 固定フィクスチャの作成方針 (実際にはコード生成で賄えた) |
| P010 / P201 | 6 | Python 3.11 での実行時検証が未実施 (※CR 改修時に WSL2 で解消済み。記述は履歴として残る) |
| P302 | 4 | 版数の扱いの履歴 (2026-10-15 に 1.1.0 へ上げて解消)、ほか |

### 出荷前に対応が要る事項 (2026-10-15)

**なし** (リリース判定 OK)。画像の書き出しに自動テストが無い件は、本ツールの目的 (RAG 向けのテキスト化) に照らして主目的ではないため、依頼者の判断で受容した (★ACCEPTED★。[ArchitectureHandbook.md](./docs/ArchitectureHandbook.md) §9-20)。実際の業務 PDF と Windows での確認は、出荷を妨げない申し送りとして [docs/P302-deliver.md](./docs/P302-deliver.md) 10.2章にある。

アプリケーション一式は 2026-10-15 にブランチ `feature/pdf-input-v1.1.0` へコミットした。
