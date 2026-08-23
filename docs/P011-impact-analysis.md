# P011 影響分析結果 — Office2RAGKnowledge

| 項目 | 内容 |
| --- | --- |
| 版 | 1.0 |
| 作成日 | 2026-08-24 |
| インプット | `docs/P010-design-review.md` (第1パスで検出した矛盾点 No.1〜No.4) |

---

## 1. 分析の目的

`docs/P010-design-review.md` §3 が列挙した4件の矛盾点について、**修正が波及する箇所をすべて洗い出す**。P012 はこの分析にもとづいて修正を行う。

---

## 2. 矛盾点 No.1 — P003 のモジュールツリーに4モジュールが欠落

### 2.1 関係箇所

| # | 文書 | 箇所 | 関係の内容 | 修正要否 |
| --- | --- | --- | --- | --- |
| 1-a | `docs/P003-backend-spec.md` | §2.2 モジュール構成 | **欠落の当事者**。4行を追加する | **要** |
| 1-b | `docs/P003-backend-spec.md` | §6.6 グラフの扱い | `charts.py` の実装先を前提とする記述 | 不要 (ツリー側の追加で解消) |
| 1-c | `docs/P003-backend-spec.md` | §9.4 レンダラ間の共通化 | `ExcelRendererBase` の実装先を前提とする記述 | 不要 (同上) |
| 1-d | `docs/P003-backend-spec.md` | §12A ログ設計 | `logging_setup.py` の実装先を前提とする記述 | 不要 (同上) |
| 1-e | `docs/P003-backend-spec.md` | §2.3 依存の方向 | 追加するモジュールが依存規則に反しないかの確認が必要 | **確認のみ** |
| 1-f | `docs/P007-impl-direction/U003-shape-text.md` | U003-T2 | `ooxml/charts.py` を対象ファイルに挙げている | 不要 (既に正しい) |
| 1-g | `docs/P007-impl-direction/U004-word-powerpoint.md` | U004-T4 | `ooxml/images.py` を対象ファイルに挙げている | 不要 (既に正しい) |
| 1-h | `docs/P007-impl-direction/U005-api-cli.md` | U005-T3 | `logging_setup.py` を対象ファイルに挙げている | 不要 (既に正しい) |
| 1-i | `docs/P007-impl-direction/U002-excel-core.md` | U002-T3 | `render/excel_base.py` を対象ファイルに挙げている | 不要 (既に正しい) |
| 1-j | `docs/P005-impl-plan.md` | §5 スプリントの規模 | 「新規モジュール数」の見積りに影響しうる | **確認のみ** |

### 2.2 依存方向の確認 (1-e)

追加する4モジュールが、P003 §2.3 の一方向依存 (`models/` は他に依存しない、`render/` は `models/` のみ、`parsers/` は `render/` を知らない) に反しないかを確認した。

| モジュール | 依存先 | 判定 |
| --- | --- | --- |
| `ooxml/charts.py` | `ooxml/zip_reader.py`, `ooxml/xml_utils.py`, `models/` | **問題なし** (`ooxml/` 層内および `models/` への依存のみ) |
| `ooxml/images.py` | 同上 | **問題なし** |
| `render/excel_base.py` | `models/`, `render/escape.py`, `render/shapes.py` | **問題なし** (`render/` は `models/` のみに依存する規則を満たす) |
| `logging_setup.py` | 標準ライブラリのみ | **問題なし** (最上位に置き、他モジュールから独立させる) |

### 2.3 規模見積りへの影響 (1-j)

P005 §5 の「新規モジュール数」は U001=10 / U002=5 / U003=4 / U004=3 / U005=8 としている。追加した4モジュールは、いずれも既に P007 の各タスクの対象ファイルに含まれており、**P005 の見積りは既にこれらを織り込んでいる**。したがって P005 の修正は不要である。

### 2.4 結論

**修正対象は `docs/P003-backend-spec.md` §2.2 のみ** (4行の追加)。他の文書は既に正しく、修正不要。

---

## 3. 矛盾点 No.2 — `Sheet` に `shape_count` フィールドが無い

### 3.1 関係箇所

| # | 文書 | 箇所 | 関係の内容 | 修正要否 |
| --- | --- | --- | --- | --- |
| 2-a | `docs/P002-frontend-spec.md` | §7.3.3 `Sheet` の型定義 | **欠落の当事者**。フィールドを追加する | **要** |
| 2-b | `docs/P002-frontend-spec.md` | §7.4 不変条件 INV-05 | 「テキストを持たない図形はブロック化しない」— この不変条件が総数を失わせる原因 | 不要 (INV-05 自体は正しい) |
| 2-c | `docs/P002-frontend-spec.md` | §3.5 SCR-05 の表示項目 | 「図形の総数と、うちテキストを持つ図形の数」を表示すると定める | 不要 (要求どおり) |
| 2-d | `docs/P002-frontend-spec.md` | §6.4 `DocumentInfo` | `shape_count` / `shape_with_text_count` を持つ (集計先) | 不要 (既に正しい) |
| 2-e | `docs/P003-backend-spec.md` | §8.3 `inspect_file` の項目表 | 「抽出器が別途カウンタを返す」と定める (問題の指摘元) | 不要 |
| 2-f | `docs/P007-impl-direction/U001-project-foundation.md` | U001-T2 の `models/sheet.py` の説明 | `Sheet` のフィールド一覧を列挙している | **要** (追加したフィールドを反映) |
| 2-g | `docs/P007-impl-direction/U003-shape-text.md` | U003-T4 | `shape_count` の設定を指示している | **要** (No.3 と併せて修正) |
| 2-h | `docs/P007-impl-direction/U005-api-cli.md` | U005-T2 の `inspect_file` | `shape_count` を集計すると指示している | 不要 (既に正しい) |
| 2-i | `docs/P004-traceability-matrix.md` | REQ-F-091 の行 | 対応箇所として P002 §3.5 / P003 §8.3 を挙げている | 不要 (対応関係は変わらない) |

### 3.2 他形式 (Word / PowerPoint) への影響

`Sheet` は Excel 専用のブロックである。Word / PowerPoint の図形の総数は、`Document` レベルで別途集計する必要がある。

**この点は矛盾点 No.2 の範囲外か**を検討した。P003 §8.3 は「抽出器が別途カウンタを返す」と形式を限定せずに述べており、`ShapeTextExtractor.extract` が総数を返す設計 (P007 U003-T1 の戻り値 `tuple[list[ShapeText], int]`) は3形式共通である。**Word / PowerPoint では `Document` を組み立てるパーサが総数を保持すればよく、新たなフィールドは不要**である (パーサがローカル変数で集計し `DocumentInfo` に渡す)。

`Sheet` にフィールドが必要なのは、**Excel だけがシート単位で図形を保持する構造だから**である。したがって No.2 の修正は `Sheet` のみで足りる。

### 3.3 結論

**修正対象は `docs/P002-frontend-spec.md` §7.3.3** (フィールド追加) と、**`docs/P007-impl-direction/U001-project-foundation.md` U001-T2** (フィールド一覧への反映)。

---

## 4. 矛盾点 No.3 — P007 が Executor に設計書の修正を指示している

### 4.1 関係箇所

| # | 文書 | 箇所 | 関係の内容 | 修正要否 |
| --- | --- | --- | --- | --- |
| 3-a | `docs/P007-impl-direction/U003-shape-text.md` | U003-T4 【実装内容】 | **当事者**。「P002 §7.3.3 に追記すること」の指示 | **要** (削除) |
| 3-b | `docs/P007-impl-direction/U003-shape-text.md` | U003-T4 【完了条件】 | 「P002 に追記していること」を完了条件にしている | **要** (削除) |
| 3-c | `docs/P007-impl-direction.md` | §5 全スプリント共通の実装規約 | Executor が守るべき規約の一覧。設計書を編集しない旨が明記されていない | **確認のみ** |

### 4.2 3-c の検討

P007 目次 §5 の共通規約に「設計書を編集しない」を追加すべきかを検討した。

**追加しない。** 理由は次の2点である。

1. `TEMPLATE-P007-impl-direction.md` の「重要」節に既に「**各タスクの範囲外のファイルは編集しないでください**」があり、`docs/` 配下は各タスクの【作成・編集対象ファイル】に含まれないため、既存の規約で禁止されている。
2. 規約を増やすほど Executor が一度に把握すべき事項が増える。既存の規約で足りる場合は増やさない (`SKILL-P007` の「Executor が把握しきれない量にならないよう」の趣旨)。

**No.2 を先に是正すれば、この指示自体が不要になる**ため、3-a・3-b の削除で解消する。

### 4.3 結論

**修正対象は `docs/P007-impl-direction/U003-shape-text.md` の U003-T4 のみ** (2箇所)。

---

## 5. 矛盾点 No.4 — エラーコードの件数の記述が曖昧

### 5.1 関係箇所

| # | 文書 | 箇所 | 関係の内容 | 修正要否 |
| --- | --- | --- | --- | --- |
| 4-a | `docs/P007-impl-direction/U001-project-foundation.md` | U001-T3 【Unit Test内容】ケース5 | **当事者**。19件と18件が同一文中にある | **要** |
| 4-b | `docs/P002-frontend-spec.md` | §9.1 エラーコード表 | 実際に18件 (E-009 が欠番) | 不要 (表自体は正しい) |
| 4-c | `docs/P003-backend-spec.md` | §8 例外階層とエラーコードの対応 | 例外クラス7種と対応コードを示す | 不要 |
| 4-d | `docs/P007-impl-direction/U001-project-foundation.md` | U001-T3 【実装内容】 | 「E-001〜E-019 をすべて登録する」と書いている | **確認のみ** |

### 5.2 E-009 が欠番である理由の確認

P002 §9.1 の表を確認したところ、E-001〜E-008 (入出力・形式・設定に関するエラー) の後、E-010 から引数・検証エラーが始まっている。**E-009 は意図的な区切りとして空けられている**と解釈できる (E-001〜E-008 が「ファイル・環境に起因するエラー」、E-010 以降が「利用者の指定に起因するエラー」という区分)。

**欠番を埋める修正は行わない。** 番号を詰めると、既に P003・P007・P008・P009 の多数の箇所が参照している E-010 以降のコードがすべてずれ、影響が大きい。欠番であること自体は問題ではない。

### 5.3 4-d の検討

【実装内容】の「E-001〜E-019 をすべて登録する」は、範囲の表現としては正しい (E-009 が存在しないだけ)。**誤解を招かないよう「P002 §9.1 の表に存在する全コードを登録する」と読み替えられる**が、修正は【Unit Test内容】側の一本化で足りる。念のため実装内容側にも「表に存在するもののみ」を含意する記述があることを確認した。

### 5.4 結論

**修正対象は `docs/P007-impl-direction/U001-project-foundation.md` U001-T3 のケース5のみ**。

---

## 6. 修正対象の総括 (P012 への指示)

| # | 文書 | 箇所 | 修正内容 | 由来する矛盾点 |
| --- | --- | --- | --- | --- |
| 1 | `docs/P003-backend-spec.md` | §2.2 | `logging_setup.py` / `ooxml/charts.py` / `ooxml/images.py` / `render/excel_base.py` の4行を追加 | No.1 |
| 2 | `docs/P002-frontend-spec.md` | §7.3.3 | `Sheet` に `shape_count: int` を追加し、追加理由と対応要求を明記 | No.2 |
| 3 | `docs/P007-impl-direction/U001-project-foundation.md` | U001-T2 | `models/sheet.py` の `Sheet` フィールド一覧に `shape_count` を追加 | No.2 |
| 4 | `docs/P007-impl-direction/U003-shape-text.md` | U003-T4 【実装内容】 | 「P002 に追記すること」を削除し、「P002 で定義済みのフィールドを埋める」に改める | No.2, No.3 |
| 5 | `docs/P007-impl-direction/U003-shape-text.md` | U003-T4 【完了条件】 | 「P002 に追記していること」を削除 | No.3 |
| 6 | `docs/P007-impl-direction/U001-project-foundation.md` | U001-T3 ケース5 | 期待件数を18件に一本化し、E-009 が欠番であることを明記 | No.4 |

**修正しないことを確認した箇所**: P005 (規模見積り)、P004 (トレーサビリティ)、P006 (テスト計画)、P008・P009 (テスト指示)、P002 §9.1 のコード体系、P007 目次 §5 の共通規約。

---

## 7. 修正後の再確認事項 (P010 第2パスで確認すべきこと)

| # | 確認事項 |
| --- | --- |
| 1 | P003 §2.2 のモジュールツリーと、P007 の全タスクの【作成・編集対象ファイル】が過不足なく一致すること |
| 2 | P002 §7.3.3 の `Sheet` の全フィールドが、P007 U001-T2 の実装指示と一致すること |
| 3 | P007 のどのタスクにも、`docs/` 配下のファイルを編集する指示が残っていないこと |
| 4 | U001-T3 のケース5の期待件数が一意であること |
| 5 | 上記の修正により、新たな矛盾が生じていないこと (特に `shape_count` の追加が INV-05 と衝突しないこと) |
