あなたはExecutor(実装担当)です。以下は1スプリント分の作業範囲と完了条件を定義したものです。実施後は、そのタスクの完了条件を満たしたことを確認したうえで、Executor Stepの「停止条件」(`SKILL.md` 参照)に該当しない限り、自動的に次のタスクへ進んでください。人間の指示を待って停止しないでください。

# 【スプリントID】U006 — pdf-core ※CR-001により追加

> **※CR-003 (P011 CR3-No.3)**: 本書の PyMuPDF に関する記述 (T1 の backend の実装内容・依存・T5 のバージョン画面) は、完了済みのスプリントの記録として残す。現在の実装は U008 (`U008-pdf-backend-mit.md`) で pdfminer.six に置き換えた。

> PDF を入力形式に加える。**PDF ライブラリ (PyMuPDF) を import してよいのは `pdf/backend.py` だけ**である (P003 §2.3)。ライセンスの観点から後でライブラリを差し替える可能性があるため、他のモジュールは `pdf/model.py` の型だけを扱うこと。

## タスク一覧(OKF副目次)

- [x] U006-T1 [PDFの型・テスト用PDF生成・安全な読み取り](#u006-t1-pdfの型テスト用pdf生成安全な読み取り) — model / make_pdf / safety / backend
- [x] U006-T2 [文字列の組み立てと構造木](#u006-t2-文字列の組み立てと構造木) — text / structure
- [x] U006-T3 [タグなしPDFの基本レイアウト](#u006-t3-タグなしpdfの基本レイアウト) — 行片・図領域・段落 (段組み補正なし)
- [x] U006-T4 [PDFパーサ](#u006-t4-pdfパーサ) — 構造の写像・警告・メタデータ
- [x] U006-T5 [既存の層への統合](#u006-t5-既存の層への統合) — 形式判定・convert・inspect・レンダラ・CLI・依存

---

## U006-T1: PDFの型・テスト用PDF生成・安全な読み取り

### 【目的】

* PDF をライブラリ非依存の型 (`PdfSource`) に変換する入口を作る。暗号化・破損・展開爆弾をここで止める。

### 【作成・編集対象ファイル】

* `app/src/office2ragknowledge/pdf/__init__.py` / `pdf/model.py` / `pdf/safety.py` / `pdf/backend.py`
* `app/tests/helpers/make_pdf.py`
* `app/pyproject.toml` (`pymupdf>=1.28,<2` を実行時依存に (※P011 CR-No.4)、`pypdf` を dev に追加。mypy の `ignore_missing_imports` に `pymupdf.*` / `fitz.*` を追加)

### 【参照すべき仕様箇所】

* `docs/P003-backend-spec.md` §1.4 (スパイク結果), §4.4 (安全な PDF 読み取り), §7A.2 (バックエンドの出力)
* `docs/P006-test-plan.md` §3.4 (PDF のテストデータ)

### 【実装内容】

* **`pdf/model.py`**: P003 §7A.2 の表のとおり `PdfChar` / `PdfPage` / `StructInfo` / `PdfMetadata` / `PdfSource` を `@dataclass(frozen=True, slots=True)` で定義する。矩形は `tuple[float, float, float, float]` (x0, top, x1, bottom)。
* **`pdf/safety.py`**: `MAX_STREAM_BYTES = 256 * 1024**2`、`MAX_TOTAL_STREAM_BYTES = 1024**3`。`check_inflated_sizes(streams: Iterable[bytes]) -> None` は各バイト列を `zlib.decompressobj().decompress(raw, max_length)` で上限付きで展開し、超過で `FileTooLargeError` を送出する。zlib として展開できないものは数えない。**上限はモジュール定数を関数実行時に参照する** (テストで `monkeypatch` できるように)。
* **`pdf/backend.py`** (PyMuPDF を import する唯一のモジュール):
  * import 時に `pymupdf.TOOLS.mupdf_display_errors(False)` / `mupdf_display_warnings(False)` を呼ぶ。
  * `open_pdf(data: bytes) -> PdfSource`: P003 §4.4 の手順1〜6。`needs_pass` → `PasswordProtectedError`、0 ページ → `CorruptedFileError`、Flate ストリーム (`xref_get_key(x, "Filter")` が `/FlateDecode` または配列の先頭が `/FlateDecode`) の `xref_stream_raw` を `check_inflated_sizes` に渡す。
  * 文字: `page.get_text("rawdict", flags=TEXT_COLLECT_STRUCTURE | TEXT_PRESERVE_WHITESPACE | TEXT_MEDIABOX_CLIP)` を再帰的に辿り、構造ブロック (`type == 2`) の `index` を経路に積む。`segments` は各テキストブロックの文字範囲。
  * `StructInfo`: `pymupdf.mupdf` の低水準 API で `Root/StructTreeRoot` の `/K` を辿る (P003 §7A.2)。`RoleMap` を適用して標準タグにする。`/Alt` は `pdf_to_text_string`、`/A` (辞書または辞書の配列) から `ListNumbering`・`ColSpan`・`RowSpan`。循環防止 (オブジェクト番号の記録) と深さ 64 の上限。
  * 図領域: `page.cluster_drawings()` の矩形。画像数: `len(page.get_image_info())`。
  * メタデータ: `doc.metadata` (title/author/creationDate/modDate) を優先し、欠けた項目を `doc.get_xml_metadata()` の XMP (安全な XML パーサ = `ooxml/xml_utils.py` を使う) で補う。PDF の日付 `D:YYYYMMDDHHmmSS+HH'mm'` (秒・タイムゾーンは省略されうる) を `datetime` にする関数を本モジュールに置く。
  * 権限: `copy_restricted = not (doc.permissions & pymupdf.PDF_PERM_COPY)`。
  * **PyMuPDF の例外を外に漏らさない**: `Office2RagError` 以外の例外は `CorruptedFileError` に変換する。
* **`tests/helpers/make_pdf.py`**: P006 §3.4 のとおり。`Text(x, y, text, size, mcid=None, artifact=None)`・`Page(items, rects, width, height)`・`Elem(tag, kids, alt, extra)` と `build_pdf(pages, struct=None, title=None, author=None, mcr=False, compress=False)`。`artifact` は `"Header"`/`"Footer"` で Pagination の Artifact。`compress=True` で内容ストリームを Flate で圧縮する。`encrypt_pdf(data, user, owner, copy_allowed)` は pypdf で暗号化する (`/P` は -3904 など仕様どおりの値)。`flate_bomb_pdf(inflated_size)` は高圧縮ストリームを追加した PDF を返す。

### 【実装してはいけないこと】

* `pdf/backend.py` 以外での `pymupdf` / `fitz` の import。
* JavaScript・注釈アクション・埋め込みファイルを扱う API の呼び出し (REQ-NF-020)。
* 展開サイズ検査の前にページのテキスト抽出を行うこと。

### 【Unit Test内容】

* **ファイル**: `app/tests/unit/test_pdf_backend.py`
  1. タグなし PDF: ページ数・文字・座標 (左上原点)・`path is None`・`has_struct_tree=False`。
  2. タグ付き PDF (整数 MCID): 文字に経路が付き、`StructInfo` のタグ・`/Alt`・`ListNumbering`・`ColSpan` が取れる。`RoleMap` の独自タグが標準タグになる。
  3. **MCR 辞書形式のタグ付き PDF: `has_struct_tree=True` だが文字の `path` がすべて `None`** (P003 §1.4 #2 の既知の挙動を固定)。
  4. Artifact (Header) の文字は `path is None`。
  5. メタデータ: 日本語のタイトル・作成者・作成日時 (タイムゾーン付き) が取れる。日付の解析関数の境界 (秒なし・`Z`・不正値で `None`)。
  6. 開くパスワードありで `PasswordProtectedError` (E-005)。所有者パスワードのみ + コピー禁止で開け、`copy_restricted=True`。
  7. 破損 (ヘッダのみ・途中で切断) で `CorruptedFileError` (E-007)。
  8. **展開爆弾**: `MAX_STREAM_BYTES` を小さく差し替え、`flate_bomb_pdf` で `FileTooLargeError` (E-008)。合計上限も同様。
  9. 図領域: 矩形を描いた PDF で `figure_rects` が1つ以上。画像数が 0。
  10. **MuPDF が標準エラーに何も書かない** (破損 PDF を開いたときに `capfd` で確認)。

---

## U006-T2: 文字列の組み立てと構造木

### 【目的】

* 文字から行・文字列を組み立てる規則と、ページごとの構造断片を文書全体の木に統合する処理を作る。

### 【作成・編集対象ファイル】

* `app/src/office2ragknowledge/pdf/text.py` / `pdf/structure.py`

### 【参照すべき仕様箇所】

* `docs/P003-backend-spec.md` §7A.3 (被覆率・統合), §7A.5 (行の組み立て)

### 【実装内容】

* **`pdf/text.py`**: `is_cjk(ch)`、`group_lines(chars) -> list[list[PdfChar]]` (内容順の文字を行に分ける)、`line_text(chars) -> str` (空白の補完)、`join_lines(texts) -> str` (CJK の連結規則)、`text_of(chars) -> str` (= 行に分けて連結)。
* **`pdf/structure.py`**: `TextRun` (文字の並び) と `StructNode(path, info, items)`。`coverage(source) -> float`、`is_tagged(source) -> tuple[bool, bool]` (タグ付きか, 不完全タグで切り替えたか)、`build_tree(source) -> list[StructNode]` (ルート要素の並び)。P003 §7A.3 の手順のとおり、経路ごとに1ノード、初出時に親の末尾へ追加。親ノードが未出の経路 (ページ途中から現れた子) は祖先を補って作る。

### 【実装してはいけないこと】

* 座標による並べ替え (タグ付きは構造の順序が正。REQ-F-127)。

### 【Unit Test内容】

* **ファイル**: `app/tests/unit/test_pdf_text.py`, `app/tests/unit/test_pdf_structure.py`
  1. 英語の単語間の隙間に空白が補われ、日本語の文字間には補われない。元の空白は重複しない。
  2. 2行の日本語は空白なしで、英語は空白1つで連結される。日英混在の境界。
  3. 縦位置の違う文字が別の行になる。
  4. 被覆率: 全文字に経路 → タグ付き、半分未満 → タグなし + 切り替えフラグ、構造ツリーなし → タグなし (フラグなし)、文字0 → タグなし。
  5. **2ページにまたがる `P` が1ノードにまとまり、テキストがページ順に並ぶ**。
  6. 要素内で MCID → 子要素 → MCID の順の内容が、その順で `items` に入る。

---

## U006-T3: タグなしPDFの基本レイアウト

### 【目的】

* タグなし PDF を、段組み補正なし (上→下) の読み順で段落と図ユニットに組み立てる。段組みとヘッダー・フッターは U007 で加えるため、**並べ替えと除去を差し込める関数構成**にしておく。

### 【作成・編集対象ファイル】

* `app/src/office2ragknowledge/pdf/layout.py`

### 【参照すべき仕様箇所】

* `docs/P003-backend-spec.md` §7A.6 (行片), §7A.8 (図領域), §7A.9 の「段落の組み立て」
* `docs/P002-frontend-spec.md` §5.12.3

### 【実装内容】

* `Fragment` (行片: text・矩形・size・page)、`FigureUnit` (矩形・行の並び)、`LayoutBlock` (段落: `kind="paragraph"`, `text`, または図: `kind="figure"`, `lines`)。
* `build_fragments(page) -> list[Fragment]` (P003 §7A.6)。
* `extract_figures(page, fragments) -> tuple[list[FigureUnit], list[Fragment]]` (P003 §7A.8)。
* `order_units(page, units) -> tuple[list[unit], int]` — **このタスクでは上→下・左→右の単純な並べ替え**とし、段組みを検出した数 (常に 0) を返す。U007 で段組み検出に置き換える。
* `build_paragraphs(ordered) -> list[LayoutBlock]` (P003 §7A.9 の段落の区切り規則 (a)〜(d) と同じ高さの行片の連結)。
* `layout_document(source, *, shapes: bool, headers_footers: bool) -> LayoutResult` (ブロックの並び・`headers_footers_removed`・`multi_column_pages`)。このタスクではヘッダー・フッター除去を行わない (U007)。座標は 0.01pt に丸めて比較する。

### 【Unit Test内容】

* **ファイル**: `app/tests/unit/test_pdf_layout.py`
  1. 行間の広い2つの文が2段落、狭い2行は1段落に連結される。
  2. 文字サイズの大きく違う行は別段落になる。
  3. 同じ高さで離れた2つの行片 (タブ区切り) が1行に空白で連結される。
  4. **枠で囲まれた文字が図ユニットになり、本文から外れる**。ページ全体の枠 (面積 80% 以上) と下線 (高さ 5pt 以下) は図にならない。
  5. `shapes=False` で枠内の文字が本文の段落に残る。
  6. ページの切り替わりで段落が分かれる。
  7. 同じ入力で2回組み立てて同じ結果。

---

## U006-T4: PDFパーサ

### 【目的】

* `PdfSource` から中間表現 `Document` を作る。

### 【作成・編集対象ファイル】

* `app/src/office2ragknowledge/parsers/pdf.py`

### 【参照すべき仕様箇所】

* `docs/P003-backend-spec.md` §7A.1, §7A.4, §7A.4.1, §7A.10
* `docs/P002-frontend-spec.md` §5.12.1, §5.12.2, §9.3

### 【実装内容】

* `PdfParser.parse(data: bytes, filename: str, options: ConvertOptions, converted_at: datetime) -> Document`。
* タグ付き: `build_tree` の結果を P003 §7A.4 の表で写像する (見出し・リスト (入れ子の深さ・番号付き判定)・表 (ColSpan/RowSpan の格子・列数の揃え・`has_header`)・図 (`Image` / `ShapeText(shape_kind="図" / "数式")`)・段落・まとまり・インライン・Artifact)。構造外の文字の行数を `headers_footers_removed` とする。
* タグなし: `layout_document` の結果を `Paragraph` / `ShapeText(shape_kind="図")` にする。
* 警告 (P003 §7A.10): テキストなし・テキストの無いページ (`3, 5-7` 形式)・コピー禁止・不完全タグ・`images=EXTRACT` で画像参照あり。
* `DocumentMeta`: `source_format=PDF`、`pdf_structure`、`title`/`author`/日時、`stats={"pages", "headers_footers_removed", "multi_column_pages"}`。`Document.title` はメタデータのタイトル、無ければ `Path(filename).stem`。
* ログ (規約9): ページ数・ブロック数・警告数のみ。本文を渡さない。

### 【Unit Test内容】

* **ファイル**: `app/tests/unit/test_pdf_parser.py`
  1. **`H1`/`H2`/`H3` が level 1/2/3 の `Heading` として文書順に並ぶ**。`H` は祖先 `Sect` の数 + 1。
  2. **3段のネストリストが level 0/1/2 の `ListItem` になる**。`ListNumbering=Decimal` で `ordered=True`、属性なし + `Lbl` が `1.` で `ordered=True`、`•` で `False`。
  3. 表: `TH` の見出し行、`ColSpan=2` の複製 (`from_merge`)、`RowSpan=2` の複製、列数の揃え。
  4. `Figure` + `/Alt` で `Image(alt_text)`、内側の文字で `ShapeText(shape_kind="図")`。`shapes=False` で `ShapeText` なし。
  5. `P` の中の `Span` のテキストが同じ段落に連結される。
  6. Artifact (ヘッダー) が出力されず、`stats["headers_footers_removed"] >= 1`。
  7. タグなし PDF: `Heading` / `ListBlock` が1つも無い。`pdf_structure="untagged"`。
  8. MCR 辞書形式 → タグなし + 不完全タグの警告。
  9. 文字の無い画像だけのページ → ページ番号付きの警告。全ページ文字なし → テキストなしの警告。
  10. コピー禁止 → 警告。`images=EXTRACT` + `/Alt` → 警告。
  11. タイトル: メタデータ優先、無ければファイル名。

---

## U006-T5: 既存の層への統合

### 【目的】

* PDF を形式判定・変換・構造確認・レンダリング・CLI に通す。

### 【作成・編集対象ファイル】

* `models/options.py` (`DocumentFormat.PDF`)、`models/document.py` (`DocumentMeta.pdf_structure: str | None = None`)、`models/result.py` (`DocumentInfo.pdf_tagged: bool | None = None`)
* `detect.py`、`convert.py`、`inspection.py`、`errors.py` (E-002・E-005 の案内文。P002 §9.1)
* `render/markdown.py`、`render/frontmatter.py`
* `cli/main.py` (アプリの説明・`convert` の説明・`--headers-footers` の説明)、`cli/console.py` (バージョン画面に PyMuPDF・inspect の「構造」行・JSON の `pdf_tagged`)
* `batch.py` は `SUPPORTED_EXTENSIONS` の参照で自動的に対象になるため変更不要であることを確認する

### 【参照すべき仕様箇所】

* `docs/P003-backend-spec.md` §4.3, §8.1, §8.3, §9.1
* `docs/P002-frontend-spec.md` §3.1, §3.2, §3.5, §5.3, §5.11, §6.3, §6.4

### 【実装内容】

* `detect.py`: `SUPPORTED_EXTENSIONS` に `.pdf`。`detect_format` は先頭 1024 バイト内の `%PDF-` で `PDF`。
* `convert.py`: `fmt is PDF` のとき `SafeZipReader` を使わず `PdfParser().parse(data, ...)`。
* `inspection.py`: PDF は `PdfParser` を使い、`PasswordProtectedError` → `protected`、`CorruptedFileError`/`FileTooLargeError` → `corrupted`。`unit_label="ページ"`、`pdf_tagged`。
* `render/frontmatter.py`: `meta.pdf_structure` があれば `source_format` の直後に `pdf_structure: "..."`。
* `render/markdown.py`: PDF の `stats` を P002 §5.3 の順で組み立てる (パーサの `pages`・`headers_footers_removed`・`multi_column_pages` を用いる)。**`Image.media_ref` が空なら `--images` によらずプレースホルダ**。
* `cli/console.py`: `print_version` に PyMuPDF の版、`print_inspect` の表の下に PDF の構造の行、`print_inspect_json` に `pdf_tagged`。

### 【実装してはいけないこと】

* Word / Excel / PowerPoint の出力を変えること (既存のゴールデン・単体テストが全件合格のままであること)。

### 【Unit Test内容】

* **ファイル**: `test_detect.py`・`test_convert.py`・`test_frontmatter.py`・`test_markdown_render.py`・`test_cli_options.py` に追加 (既存ファイルへの追記)
  * **実施記録 (P102)**: 既存ファイルに散らさず `app/tests/unit/test_pdf_wiring.py` にまとめて実装した (PDF の統合の検証を1箇所で読めるようにするため)。ケースは下記 1〜6 をすべて含む。
  1. `%PDF-` で `PDF`、先頭に数バイトのゴミがあっても 1024 バイト以内なら `PDF`。`.pdf` 拡張子が対応拡張子に含まれる。
  2. `convert_bytes` で PDF が1出力 (`{ステム}.md`)・`source_format: "pdf"`・`pdf_structure` が出る。暗号化で E-005、破損で E-007。
  3. front matter: `pdf_structure` は PDF のみ、`source_format` の直後。
  4. レンダラ: PDF の `stats` のキー順。`media_ref` 空の画像は `images=EXTRACT` でもプレースホルダ。
  5. `inspect_file`: PDF で `unit_label="ページ"`・`unit_count`=ページ数・`pdf_tagged`、暗号化で `protected`。
  6. バージョン画面に `PyMuPDF` が出る。
