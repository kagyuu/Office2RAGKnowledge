# app/ INDEX

Office2RAGKnowledge のソースツリーの目次。**主に後続の Executor・Reviewer Loop が、ソースコードを全読みせずに構成を把握するために参照する。**

| 項目 | 内容 |
| --- | --- |
| 更新 | 2026-10-14 (※CR-003 の P104 により PDF ライブラリの差し替えを反映) |
| 実装ファイル数 | `src/` 51ファイル / `tests/` 47テストファイル (※CR-003: `pdf/content.py`・`test_pdf_content.py` を削除し、`pdf/drawings.py`・`test_pdf_drawings.py` を追加) |
| テスト | 単体 518件・結合 79件 (すべて合格)。`docs/test-records/20261014-0745-test-record.md` 参照 |

## 全体構成

- `pyproject.toml` — ビルド構成・依存7件 (※CR-003 で PyMuPDF を pdfminer.six (MIT) に差し替え)・ruff/mypy/pytest の設定
- `README.md` — アプリの概要と使い方 (配布時の説明書)
- `.gitignore` — `.venv/` 等の除外
- `src/office2ragknowledge/` — パッケージ本体
- `tests/` — テストコード

## src/office2ragknowledge/

- `__init__.py` — 公開API の再輸出。`__all__` (31シンボル)・`__version__`・`NullHandler` の設定
- `py.typed` — 型情報を同梱することの標識 (REQ-F-103)
- `errors.py` — 例外階層7種と `ERROR_CATALOG` (E-001〜E-019 の18コード)
- `config.py` — `load_config` (API-07)・設定値の検証関数 (CLI 層と共有)
- `detect.py` — `detect_format` (API-05)・拡張子表・OLE シグネチャ判定
- `convert.py` — `convert_file` (API-01) / `convert_bytes` (API-02)。**時刻取得はここ1箇所のみ**
- `batch.py` — `convert_batch` (API-03)・`scan_inputs`・`_worker_convert` (spawn 対応のトップレベル関数)
- `inspection.py` — `inspect_file` (API-04)。変換と同じパーサを使う
- `writer.py` — `write_result` (API-06)。**出力ごとの個別 on_exists 判定・原子的置換**
- `logging_setup.py` — ロガー構成 (text/json)・レベル対応。ルートロガーを触らない

### src/office2ragknowledge/models/

形式非依存の中間表現。**他のどの層にも依存しない**。

- `options.py` — `ConvertOptions` / `ExcelOptions` / `BatchOptions` / `LogOptions` / `Config` と列挙型6種
- `inline.py` — `InlineRun` / `ListItem` / `TableRow` / `TableCell` / `ShapeParagraph` / `make_run`
- `media.py` — `ExtractedImage` (`document.py` と `result.py` の双方から参照。循環 import 回避のため独立)
- `document.py` — `Document` / `DocumentMeta` / `Block` の各バリアント9種
- `sheet.py` — `Sheet` / `SheetRow` / `Cell` / `TableRegion` / `MergedRange` / `col_to_letter` (**Excel 専用**)
- `result.py` — `ConversionResult` / `MarkdownOutput` / `BatchResult` / `DocumentInfo` / `WrittenFiles`

### src/office2ragknowledge/ooxml/

OOXML を安全に読むための基盤と、3形式で共有する抽出器。

- `zip_reader.py` — `SafeZipReader`。ZIP爆弾・パストラバーサル検査 (REQ-NF-006/008)
- `xml_utils.py` — 安全な XML パーサ (XXE 無効化) と名前空間定数18種 (REQ-NF-007)
- `shapes.py` — `ShapeTextExtractor` + 方言3種。**本アプリの中核。`mc:Choice` のみを辿る** (ADR-003)
- `smartart.py` — SmartArt のデータモデル抽出と階層復元 (REQ-F-034)
- `charts.py` — グラフのタイトル・系列名・カテゴリ名の抽出 (REQ-F-047)
- `images.py` — `ImageCollector`。代替テキストとバイナリの収集 (REQ-F-048/049/069)

### src/office2ragknowledge/pdf/ ※CR-001・CR-002

PDF を安全に読むための基盤。**PDF ライブラリ (※CR-003 で pdfminer.six) を import するのは `backend.py` のみ** (ADR-015)。

- `model.py` — ライブラリ非依存の PDF データ型 `PdfChar` / `PdfPage` / `StructInfo` / `PdfMetadata` / `PdfSource`
- `backend.py` — `open_pdf` (pdfminer.six)。暗号化・破損・展開サイズ・**構造ツリーの走査 (MCID → 経路・`/K` 内の位置)**・マーク付きコンテンツで文字に MCID と Artifact を付ける・図形・メタデータ・権限。ライブラリのログと警告の抑止 (Handbook §4-16〜4-18)
- `drawings.py` — 近接するベクター図形の矩形のまとめ (※CR-003。ライブラリ非依存)
- `safety.py` — Flate ストリームの展開サイズ検査 (REQ-NF-020)。上限はモジュール定数
- `text.py` — 文字 → 行 → 文字列 (日本語の連結規則)
- `structure.py` — 被覆率の判定 (50%)・ページをまたぐ構造木の統合・**画像だけの図の挿入**・**`/K` の順序での並べ直し** (※CR-003)
- `layout.py` — タグなし PDF の行片・図領域・**ヘッダー/フッター除去**・**段組み検出**・段落

### src/office2ragknowledge/parsers/

形式別のパーサ。中間表現を生成する。**`render/` を知らない**。

- `base.py` — `Parser` プロトコル・`read_core_properties`・`parse_iso`
- `word.py` — `WordParser`。**`_run_text` が図形の内側で打ち切る** (本文と図形の二重取得を防ぐ)
- `excel.py` — `ExcelParser`。**openpyxl + lxml のハイブリッド**。`<v>` のテキスト有無でキャッシュ値を判定
- `excel_regions.py` — `detect_regions`。空行・空列による2段階分割 (要求①)
- `excel_shapes.py` — シートと drawing の対応付け・アンカーセル参照の算出 (REQ-F-035)
- `powerpoint.py` — `PowerPointParser`。スライド本体のみ走査 (マスター由来の文言を除外)
- `pdf.py` — `PdfParser` (※CR-001)。構造木の写像 (見出し・リスト・表・図) / タグなしレイアウト → 中間表現。`SafeZipReader` を通らない入口

### src/office2ragknowledge/render/

中間表現から Markdown を生成する。**`models/` のみに依存する**。

- `__init__.py` — `render_document`。**1つの中間表現から1〜2の出力を生成** (要求③)
- `escape.py` — 行頭の構造記号のみをエスケープ (ADR-010)
- `frontmatter.py` — YAML front matter (キー順固定)・`strip_front_matter`
- `shapes.py` — 図形テキストブロックの体裁3種・図形内の表の外出し
- `markdown.py` — `MarkdownRenderer` (Word / PowerPoint 用)。脚注と位置不明図形の末尾移送
- `excel_base.py` — `ExcelRendererBase`。**両モード共通処理 (章見出し・図形ブロック)**
- `excel_table.py` — `ExcelTableRenderer`。**表計算モード。結合セルを複製する**
- `excel_grid.py` — `ExcelGridRenderer`。**方眼紙モード。結合セルを複製しない**

### src/office2ragknowledge/cli/

利用者に接する層。全7画面 (SCR-01〜07)。

- `main.py` — Typer アプリ。`convert` / `inspect`。`if __name__ == "__main__":` で保護
- `options.py` — 全オプションの検証 (V-01〜V-52)。★**設定ファイルの優先順位に既知の欠陥あり** (P103 失敗1)
- `console.py` — 進捗・サマリ・構造表示・エラー表示。Console は遅延解決

## tests/

- `conftest.py` — (未作成。各テストが `tmp_path` で自己完結するため不要だった)
- `helpers/make_office.py` — Office ファイルの生成・ZIP への注入 (drawing / 変更履歴 / キャッシュ値)
- `helpers/make_malicious.py` — 細工ファイル (ZIP爆弾・XXE・パストラバーサル) の生成
- `helpers/make_pdf.py` — PDF のバイト列の直接生成 (タグ付き/タグなし/MCR形式/Form XObject/暗号化/展開爆弾。※CR-001・CR-003)
- `helpers/pdf_samples.py` — 結合・受け入れテストで共有するサンプル PDF (※CR-001・CR-002)
- `helpers/compare.py` — front matter を除いた Markdown 比較 (冪等性検証)
- `unit/` — 単体テスト・518件 (`test_pdf_*.py` 8ファイル。※CR-003 で `test_pdf_content.py` を削除、`test_pdf_drawings.py` を追加)
- `integration/` — 結合テスト・79件 (T001〜T006。T006 = `test_pdf_conversion.py`)
- `acceptance/` — 受け入れ・システムテスト (P201 で実装)
- `fixtures/` — (未使用。すべてコード生成と XML 直接入力で賄えたため)

## 実装時に判明した重要事項

| # | 事項 | 対応箇所 |
| --- | --- | --- |
| 1 | **openpyxl は数式セルに空の `<v>` を書き出す。** 要素の有無で判定すると必ず誤判定する | `parsers/excel.py` の `_read_formula_map` |
| 2 | **Word の図形を包む外側の run を素朴に走査すると、テキストボックスの内容を本文として拾う** (しかも Choice/Fallback で二重になる) | `parsers/word.py` の `_run_text` |
| 3 | **`ShapeTextExtractor.extract` は、渡された要素自身が図形の場合にも対応する必要がある** (PowerPoint は図形単位で呼ぶ) | `ooxml/shapes.py` の `extract` |
| 4 | **Rich の `Console(file=sys.stdout)` は import 時のストリームを掴む。** リダイレクト時に出力が捕捉できない | `cli/console.py` |
| 5 | **`posixpath.basename` は Windows のバックスラッシュを分割しない。** タイトルにフルパスが入る | 3つのパーサ (`Path(filename).stem` に統一) |
| 6 | openpyxl 自身が「Shapes and drawings will be lost」と警告する。lxml 直接走査の必要性の裏付け | — |
| 7 | MuPDF の制約 (MCR 形式・後置の Artifact) は ※CR-003 の差し替えで解消。画像だけの図の挿入は残す | `pdf/structure.py` (Handbook §4-14) |
| 8 | **pdfminer.six は文字を描画順に返す → `/K` の順に並べ直す。`PDFPageAggregator` の `_stack` を上書きしない** (※CR-003) | `pdf/structure.py`・`pdf/backend.py` (Handbook §4-15・§4-18) |

## 参照

| 知りたいこと | 参照先 |
| --- | --- |
| なぜこの構成なのか | `docs/P003-backend-spec.md` §2 |
| 技術的決定の理由 | `docs/ADR.md` (ADR-001〜011) |
| 実装時に踏んではならない落とし穴 | `docs/ArchitectureHandbook.md` §4 |
| テストの実行結果 | `docs/test-records/` |
