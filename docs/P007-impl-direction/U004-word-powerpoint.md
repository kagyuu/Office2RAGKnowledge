あなたはExecutor(実装担当)です。以下は1スプリント分の作業範囲と完了条件を定義したものです。実施後は、そのタスクの完了条件を満たしたことを確認したうえで、Executor Stepの「停止条件」(`SKILL.md` 参照)に該当しない限り、自動的に次のタスクへ進んでください。人間の指示を待って停止しないでください。

# 【スプリントID】U004 — word-powerpoint

## タスク一覧(OKF副目次)

- [x] U004-T1 [Wordパーサ](#u004-t1-wordパーサ) — 見出し・リスト・表・書式・脚注・変更履歴・図形アンカー
- [x] U004-T2 [PowerPointパーサ](#u004-t2-powerpointパーサ) — スライド・プレースホルダ・表・ノート・図形
- [x] U004-T3 [共通レンダラ](#u004-t3-共通レンダラ) — Word/PowerPoint 用の Markdown 生成
- [x] U004-T4 [画像の抽出](#u004-t4-画像の抽出) — 代替テキスト・プレースホルダ・バイナリ収集

---

## U004-T1: Wordパーサ

### 【目的】

* Word 文書を中間表現に変換する (REQ-F-011〜020, 036)。

### 【作成・編集対象ファイル】

* `app/src/office2ragknowledge/parsers/word.py`

### 【参照すべき仕様箇所】

* `docs/P003-backend-spec.md` §6.5 (アンカー解決の表), §8.3 (図形の走査)
* `docs/P002-frontend-spec.md` §5.9 (Word の出力構造と確定事項), §7.3.2 (Block バリアント)
* `docs/P001-requirement.md` REQ-F-011〜020, REQ-F-036

### 【実装内容】

* `class WordParser`。python-docx で開き、`doc.element.body` を走査する。**図形テキストは python-docx の公開 API では取れない** (P003 §1.3 で実測) ため、lxml で本文要素を辿る。
* **本文の走査**: `body` の直接の子を順に処理する。
  * `w:p` (段落): スタイル名から見出しレベルを判定する。
    * スタイル名が `Heading N` / `見出し N` にマッチしたら `Heading(level=min(N+1, 6))` を作る。**+1 するのは、front matter 直後の `#` が文書タイトルで占められるため** (P002 §5.9)。
    * リスト段落 (`w:numPr` を持つ) は `ListItem` として収集し、連続するものを1つの `ListBlock` にまとめる。`w:ilvl` を `level`、`w:numFmt` が `bullet` 以外なら `ordered=True`。
    * それ以外は `Paragraph`。
    * 空段落 (テキストも図形もない) は無視する。
  * `w:tbl` (表): `Table` に変換する。`w:gridSpan` / `w:vMerge` による結合は**値を複製して矩形を保つ** (REQ-F-013)。全行の列数を揃える (INV-01)。
* **run の変換** (REQ-F-014): `w:r` ごとに `InlineRun` を作る。`w:b`→`bold`、`w:i`→`italic`、`w:strike`→`strike`、フォントが等幅 (`w:rFonts` の名前に `Mono`/`Courier`/`Consolas` を含む) → `code`。
* **ハイパーリンク** (REQ-F-015): `w:hyperlink` の `r:id` を `document.xml.rels` で解決し、配下の run に `link_url` を設定する。
* **変更履歴** (REQ-F-018): `w:ins` 配下の run は**採用**し、`w:del` 配下の run は**除外**する。`w:delText` は読まない。
* **脚注** (REQ-F-016): `w:footnoteReference` / `w:endnoteReference` の ID を記録し、`footnotes.xml` / `endnotes.xml` から本文を読んで `Footnote` ブロックを作る。本文中には `[^N]` の参照を `InlineRun` として挿入する。ID が `0` / `1` の区切り用脚注は除外する。
* **ヘッダー・フッター** (REQ-F-017): `options.headers_footers` が真のときのみ、`header*.xml` / `footer*.xml` を読み、文書末尾の `## ヘッダー・フッター` 節として `Paragraph` を追加する。既定は読まない。
* **コメント** (REQ-F-019): `options.comments` が真のときのみ、`comments.xml` を読み、対象段落の直後に `ShapeText(shape_kind="コメント", ...)` として挿入する。既定は読まない。
  * ★FIXME★ コメントを `ShapeText` として表現するのは、専用のブロック型を増やさないための簡略化である。出力体裁は `> **[図形: コメント]**` となり、P002 §5.9 が定めた `> **[コメント: {作成者}]**` と異なる。**P002 §5.9 の体裁に合わせるため、`shape_kind` に `コメント: {作成者}` を入れる**ことで対処する。
* **改ページ・セクション区切り** (REQ-F-020): 水平線を出力しない。`w:br type="page"` と `w:sectPr` は**無視する**。
* **図形テキスト** (REQ-F-036): `options.shapes` が真のとき、各 `w:p` の配下を `ShapeTextExtractor(WORD_DIALECT)` で走査し、得た `ShapeText` を**その段落ブロックの直後**に挿入する。
  * ヘッダー・フッター内の図形は、`options.headers_footers` が偽なら抽出しない。
  * 本文のどの段落にも属さない図形が見つかった場合は `anchor=None` のまま末尾に集め、警告 `アンカー位置を特定できない図形が {N} 件あり、文書末尾にまとめました` を追加する。
  * SmartArt (`dgm:relIds`) とグラフ (`c:chart`) は U003-T2 の関数を呼ぶ。
* **文書タイトル**: `docProps/core.xml` の `dc:title`。空ならファイル名 (拡張子なし)。
* `converted_at` は引数で受け取る (規約11)。

### 【実装してはいけないこと】

* `document.paragraphs` のような python-docx の高レベル API のみで図形を探すこと (取得できない。P003 §1.3)。
* `w:del` 配下のテキストの出力 (REQ-F-018)。
* 改ページの水平線化 (REQ-F-020)。
* Markdown の生成 (U004-T3)。

### 【Unit Test内容】

* **ファイル**: `app/tests/unit/test_word_parser.py`
* **テストデータ**: `tests/helpers/make_office.py` に python-docx で `.docx` を生成する関数を追加する。図形・変更履歴・コメントは python-docx で作れないため、**生成後に `document.xml` に XML を注入する**ヘルパを用意する。
* **ケース**:
  1. 見出し1が `Heading(level=2)` になる (1繰り下げ)。
  2. 見出し5以上が `level=6` に丸められる。
  3. 箇条書きが `ListBlock` になり、`ilvl` が `level` に入る。
  4. 連続する箇条書きが1つの `ListBlock` にまとまる。
  5. 番号付きリストで `ordered=True`。
  6. 表が `Table` になり、全行の列数が揃う (INV-01)。
  7. 結合セル (`gridSpan`) の値が複製される。
  8. 太字・斜体・取り消し線が `InlineRun` のフラグになる。
  9. ハイパーリンクの `link_url` が解決される。
  10. **`w:ins` のテキストが出力に含まれ、`w:del` のテキストが含まれない** (REQ-F-018)。
  11. 脚注が `Footnote` ブロックになり、本文に `[^1]` が入る。
  12. `headers_footers=False` でヘッダーのテキストが `blocks` に現れない。
  13. `headers_footers=True` でヘッダーの節が追加される。
  14. `comments=False` でコメントが現れない。
  15. **図形テキストが、アンカーされた段落の直後のブロックとして挿入される** (REQ-F-036)。
  16. `shapes=False` で図形が抽出されない。
  17. 改ページが水平線として現れない (REQ-F-020)。
  18. 文書タイトルが `docProps` から取られ、無ければファイル名になる。
  19. `converted_at` が引数の値になる。

### 【実行コマンド】

* `pytest tests/unit/test_word_parser.py -v`

### 【完了条件】

* 上記19ケースすべてが合格する。

### 【次タスクに進む前の停止条件】

* 単体テストが3回自己修正しても合格しない場合は停止して報告する。

---

## U004-T2: PowerPointパーサ

### 【目的】

* PowerPoint を中間表現に変換する (REQ-F-041〜047, 037)。

### 【作成・編集対象ファイル】

* `app/src/office2ragknowledge/parsers/powerpoint.py`

### 【参照すべき仕様箇所】

* `docs/P002-frontend-spec.md` §5.10 (PowerPoint の出力構造と確定事項)
* `docs/P003-backend-spec.md` §6.1 (方言表), §6.6 (グラフ)
* `docs/P001-requirement.md` REQ-F-037, REQ-F-041〜047

### 【実装内容】

* `class PowerPointParser`。python-pptx で開く。**グループ図形の再帰は `shape.shapes` で辿れる** (P003 §1.3 検証4) が、`mc:AlternateContent` や SmartArt の扱いのため、図形テキストの抽出は U003 の `ShapeTextExtractor(PPTX_DIALECT)` を用いる。
* **スライドごと**に `SlideBreak(slide_number, slide_title, notes)` を作り、続けて本文ブロックを並べる。
  * `slide_title`: タイトルプレースホルダのテキスト。無ければ `None` (見出しは `## スライド {N}` となる。REQ-F-041)。
  * **非表示スライド** (REQ-F-045): `slide._element.get("show") == "0"` のとき、`options.include_hidden` が偽ならスキップする。
* **本文プレースホルダ** (REQ-F-042): 本文プレースホルダの段落を `ListBlock` に変換する。`paragraph.level` を `ListItem.level` に入れる。
* **表** (REQ-F-043): `shape.has_table` の図形を `Table` に変換する。結合は値を複製する。
* **ノート** (REQ-F-044): `options.notes` が真のとき、`slide.notes_slide.notes_text_frame.text` を `SlideBreak.notes` に `ShapeParagraph` として入れる。空なら空タプル。
* **図形テキスト** (REQ-F-037): **プレースホルダ (タイトル・本文) 以外**の図形を対象とする。`shape.is_placeholder` が真でタイプが `TITLE` / `BODY` / `CENTER_TITLE` / `SUBTITLE` のものは**除外する** (二重出力の防止)。それ以外の図形を `ShapeTextExtractor` で処理する。
* **マスター・レイアウト由来の文言** (REQ-F-046): **スライド本体 (`slide.shapes`) のみを走査し、`slide_layout` / `slide_master` の図形を走査しない。** これにより定型文言が自動的に除外される。
* **SmartArt・グラフ**: U003-T2 の関数を呼ぶ。
* 文書タイトル: `docProps/core.xml` の `dc:title`。無ければファイル名。

### 【実装してはいけないこと】

* スライドマスター・レイアウトの図形の走査 (REQ-F-046)。
* プレースホルダのテキストを図形テキストとしても出力すること (REQ-F-037: 二重出力の禁止)。
* Markdown の生成 (U004-T3)。

### 【Unit Test内容】

* **ファイル**: `app/tests/unit/test_powerpoint_parser.py`
* **ケース**:
  1. スライドごとに `SlideBreak` が作られ、`slide_number` が1起点。
  2. タイトルが `slide_title` に入る。
  3. タイトルプレースホルダが無いスライドで `slide_title=None`。
  4. 本文プレースホルダの箇条書きが `ListBlock` になり、階層が `level` に入る。
  5. 表が `Table` になる。
  6. `notes=True` でノートが `SlideBreak.notes` に入る。
  7. `notes=False` でノートが空。
  8. ノートが空のスライドで `notes` が空タプル。
  9. **プレースホルダ以外の図形が `ShapeText` になる**。
  10. **タイトル・本文プレースホルダが `ShapeText` として二重に出力されない** (REQ-F-037)。
  11. **レイアウト由来の図形が出力に含まれない** (REQ-F-046)。
  12. `include_hidden=False` で非表示スライドがスキップされる。
  13. `include_hidden=True` で非表示スライドが含まれる。
  14. `shapes=False` で図形が抽出されない。

### 【実行コマンド】

* `pytest tests/unit/test_powerpoint_parser.py -v`

### 【完了条件】

* 上記14ケースすべてが合格する。

### 【次タスクに進む前の停止条件】

* 単体テストが3回自己修正しても合格しない場合は停止して報告する。

---

## U004-T3: 共通レンダラ

### 【目的】

* Word / PowerPoint 用の Markdown レンダラを実装し、U002-T5 の `render_document` の `NotImplementedError` を解消する。

### 【作成・編集対象ファイル】

* `app/src/office2ragknowledge/render/markdown.py`
* `app/src/office2ragknowledge/render/__init__.py` (ディスパッチの更新)

### 【参照すべき仕様箇所】

* `docs/P002-frontend-spec.md` §5.9 (Word), §5.10 (PowerPoint), §5.1 (エスケープ), §7.4 INV-04
* `docs/P001-requirement.md` REQ-F-011〜016, REQ-F-041〜044

### 【実装内容】

* `class MarkdownRenderer`。`render(document, options) -> tuple[str, dict, tuple[str,...]]`。
* 文書冒頭に `# {document.title}` を出力する。
* `blocks` を**順に**処理する (INV-04: 並べ替えない)。ただし次の2つのみ末尾へ移送する:
  * `Footnote` → `## 脚注` 節にまとめる (0件なら節ごと出さない)。
  * `anchor is None` かつ Word 由来の `ShapeText` → `## 図形テキスト (位置不明)` 節にまとめる (0件なら出さない)。
* ブロック別の描画:
  * `Heading` → `#` × `level` + テキスト。
  * `Paragraph` → run を連結し `escape_line` を通す。
  * `ListBlock` → `level` × 2スペースのインデント + `- ` または `1. `。
  * `Table` → GFM テーブル。ヘッダ行と区切り行。セルは `escape_cell`。
  * `ShapeText` → U003-T3 の `render_shape_block`。
  * `Image` → `![{alt}]({参照})`。`images=NONE` なら参照は `画像は出力されていません`、`EXTRACT` なら `./{ステム}_assets/{連番}.{拡張子}` (P002 §5.11)。
  * `SlideBreak` → `## スライド {N}: {タイトル}` (タイトルが無ければ `## スライド {N}`)。`notes` があれば、そのスライドの本文の後に `### ノート` 節を出す。
* **run の描画**: `bold`→`**x**`、`italic`→`*x*`、`strike`→`~~x~~`、`code`→`` `x` ``、`link_url`→`[x](url)`。複数フラグは入れ子にする。**テキストは `escape_line` の対象だが、装飾記号自体はエスケープしない**。
* 最終段で空行の正規化を行う。
* `stats`: Word は `paragraphs` `headings` `tables` `shapes_with_text` `images`、PowerPoint は `slides` `tables` `shapes_with_text` `images`。
* `render/__init__.py` の `render_document` で、`DOCX` / `PPTX` のときこのレンダラを呼ぶ (サフィックス `.md`、`mode=None`)。

### 【実装してはいけないこと】

* `blocks` の並べ替え (脚注と位置不明図形の末尾移送を除く。INV-04)。
* Excel の `Sheet` ブロックの処理 (専用レンダラの担当)。

### 【Unit Test内容】

* **ファイル**: `app/tests/unit/test_markdown_render.py`
* **ケース**:
  1. `Heading(level=2)` が `## ` になる。
  2. `ListBlock` の階層が2スペースのインデントで表現される。
  3. 番号付きリストが `1. ` になる。
  4. `Table` が GFM テーブルになり、区切り行が入る。
  5. 太字・斜体・取り消し線・コードが対応する記法になる。
  6. リンクが `[表示](URL)` になる。
  7. **`Footnote` が `## 脚注` 節として末尾に移送される** (INV-04)。
  8. 脚注が0件なら `## 脚注` 節が出ない。
  9. **`anchor=None` の `ShapeText` が `## 図形テキスト (位置不明)` 節に移送される**。
  10. `anchor` を持つ `ShapeText` は元の位置に残る。
  11. `SlideBreak` が `## スライド 1: タイトル` になる。
  12. タイトルが `None` のとき `## スライド 1` になる。
  13. ノートが `### ノート` 節として出る。
  14. `images=NONE` で画像がプレースホルダになる。
  15. `images=EXTRACT` で相対パス参照になる。
  16. `render_document` が `DOCX` で1件の `MarkdownOutput` を返し、サフィックスが `.md`、`mode=None`。
  17. `render_document` が `PPTX` で同様。
  18. 文書冒頭に `# {タイトル}` が出る。
  19. 連続する空行が出力に現れない。

### 【実行コマンド】

* `pytest tests/unit/test_markdown_render.py -v`

### 【完了条件】

* 上記19ケースすべてが合格する。
* U002-T5 のテストで `DOCX`/`PPTX` が `NotImplementedError` にならなくなっている。

### 【次タスクに進む前の停止条件】

* 単体テストが3回自己修正しても合格しない場合は停止して報告する。

---

## U004-T4: 画像の抽出

### 【目的】

* 画像の代替テキストとバイナリを収集する (REQ-F-048, 049, 069, 070)。

### 【作成・編集対象ファイル】

* `app/src/office2ragknowledge/ooxml/images.py`
* 各パーサへの組み込み (`parsers/word.py`, `parsers/powerpoint.py`, `parsers/excel.py`)

### 【参照すべき仕様箇所】

* `docs/P002-frontend-spec.md` §5.11 (画像の出力)
* `docs/P003-backend-spec.md` §4.2 (拡張子の許可リスト), §8.4 手順4
* `docs/P001-requirement.md` REQ-F-048, REQ-F-049, REQ-F-069, REQ-F-070

### 【実装内容】

* `extract_image_ref(el, reader, part_name) -> tuple[str, str, str] | None` — (代替テキスト, media参照, 拡張子)。
  * 代替テキストは `cNvPr` の `descr` 属性、無ければ `name` 属性、それも無ければ `None`。
  * `a:blip` の `r:embed` を `resolve_rels` で解決し、`xl/media/image1.png` のようなパートを得る。
* **代替テキストが無い場合は `図{連番}`** を用いる (REQ-F-048)。連番は文書内の画像の出現順。
* `options.images == EXTRACT` のとき、パートのバイナリを読んで `ExtractedImage(media_ref, data, extension)` を収集する。`NONE` のときは**バイナリを読まない** (メモリ節約)。
* **拡張子の検証** (P003 §4.2): 許可リスト `{png, jpg, jpeg, gif, bmp, tiff, emf, wmf, svg}` と照合し、外れるものは `bin` とする。
* 画像ファイル名は `{連番:04d}.{拡張子}`。連番は**表計算モードでの出現順**で固定する (P003 §11 の危険要素5)。
* **OCR は行わない** (REQ-F-070)。画像バイナリを解析しない。
* 同じ `media_ref` が複数回参照される場合、`ExtractedImage` は1件のみ収集する (重複を避ける)。

### 【実装してはいけないこと】

* 画像の内容解析・OCR (REQ-F-070)。
* `images=NONE` のときにバイナリを読むこと。
* 元の埋め込みファイル名を出力ファイル名に使うこと (冪等性のため連番を使う。P002 §5.11)。

### 【Unit Test内容】

* **ファイル**: `app/tests/unit/test_images.py`
* **ケース**:
  1. 代替テキスト (`descr`) が抽出される。
  2. `descr` が無いとき `name` が使われる。
  3. どちらも無いとき `図1` になる。
  4. `images=NONE` で `ConversionResult.images` が空タプル。
  5. `images=EXTRACT` でバイナリが収集される。
  6. 拡張子が許可リストにあるものはそのまま、外れるものは `bin`。
  7. 同じ画像が2回参照されても `ExtractedImage` は1件。
  8. **画像の連番が出現順で、2回の実行で同じになる** (冪等性)。
  9. Markdown の参照が `./{ステム}_assets/0001.png` の形になる。

### 【実行コマンド】

* `pytest tests/unit/test_images.py -v`
* スプリント全体: `pytest tests/unit -v`

### 【完了条件】

* 上記9ケースすべてが合格する。
* **U004 の全タスクが `[x]` になっていること。**
* `pytest tests/unit` が全件合格。
* `ruff check src tests` と `mypy src` がエラー0件。

### 【次タスクに進む前の停止条件】

* 単体テストが3回自己修正しても合格しない場合は停止して報告する。

---

## 重要

* 各タスクの範囲外のファイルは編集しないでください。
* タスクの実装後、実行したテストコマンドと結果を報告してください。
* タスクが完了したら、上記「タスク一覧」の該当行を `[x]` に更新してください。
* 全タスクが完了したら、`docs/P007-impl-direction.md` の本スプリント行を `[x]` に更新してください。
* Executor Stepの停止条件に該当しない限り、次のタスクに自動的に進んでください。
