# Office2RAGKnowledge — リポジトリ全体の目次

Office 文書 (Word / Excel / PowerPoint) を、AI の RAG パイプライン向け Markdown に変換するツール。

| 項目 | 内容 |
| --- | --- |
| 状態 | **完成** (全フェーズ P001〜P302 完了) |
| 更新 | 2026-08-24 |
| テスト | **539件合格 / 0件失敗** (`docs/test-records/20260824-0850-test-record.md`) |
| 静的検査 | ruff check / ruff format / mypy strict すべてエラー0件 |
| ライセンス | MIT © 2026 HONDOH Atsushi |

---

## 1. このアプリが解決すること

読み手は人間ではなく**チャンク分割器と埋め込みモデル**である。視覚的忠実性を捨て、**構造的忠実性**を追う。

他ツールと異なる2点:

1. **オートシェープ内テキストを取りこぼさない** — 日本のビジネス文書は要点や注意事項が図形の中に書かれていることが多い。OCR は使わず OOXML 上のテキストを回収する。
2. **Excel の二面性に判別なしで両対応する** — 「表計算」か「方眼紙」かを判別せず、両方の Markdown を常に出力する。

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

- [app/INDEX.md](./app/INDEX.md) — アプリケーション本体の目次 (`src/` 42ファイル / `tests/` 34ファイル)

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
| [P007-impl-direction.md](./docs/P007-impl-direction.md) | プログラム実装定義の目次 (**全5スプリント完了**) |
| [P008-test-direction.md](./docs/P008-test-direction.md) | 結合テスト定義の目次 (T001〜T005。**全件完了**) |
| [P009-acceptance-direction.md](./docs/P009-acceptance-direction.md) | 受け入れ結合テスト定義の目次 (A001〜A005。**全件完了**) |

### レビュー・修正の記録

| ファイル | 内容 |
| --- | --- |
| [P010-design-review.md](./docs/P010-design-review.md) | 設計書横断レビュー。第1パスで4件の矛盾を検出→是正→第2パスで0件 |
| [P011-impact-analysis.md](./docs/P011-impact-analysis.md) | 矛盾点の影響分析 |
| [P201-review-report.md](./docs/P201-review-report.md) | 実装横断レビュー。2件の欠陥を検出 |
| [P202-fix-plan.md](./docs/P202-fix-plan.md) | 修正計画 (F001〜F003。**全件修正済み**) |
| [P204-impact-analysis.md](./docs/P204-impact-analysis.md) | 修正の影響分析。他機能を壊していないことの確認 |

### 恒久文書

| ファイル | 内容 |
| --- | --- |
| [ADR.md](./docs/ADR.md) | **アーキテクチャ決定記録** (ADR-001〜011)。判断とその理由 |
| [ArchitectureHandbook.md](./docs/ArchitectureHandbook.md) | **技術ハンドブック**。§4 の落とし穴と §9 の既知の制約は改修前に必読 |
| [P101-impl-context.md](./docs/P101-impl-context.md) | 実装担当向けの文脈要約 |

### 納品

| ファイル | 内容 |
| --- | --- |
| [P302-deliver.md](./docs/P302-deliver.md) | **納品物まとめ・配布手順** |

### テスト記録 (docs/test-records/)

| ファイル | 内容 |
| --- | --- |
| [20260824-0815-test-record.md](./docs/test-records/20260824-0815-test-record.md) | P103 結合テスト実行記録 (446合格 / 2失敗) |
| [20260824-0850-test-record.md](./docs/test-records/20260824-0850-test-record.md) | **P205 再実行記録 (539合格 / 0失敗)**。性能・カバレッジの実測値を含む |

---

## 5. 配布資産

| 資産 | 場所 |
| --- | --- |
| Python パッケージ | `app/` (`pip install ./app` または `pip install -e ./app`) |
| CLI コマンド | `office2rag` (インストール後に利用可能) |
| Docker / docker compose | `deploy/` ([P302-deliver.md](./docs/P302-deliver.md) 参照) |

---

## 6. 開発の進め方

本リポジトリは `.claude/skills/spec-driven-dev` の仕様駆動開発ワークフローに沿って構築されている。

* 改修は **CR (変更要求)** として `docs/P901-cr-direction/` に起票し、`docs/CR.md` の台帳で状態を追う。
* 現在 CR は起票されていない (`docs/CR.md` は未作成)。
* 実装に着手する前に [ArchitectureHandbook.md](./docs/ArchitectureHandbook.md) §4 (落とし穴) と [ADR.md](./docs/ADR.md) を読むこと。

---

## 7. 人間が確認すべき箇所 (★FIXME★)

自動生成の過程で、Agent が想定で補った箇所には `★FIXME★` を付けている。**設計判断として意識的に選んだ割り切りには `★ACCEPTED★` を付けており、こちらは確認不要である。**

| 文書 | ★FIXME★ の件数 | 主な内容 |
| --- | --- | --- |
| P001 | 10 | 性能の目標値 (実測で大幅に下回ることを確認済み)、想定利用規模、Excel 出力ファイル名の命名 |
| P003 | 11 | ADR番号の暫定参照 (P021 で解消済み)、通貨書式の網羅性、SmartArt の階層復元 |
| P002 | 2 | 図形プリセットの分類の網羅性 |
| P006 | 2 | 固定フィクスチャの作成方針 (実際にはコード生成で賄えた) |
| P010 / P201 | 5 | Python 3.11 での実行時検証が未実施 (本環境に 3.11 が無いため) |

**もっとも重要な未検証事項**: [Python 3.11 での実行時動作](./docs/test-records/20260824-0850-test-record.md#7-結論)。`mypy --python-version 3.11` は通っており、3.12+ 専用の構文は使っていないが、実行時の確認は行えていない。
