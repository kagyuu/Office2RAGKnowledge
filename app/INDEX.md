# app/ INDEX

Office2RAGKnowledge のソースツリーの目次。**主に後続の Executor・Reviewer Loop が、ソースコードを全読みせずに構成を把握するために参照する。**

| 項目 | 内容 |
| --- | --- |
| 更新 | 2026-08-24 (P104 により実装後の実体へ更新) |
| 実装ファイル数 | `src/` 42ファイル / `tests/` 34テストファイル |
| テスト | 448件 (446合格 / 2失敗。`docs/test-records/20260824-0815-test-record.md` 参照) |

## 全体構成

- `pyproject.toml` — ビルド構成・依存6件・ruff/mypy/pytest の設定
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

### src/office2ragknowledge/parsers/

形式別のパーサ。中間表現を生成する。**`render/` を知らない**。

- `base.py` — `Parser` プロトコル・`read_core_properties`・`parse_iso`
- `word.py` — `WordParser`。**`_run_text` が図形の内側で打ち切る** (本文と図形の二重取得を防ぐ)
- `excel.py` — `ExcelParser`。**openpyxl + lxml のハイブリッド**。`<v>` のテキスト有無でキャッシュ値を判定
- `excel_regions.py` — `detect_regions`。空行・空列による2段階分割 (要求①)
- `excel_shapes.py` — シートと drawing の対応付け・アンカーセル参照の算出 (REQ-F-035)
- `powerpoint.py` — `PowerPointParser`。スライド本体のみ走査 (マスター由来の文言を除外)

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
- `helpers/compare.py` — front matter を除いた Markdown 比較 (冪等性検証)
- `unit/` — 単体テスト23ファイル・389件
- `integration/` — 結合テスト4ファイル・59件 (T001〜T004)
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

## 参照

| 知りたいこと | 参照先 |
| --- | --- |
| なぜこの構成なのか | `docs/P003-backend-spec.md` §2 |
| 技術的決定の理由 | `docs/ADR.md` (ADR-001〜011) |
| 実装時に踏んではならない落とし穴 | `docs/ArchitectureHandbook.md` §4 |
| テストの実行結果 | `docs/test-records/` |
