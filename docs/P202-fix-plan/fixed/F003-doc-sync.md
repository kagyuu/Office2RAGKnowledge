# F003 — 設計書と実装の乖離の是正

| 項目 | 内容 |
| --- | --- |
| 由来 | `docs/P201-review-report.md` §7 申し送り3 |
| 対象 | `docs/P002-frontend-spec.md` §7.3.1 (データモデル) |
| 重大度 | 低 (動作に影響しない) |

## 【症状】

実装時に `Document` へ `images: tuple[ExtractedImage, ...]` フィールドを追加したが、**`docs/P002-frontend-spec.md` §7.3.1 の型定義表に記載がない**。設計書と実装が乖離している。

## 【なぜ追加が必要だったか】

P002 §6.4 は `ConversionResult.images` に抽出した画像バイナリを持たせると定めていたが、**パーサが収集した画像を `ConversionResult` まで運ぶ経路が中間表現に存在しなかった**。

* `ImageCollector` はパーサの内部で画像を収集する
* `convert_file` は `Document` を受け取って `ConversionResult` を組み立てる
* `Document` に画像を載せる場所が無いため、収集した画像が捨てられていた

`Document` に `images` を追加することで、パーサ → 中間表現 → 結果オブジェクトの経路が繋がる。**Excel の二重出力でも中間表現は1つであるため、画像が重複しない** (REQ-F-069) という利点もある。

## 【併せて行った構造変更】

`ExtractedImage` を `models/result.py` から `models/media.py` へ移した。`models/document.py` と `models/result.py` の双方から参照されるため、そのままでは循環 import になるためである。

## 【修正内容】

### 1. `docs/P002-frontend-spec.md` §7.3.1 の `Document` の表に行を追加

```markdown
| `images` | `tuple[ExtractedImage, ...]` | ○ | 抽出した画像バイナリ。`images=EXTRACT` のときのみ非空。パーサが収集し `ConversionResult.images` へそのまま渡る。**Excel の二重出力でも中間表現は1つであるため重複しない** (REQ-F-069)。※P201 の申し送り3にもとづき追加 |
```

### 2. `docs/P002-frontend-spec.md` §7.2 の ER 図に反映

`DOCUMENT ||--o{ EXTRACTED_IMAGE : holds` を追加する。

### 3. `docs/P003-backend-spec.md` §2.2 のモジュールツリーに `models/media.py` を追加

### 4. `docs/ArchitectureHandbook.md` §3 の中間表現の表に `images` を追記

## 【実装してはいけないこと】

* **アプリケーションコードの変更。** 本項目は設計書の追随のみである。
* `ExtractedImage` を `result.py` に戻すこと (循環 import が再発する)。

## 【完了条件】

* 上記4文書が更新されている。
* `docs/P002-frontend-spec.md` の `Document` の型定義が、実装の `models/document.py` と一致している。
* テストの結果に変化がない (設計書のみの変更であるため)。
