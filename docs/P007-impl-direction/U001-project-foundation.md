あなたはExecutor(実装担当)です。以下は1スプリント分の作業範囲と完了条件を定義したものです。スプリントは複数のタスクから成り、各タスクに個別の完了条件とチェックボックスを持ちます。実施後は、そのタスクの完了条件を満たしたことを確認したうえで、Executor Stepの「停止条件」(`SKILL.md` 参照)に該当しない限り、自動的に次のタスクへ進んでください。人間の指示を待って停止しないでください。

# 【スプリントID】U001 — project-foundation

## タスク一覧(OKF副目次)

* 状態は `[ ]`(未着手) / `[~]`(進行中) / `[x]`(完了) の3種類とする。1タスクの作業を開始したら `[~]` に、完了条件をすべて満たしたら `[x]` に更新する。
* このスプリントファイル自体の状態(`docs/P007-impl-direction.md` の該当行)は、全タスクが `[x]` になって初めて `[x]` にする。
* **中断からの再開**: `[~]` のタスクがあれば、それが中断時点の作業対象である。再開時は該当タスクの【完了条件】を実際に再実行して現状を確認してから続きを行う。
* **先行実装の禁止**: `[~]` のタスクを進める際、まだ `[ ]` の後続タスクが対象とするファイルには着手しない。

- [x] U001-T1 [プロジェクトの初期化](#u001-t1-プロジェクトの初期化) — ビルド構成・依存・静的解析設定・ディレクトリ構造
- [x] U001-T2 [中間表現とオプションの型定義](#u001-t2-中間表現とオプションの型定義) — models/ 配下の全データモデル
- [x] U001-T3 [例外階層](#u001-t3-例外階層) — errors.py
- [x] U001-T4 [安全なXML/ZIP読み取り基盤](#u001-t4-安全なxmlzip読み取り基盤) — ooxml/xml_utils.py, ooxml/zip_reader.py
- [x] U001-T5 [形式判定と設定読込](#u001-t5-形式判定と設定読込) — detect.py (API-05), config.py (API-07)
- [x] U001-T6 [描画基盤](#u001-t6-描画基盤) — render/escape.py, render/frontmatter.py

---

## U001-T1: プロジェクトの初期化

### 【目的】

* 以降の全スプリントが動作する土台となる、ビルド構成・依存・静的解析設定・ディレクトリ構造を作る。

### 【作成・編集対象ファイル】

* `app/pyproject.toml`
* `app/README.md`
* `app/src/office2ragknowledge/__init__.py` (この時点では空でよい)
* `app/src/office2ragknowledge/py.typed` (空ファイル)
* `app/tests/__init__.py`
* `app/.gitignore`

### 【参照すべき仕様箇所】

* `docs/P005-impl-plan.md` §6.1 (依存とその版), §6.2 (コマンド)
* `docs/P003-backend-spec.md` §2.2 (モジュール構成), §12C (静的解析の設定方針)
* `docs/P001-requirement.md` REQ-NF-012, REQ-NF-017, REQ-NF-019, REQ-F-103

### 【実装内容】

* `app/` 配下を **uv 相当の構成** で初期化する。`app/` ディレクトリと `app/INDEX.md` は既に存在する場合があるため、スキャフォールドツールをそのまま実行せず、必要なファイルを個別に作成してよい。既存の `INDEX.md` を削除・上書きしないこと。
* `app/pyproject.toml` を PEP 621 形式で作成する。
  * `[project]`: `name = "office2ragknowledge"`, `version = "1.0.0"`, `requires-python = ">=3.11"`, `license = {text = "MIT"}`, 説明文は日本語で可。
  * `dependencies`: `openpyxl>=3.1,<4` / `python-docx>=1.1,<2` / `python-pptx>=1.0,<2` / `lxml>=5.0` / `typer>=0.12` / `rich>=13.0`
  * `[project.optional-dependencies] dev`: `pytest>=8.0` / `pytest-cov` / `ruff` / `mypy`
  * `[project.scripts]`: `office2rag = "office2ragknowledge.cli.main:app"`
  * `[build-system]`: `hatchling` を用いる (`requires = ["hatchling"]`, `build-backend = "hatchling.build"`)。パッケージの探索先は `src/office2ragknowledge`。
  * `[tool.ruff]`: `line-length = 100`, `src = ["src"]`。`[tool.ruff.lint] select = ["E","F","I","UP","B"]`。
  * `[tool.mypy]`: `strict = true`, `python_version = "3.11"`, `files = ["src"]`。`docx` `pptx` `openpyxl` に対して `[[tool.mypy.overrides]]` で `ignore_missing_imports = true` を設定する。
  * `[tool.pytest.ini_options]`: `testpaths = ["tests"]`, `markers = ["perf: 性能テスト (既定では実行しない)"]`, `addopts = "-m 'not perf'"`。
* `app/src/office2ragknowledge/py.typed` を空ファイルとして作成する (REQ-F-103)。`pyproject.toml` のパッケージデータに含める設定を入れる。
* 次の空のパッケージディレクトリと `__init__.py` を作成する: `models/`, `ooxml/`, `parsers/`, `render/`, `cli/`。
* `app/tests/` 配下に `unit/`, `integration/`, `acceptance/`, `helpers/`, `fixtures/` を作成し、それぞれ `__init__.py` (fixtures を除く) を置く。
* 開発環境を構築し、依存が導入できることを確認する。`uv sync` が使えない場合は `python -m venv` + `pip install -e ".[dev]"` でよい。**どの方法で構築したかを報告に含めること。**
* `app/.gitignore` に `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `htmlcov/`, `.coverage` を記載する。

### 【実装してはいけないこと】

* アプリケーションのロジックを一切書かない。このタスクは構成の準備のみ。
* `app/INDEX.md` の削除・上書き (P020 の成果物であるため)。
* リポジトリ直下 (`app/` の外) に `office2rag.toml` を置くこと (テストの独立性が壊れる。P006 §4.2)。

### 【Unit Test内容】

* **テスト対象**: パッケージが import できること。
* **ファイル**: `app/tests/unit/test_package.py`
* **ケース**:
  1. `import office2ragknowledge` が成功する。
  2. `office2ragknowledge.__version__` が `"1.0.0"` である (`__init__.py` に `__version__` を定義すること)。
  3. `py.typed` が同梱されている (`importlib.resources` またはパス存在確認)。

### 【実行コマンド】

* 依存の導入: `uv sync --extra dev` または `pip install -e ".[dev]"` (`app/` で実行)
* テスト: `pytest tests/unit/test_package.py` (`app/` で実行)
* lint: `ruff check src tests`
* 型検査: `mypy src`

### 【完了条件】

* 上記のテストが合格する。
* `ruff check src tests` がエラー0件。
* `mypy src` がエラー0件。
* 依存6件がすべて import できる (`python -c "import openpyxl, docx, pptx, lxml, typer, rich"` が成功)。

### 【次タスクに進む前の停止条件】

* 依存ライブラリの導入がネットワーク等の理由で3回試みても失敗する場合は停止し、`docs/.stop-report.md` に記録して人間に報告する。
* Python 3.11 での動作確認ができない環境の場合は、**停止せず** 3.14 のみで進め、その旨を報告に含める (P005 §7 R6)。

---

## U001-T2: 中間表現とオプションの型定義

### 【目的】

* `docs/P002-frontend-spec.md` §6.2・§6.4・§7.3 が定めた全データモデルを、実装として起こす。以降の全スプリントがこの型に依存する。

### 【作成・編集対象ファイル】

* `app/src/office2ragknowledge/models/options.py`
* `app/src/office2ragknowledge/models/inline.py`
* `app/src/office2ragknowledge/models/document.py`
* `app/src/office2ragknowledge/models/sheet.py`
* `app/src/office2ragknowledge/models/result.py`
* `app/src/office2ragknowledge/models/__init__.py` (再輸出)

### 【参照すべき仕様箇所】

* `docs/P002-frontend-spec.md` §6.2 (オプション型と列挙型), §6.4 (戻り値型), §7.3 (型定義の全表), §7.4 (不変条件 INV-01〜11)
* `docs/P003-backend-spec.md` §5.1 (実装形式), §5.2 (不変条件の担保場所)

### 【実装内容】

* すべて `@dataclass(frozen=True, slots=True)` で定義する。コレクションのフィールドは `tuple[...]` とする (`list` を使わない)。
* **`models/options.py`**
  * 列挙型6種を `enum.StrEnum` (Python 3.11+) で定義する。値は CLI の文字列と一致させる。
    * `ExcelModes`: `BOTH="both"`, `TABLE="table"`, `GRID="grid"`
    * `OutputMode`: `TABLE="table"`, `GRID="grid"` (**`BOTH` を持たせない**)
    * `ShapeStyle`: `QUOTE="quote"`, `HEADING="heading"`, `PLAIN="plain"`
    * `ImageMode`: `NONE="none"`, `EXTRACT="extract"`
    * `OnExists`: `SKIP="skip"`, `OVERWRITE="overwrite"`, `FAIL="fail"`
    * `DocumentFormat`: `DOCX="docx"`, `XLSX="xlsx"`, `PPTX="pptx"`
  * `ExcelOptions`: `modes` `grid_separator` `table_regions` `max_table_regions` `formulas` `max_rows` (既定値は P002 §6.2 のとおり)
  * `ConvertOptions`: `excel` `shapes` `shape_style` `images` `include_hidden` `notes` `headers_footers` `comments` `front_matter`
  * `BatchOptions`: `convert` `recursive` `on_exists` `jobs` `output_dir`
  * `LogOptions`: `level: Literal["quiet","info","verbose"]`, `format: Literal["text","json"]`, `file: Path | None`
  * `Config`: `convert: ConvertOptions`, `batch: BatchOptions`, `log: LogOptions`
  * **注意**: frozen dataclass の既定値に可変でないネストした dataclass を置く場合、`field(default_factory=...)` を用いること (`ConvertOptions()` をそのまま既定値に書くと共有される。frozen なので実害は小さいが、`default_factory` で統一する)。
* **`models/inline.py`**: `InlineRun` (`text` `bold` `italic` `strike` `code` `link_url`)、`ListItem` (`level` `ordered` `runs`)、`TableCell` (`runs` `from_merge`)、`TableRow` (`cells` `is_header`)、`ShapeParagraph` (`runs` `level`)。
  * `InlineRun` を作るヘルパ関数 `make_run(text: str, **flags) -> InlineRun | None` を用意し、`text` が空文字なら `None` を返す (INV-03 の担保)。
* **`models/document.py`**
  * `Block` を抽象基底クラス (`@dataclass(frozen=True, slots=True)` のまま、フィールドを持たない) として定義する。
  * バリアント: `Heading` (`level:int` `runs`)、`Paragraph` (`runs`)、`ListBlock` (`items`)、`Table` (`rows` `has_header`)、`ShapeText` (`shape_kind` `shape_name` `anchor` `group_path` `paragraphs` `tables`)、`Image` (`alt_text` `media_ref` `extension`)、`Footnote` (`marker` `runs`)、`SlideBreak` (`slide_number` `slide_title` `notes`)。
  * `DocumentMeta`: `source_file` `source_path` `source_format` `source_size_bytes` `source_sha256` `title` `author` `created_at` `modified_at` `converted_at` `converter` `stats: Mapping[str,int]` `warnings: tuple[str,...]`。日時は `datetime | None`。
  * `Document`: `format` `title` `meta` `blocks` `warnings`。
* **`models/sheet.py`**
  * `Cell`: `row:int` `col:int` `text:str` `is_formula:bool` `formula:str|None` `value_missing:bool` (row/col は **1起点**)
  * `SheetRow`: `row_index:int` `cells:tuple[Cell,...]` — `is_empty` は **プロパティ**として `len(self.cells) == 0` を返す (フィールドとして持つと不整合が起きうる)
  * `TableRegion`: `top` `left` `bottom` `right` `has_header` (1起点の閉区間)
  * `MergedRange`: `top` `left` `bottom` `right` (1起点の閉区間)。`contains(row, col) -> bool` メソッドを持たせる。
  * `Sheet(Block)`: `name` `hidden` `rows` `merged` `regions` `region_split_abandoned` `shapes` `truncated_at` `total_rows` `formula_without_cache_count` `shape_count` `is_empty`
    * **`shape_count`** は、テキストを持たない図形も含めた図形の総数 (※P011 の矛盾点 No.2 にもとづき追加)。`shapes` は INV-05 によりテキストを持つ図形しか保持しないため、`inspect` の「図形」列 (総数と、うちテキストあり数) を出すにはこのフィールドが要る。U001 の時点では既定値 0 で定義し、U003-T4 で実際の値を格納する。
* **`models/result.py`**: `ExtractedImage` (`media_ref` `data:bytes` `extension`)、`MarkdownOutput` (`mode` `filename_suffix` `markdown` `meta` `warnings`)、`ConversionResult` (`source_path` `format` `outputs` `images` `warnings` + `markdown` プロパティ)、`FailureInfo` (`path` `code` `message`)、`BatchResult` (`succeeded` `skipped` `failures` `warnings` `written_files` `elapsed_seconds` + `exit_code` プロパティ)、`DocumentInfo` (P002 §6.4 の全フィールド)、`WrittenFiles` (`markdown_paths` `image_paths` `skipped_paths`)。
  * **`ConversionResult.markdown` プロパティは、`len(self.outputs) != 1` のとき `ValueError` を送出する** (P002 §6.4)。メッセージは日本語で、`outputs` を使うよう案内する。
  * **`BatchResult.exit_code` プロパティ**: `failures` が1件以上なら `1`、それ以外は `0` を返す (`2` は CLI 層が返す)。
* `models/__init__.py` で全型を再輸出する。

### 【実装してはいけないこと】

* パーサ・レンダラのロジック。このタスクは型定義のみ。
* `models/` から `parsers/` `render/` `ooxml/` を import すること (規約1)。
* `Sheet.is_empty` を `SheetRow.is_empty` と混同すること。`Sheet.is_empty` は「シート全体に非空セルが1つもない」を意味するフィールド、`SheetRow.is_empty` は「その行に非空セルがない」を意味するプロパティである。

### 【Unit Test内容】

* **テスト対象**: `models/` の全型
* **ファイル**: `app/tests/unit/test_models.py`
* **ケース**:
  1. 全 dataclass が frozen である (フィールドへの代入が `FrozenInstanceError` を送出する)。
  2. 列挙型の値が CLI 文字列と一致する (`ExcelModes.BOTH == "both"` 等、6種すべて)。
  3. `OutputMode` に `BOTH` が**存在しない** (`hasattr` が偽)。
  4. `make_run("")` が `None` を返し、`make_run("あ")` が `InlineRun` を返す (INV-03)。
  5. `ConversionResult.markdown` が、`outputs` 1件なら文字列を返す。
  6. **`ConversionResult.markdown` が、`outputs` 2件なら `ValueError` を送出する** (P002 §6.4 の重要な契約)。
  7. `ConversionResult.markdown` が、`outputs` 0件でも `ValueError` を送出する。
  8. `BatchResult.exit_code` が、失敗0件で `0`、1件以上で `1` を返す。
  9. `SheetRow(row_index=1, cells=()).is_empty` が `True`、セルがあれば `False`。
  10. `MergedRange(2,1,3,4).contains(3,2)` が `True`、`contains(4,2)` が `False` (境界を含む閉区間であること)。
  11. `ConvertOptions()` の既定値が P002 §6.2 のとおり (`shapes=True`, `images=NONE`, `notes=True`, `excel.modes=BOTH`, `excel.grid_separator=""`, `excel.max_table_regions=100`, `excel.max_rows=10000` 等)。

### 【実行コマンド】

* `pytest tests/unit/test_models.py -v`
* `mypy src`

### 【完了条件】

* 上記11ケースすべてが合格する。
* `mypy src` がエラー0件 (strict)。
* `ruff check src tests` がエラー0件。

### 【次タスクに進む前の停止条件】

* 単体テストが3回自己修正しても合格しない場合は停止し、`docs/.stop-report.md` に記録して人間に報告する。

---

## U001-T3: 例外階層

### 【目的】

* `docs/P002-frontend-spec.md` §6.5・§9.1 が定めた例外階層とエラーコードを実装する。CLI 層はこの例外の属性をそのまま画面表示に用いる。

### 【作成・編集対象ファイル】

* `app/src/office2ragknowledge/errors.py`

### 【参照すべき仕様箇所】

* `docs/P002-frontend-spec.md` §6.5 (例外階層), §9.1 (エラーコード表 E-001〜E-019)
* `docs/P001-requirement.md` REQ-F-093, REQ-NF-005

### 【実装内容】

* 基底 `Office2RagError(Exception)` を定義し、次の属性を持たせる。
  * `code: str` (例: `"E-002"`)
  * `path: Path | None`
  * `hint: str` (対処方法。日本語)
  * `__init__(self, message: str, *, code: str, path: Path | None = None, hint: str = "")`
  * `__str__` は `message` を返す。
* 階層: `InputError(Office2RagError)` → `UnsupportedFormatError` (E-002) / `PasswordProtectedError` (E-005) / `CorruptedFileError` (E-007) / `FileTooLargeError` (E-008)。`OutputError(Office2RagError)` (E-004)。`ConfigError(Office2RagError)` (E-006)。
* 各サブクラスは `code` を既定値として持ち、呼び出し側が指定しなくてよいようにする。
* **エラーコードと標準メッセージ・hint の対応表を、モジュール内の定数 `ERROR_CATALOG: dict[str, tuple[str, str]]` として持つ** (コード → (種別表示名, hint))。P002 §9.1 の E-001〜E-019 をすべて登録する。CLI 層 (U005) がこの表を参照して SCR-06 を描画する。
* ヘルパ関数 `catalog_entry(code: str) -> tuple[str, str]` を用意し、未登録コードには汎用の種別名と空 hint を返す (KeyError を出さない)。

### 【実装してはいけないこと】

* 例外メッセージの英語化 (日本語固定。REQ-NF-016)。
* `code` を持たない例外の定義。
* 例外クラス内でのログ出力 (ログは CLI 層の責務)。

### 【Unit Test内容】

* **テスト対象**: `errors.py`
* **ファイル**: `app/tests/unit/test_errors.py`
* **ケース**:
  1. 各例外クラスが既定の `code` を持つ (`UnsupportedFormatError("x").code == "E-002"` 等、6クラス)。
  2. すべての例外が `Office2RagError` のサブクラスである。
  3. `InputError` 系4クラスが `InputError` のサブクラスである。
  4. `path` と `hint` が保持される。
  5. **`ERROR_CATALOG` に18コードが登録されている。** 内訳は E-001〜E-008 と E-010〜E-019 であり、**E-009 は欠番**である (P002 §9.1 の表に存在しない)。期待する件数は 18 であって 19 ではない。※P011 の矛盾点 No.4 にもとづき記述を一本化した。
  6. `catalog_entry("E-999")` が例外を送出せず、汎用の値を返す。
  7. すべての `hint` が空文字でない (対処方法が必ず書かれている。REQ-F-093)。

### 【実行コマンド】

* `pytest tests/unit/test_errors.py -v`

### 【完了条件】

* 上記7ケースすべてが合格する。
* `mypy src` / `ruff check src tests` がエラー0件。

### 【次タスクに進む前の停止条件】

* 単体テストが3回自己修正しても合格しない場合は停止して報告する。

---

## U001-T4: 安全なXML/ZIP読み取り基盤

### 【目的】

* セキュリティ要件 (XXE 無効化・ZIP爆弾・パストラバーサル) を、**アプリ全体で唯一の入口**として実装する。以降のすべてのモジュールはここを経由して XML と ZIP を扱う。

### 【作成・編集対象ファイル】

* `app/src/office2ragknowledge/ooxml/xml_utils.py`
* `app/src/office2ragknowledge/ooxml/zip_reader.py`

### 【参照すべき仕様箇所】

* `docs/P003-backend-spec.md` §4.1 (パーサ設定表・名前空間表), §4.2 (ZIP検査の閾値表)
* `docs/P001-requirement.md` REQ-NF-006, REQ-NF-007, REQ-NF-008, REQ-NF-010

### 【実装内容】

* **`xml_utils.py`**
  * `NS: dict[str, str]` に P003 §4.1 の名前空間11種を定義する (`w` `mc` `wps` `wpg` `a` `p` `xdr` `m` `dgm` `r` `v`)。URI は OOXML 標準のもの。
  * `qn(prefix_colon_tag: str) -> str`: `"w:p"` のような文字列を `"{URI}p"` に変換するヘルパ。
  * `safe_parser() -> etree.XMLParser`: `resolve_entities=False`, `no_network=True`, `load_dtd=False`, `huge_tree=False`, `recover=False` を設定したパーサを返す。
  * `parse_xml(data: bytes) -> etree._Element`: `safe_parser()` を用いて解析する。`etree.XMLSyntaxError` を捕捉して `CorruptedFileError` (E-007) に変換する。**アプリ内の XML 解析はすべてこの関数を通す。**
  * `local_name(el) -> str`: 名前空間を除いたタグ名を返すヘルパ。
  * `iter_text(el, tag: str) -> str`: 指定タグの配下の全テキストを連結するヘルパ。
* **`zip_reader.py`**
  * 定数: `MAX_TOTAL_RATIO = 200`, `MAX_TOTAL_BYTES = 1024**3`, `MAX_ENTRY_BYTES = 512*1024**2`, `MAX_COMPRESS_RATIO = 1000`, `MAX_ENTRIES = 10_000`
  * `class SafeZipReader`: コンテキストマネージャ。`__init__(self, source: Path | bytes, *, source_size: int | None = None)`。バイト列の場合は `io.BytesIO` で開く。
  * 開いた直後に `namelist()` と `infolist()` を検査する:
    * エントリ数が `MAX_ENTRIES` 超 → `FileTooLargeError` (E-008)
    * 各エントリ名が絶対パス / `..` を含む / ドライブレターを含む → `CorruptedFileError` (E-007)
    * 各エントリの `file_size` が `MAX_ENTRY_BYTES` 超 → `FileTooLargeError`
    * `compress_size > 0` かつ `file_size / compress_size > MAX_COMPRESS_RATIO` → `FileTooLargeError`
    * `file_size` の合計が `min(source_size * MAX_TOTAL_RATIO, MAX_TOTAL_BYTES)` 超 → `FileTooLargeError`
  * `read(self, name: str) -> bytes`: エントリを読む。読み出したバイト数が宣言 `file_size` を超えたら `FileTooLargeError`。存在しないエントリは `KeyError` ではなく `CorruptedFileError` にする。
  * `has(self, name: str) -> bool`, `names(self) -> list[str]`
  * `read_xml(self, name: str) -> etree._Element`: `read` + `parse_xml`
  * `resolve_rels(self, part_name: str) -> dict[str, str]`: `{dir}/_rels/{base}.rels` を読み、`Id -> Target` の辞書を返す。Target が相対パスの場合は `part_name` のディレクトリを基準に正規化する。**正規化後のパスが ZIP のルートより上に出る場合は `CorruptedFileError`**。
  * `zipfile.BadZipFile` は `CorruptedFileError` に変換する。
* `SafeZipReader` は `__enter__` / `__exit__` を実装し、`with` で使えるようにする。

### 【実装してはいけないこと】

* ZIP エントリをファイルシステムに展開すること (メモリ上で読むのみ)。
* `lxml.etree.fromstring` を `xml_utils.py` の外で呼ぶこと。
* 閾値をオプションで変更可能にすること (P003 §4.2 の★ACCEPTED★のとおり固定値とする)。

### 【Unit Test内容】

* **テスト対象**: `xml_utils.py`, `zip_reader.py`
* **ファイル**: `app/tests/unit/test_xml_utils.py`, `app/tests/unit/test_zip_reader.py`
* **テストデータ**: `app/tests/helpers/make_malicious.py` に細工ファイルの生成関数を作る (リポジトリに悪意あるファイルを置かない。P006 §3.1)。
* **`test_xml_utils.py` のケース**:
  1. `qn("w:p")` が正しい `{URI}p` を返す。
  2. 正常な XML が解析できる。
  3. **XXE を含む XML (`<!ENTITY xxe SYSTEM "file:///etc/passwd">`) を解析しても、実体が展開されない** (REQ-NF-007)。
  4. **十億の笑い (Billion Laughs) の入れ子実体を含む XML でメモリが爆発しない** (実体が展開されないため。例外になるか、実体が空になること)。
  5. 壊れた XML が `CorruptedFileError` になる (`XMLSyntaxError` が漏れない)。
  6. `local_name` が名前空間を除去する。
* **`test_zip_reader.py` のケース**:
  1. 正常な ZIP からエントリを読める。
  2. **エントリ名に `../` を含む ZIP が `CorruptedFileError`** (REQ-NF-008)。
  3. **エントリ名が絶対パス (`/etc/passwd`) の ZIP が `CorruptedFileError`**。
  4. **圧縮率が 1000 を超えるエントリを含む ZIP が `FileTooLargeError`** (REQ-NF-006)。
  5. **エントリ数が 10,000 を超える ZIP が `FileTooLargeError`**。
  6. ZIP でないバイト列が `CorruptedFileError`。
  7. 存在しないエントリの `read` が `CorruptedFileError` (`KeyError` が漏れない)。
  8. `resolve_rels` が相対 Target を正規化して返す。
  9. **`resolve_rels` の Target が `../../..` でルート外に出る場合に `CorruptedFileError`**。
  10. `with SafeZipReader(...) as z:` で使え、抜けた後にファイルが閉じている。

### 【実行コマンド】

* `pytest tests/unit/test_xml_utils.py tests/unit/test_zip_reader.py -v`

### 【完了条件】

* 上記16ケースすべてが合格する。
* **特にセキュリティのケース (XXE・パストラバーサル・ZIP爆弾) が確実に合格していること。** これらは要求 REQ-NF-006〜008 に直結する。

### 【次タスクに進む前の停止条件】

* セキュリティのケースが3回自己修正しても合格しない場合は停止して報告する (セキュリティ要件のため、未達のまま先に進まない)。

---

## U001-T5: 形式判定と設定読込

### 【目的】

* API-05 (`detect_format`) と API-07 (`load_config`) を実装する。この2つは他の API に依存しないため、U001 で完成させて以降のスプリントのテストで利用できるようにする。

### 【作成・編集対象ファイル】

* `app/src/office2ragknowledge/detect.py`
* `app/src/office2ragknowledge/config.py`

### 【参照すべき仕様箇所】

* `docs/P003-backend-spec.md` §4.3 (形式判定の手順), §8.5 (設定読込の手順)
* `docs/P002-frontend-spec.md` §6.3 API-05, API-07, §4.3 (設定ファイルの項目)
* `docs/P001-requirement.md` REQ-F-001, REQ-F-098

### 【実装内容】

* **`detect.py`**
  * `detect_format(source: Path | str | bytes) -> DocumentFormat | None`
  * 手順は P003 §4.3 のとおり: (1) 先頭4バイトが `PK\x03\x04` か → 違えば `None`、(2) `SafeZipReader` で開く、(3) `[Content_Types].xml` の `Override` を走査、(4) ContentType から形式を決める、(5) 該当なしは `None`。
  * ContentType の対応:
    * `application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml` → `DOCX`
    * `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml` → `XLSX`
    * `application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml` → `PPTX`
    * マクロ有効形式 (`...wordprocessingml.document.macroEnabled.main+xml` 等) も同じ形式として扱う。判定は「`wordprocessingml.document` を含む」のような部分一致で行う。
  * `is_encrypted_ole(source) -> bool`: 先頭8バイトが `\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1` かを判定するヘルパ (パスワード保護の検出。P003 §4.3)。
  * `format_from_extension(name: str) -> DocumentFormat | None`: 拡張子から推定するヘルパ。`.docx/.docm` → DOCX、`.xlsx/.xlsm` → XLSX、`.pptx/.pptm` → PPTX、それ以外は `None`。
  * `LEGACY_EXTENSIONS = {".doc", ".xls", ".ppt"}` を定義する (CLI 層が E-002 の案内に使う)。
* **`config.py`**
  * `load_config(path: Path | str | None = None) -> Config`
  * 手順は P003 §8.5 のとおり。`path` が `None` ならカレントから上位へ `office2rag.toml` を探索する。見つからなければ既定値のみの `Config` を返す。
  * `tomllib.load` を使う。構文エラーは `ConfigError` (E-006)。
  * **既知のテーブルとキーの集合を定数として持ち、未知のキー・未知のテーブルがあれば `ConfigError`**。メッセージに「どのキーが不正か」を含める。
  * 各値の型と範囲を検証する。検証ロジックは **U005 の CLI 層と共有できるよう、`config.py` に検証関数として実装する** (`validate_excel_modes(v) -> ExcelModes` のような形)。範囲は P002 §4.1 のとおり (`max_table_regions` 1〜10000、`max_rows` 0〜1048576、`jobs` 1〜64、`grid_separator` は改行を含まず8文字以内)。
  * 既定値へのマージは `dataclasses.replace` を用いる。

### 【実装してはいけないこと】

* 設定ファイルの自動生成 (存在しなければ既定値を使うだけ)。
* 未知のキーを黙って無視すること (必ず `ConfigError`)。
* `detect_format` の中でパスワード保護の例外を送出すること (`None` を返し、判定は呼び出し元が行う。P003 §4.3)。

### 【Unit Test内容】

* **ファイル**: `app/tests/unit/test_detect.py`, `app/tests/unit/test_config.py`
* **テストデータ**: `app/tests/helpers/make_office.py` に、openpyxl / python-docx / python-pptx で最小の3形式を生成する関数を作る。
* **`test_detect.py` のケース**:
  1. 生成した `.docx` / `.xlsx` / `.pptx` がそれぞれ正しく判定される (3ケース)。
  2. ZIP でないバイト列 (テキストファイル) が `None` になる。
  3. **拡張子を `.xlsx` に偽装した `.docx` が `DOCX` と判定される** (実形式優先。REQ-F-001)。
  4. `format_from_extension(".docm")` が `DOCX` を返す。
  5. `format_from_extension(".doc")` が `None` を返し、`".doc" in LEGACY_EXTENSIONS` が真。
  6. `is_encrypted_ole` が OLE シグネチャのバイト列に対して真を返す。
  7. 空のバイト列で例外にならず `None` を返す。
* **`test_config.py` のケース**:
  1. 設定ファイルが無い場合、既定値の `Config` が返る。
  2. `[convert]` `[excel]` `[log]` の値が読み込まれ、`Config` に反映される。
  3. **未知のキーがあると `ConfigError` になり、メッセージにキー名が含まれる**。
  4. **未知のテーブルがあると `ConfigError`**。
  5. TOML の構文エラーが `ConfigError`。
  6. `excel.modes = "invalid"` が `ConfigError`。
  7. `excel.max_table_regions = 0` が `ConfigError` (範囲外)。
  8. `excel.max_rows = 0` は**受理される** (無制限の意味)。
  9. `excel.grid_separator = "a\nb"` が `ConfigError` (改行を含む)。
  10. `excel.grid_separator = "123456789"` が `ConfigError` (9文字で上限超過)。
  11. `log.jobs` のような誤った階層のキーが `ConfigError`。
  12. 上位ディレクトリの `office2rag.toml` が自動探索される。

### 【実行コマンド】

* `pytest tests/unit/test_detect.py tests/unit/test_config.py -v`

### 【完了条件】

* 上記19ケースすべてが合格する。

### 【次タスクに進む前の停止条件】

* 単体テストが3回自己修正しても合格しない場合は停止して報告する。

---

## U001-T6: 描画基盤

### 【目的】

* すべてのレンダラが用いる、Markdown エスケープと front matter 生成を実装する。

### 【作成・編集対象ファイル】

* `app/src/office2ragknowledge/render/escape.py`
* `app/src/office2ragknowledge/render/frontmatter.py`

### 【参照すべき仕様箇所】

* `docs/P002-frontend-spec.md` §5.1 (エスケープ規則の表), §5.3 (front matter の確定事項と `output_mode` / `stats`)
* `docs/P001-requirement.md` §7.1 (front matter の項目とキー順), REQ-F-007, REQ-F-009, REQ-F-066

### 【実装内容】

* **`escape.py`**
  * `escape_line(text: str) -> str`: **行頭の構造記号のみ**をエスケープする。対象は P002 §5.1 の表のとおり: 行頭の `#`、行頭の `-` `*` `+` (直後が空白のとき)、行頭の `>`、行頭の `数字.` (直後が空白のとき)、行頭の ` ``` `。
  * `escape_cell(text: str) -> str`: テーブルセル用。`|` を `\|` にエスケープし、改行を `<br>` に置換する。
  * **行中の `*` `_` `` ` `` `[` `]` はエスケープしない** (P002 §5.1 の★ACCEPTED★)。
  * `escape_line` は**改行を含む文字列を受け取ったら、各行に対して個別に適用する**。
* **`frontmatter.py`**
  * `render_front_matter(meta: DocumentMeta, mode: OutputMode | None) -> str`
  * キー順は P001 §7.1 の記載順に固定する: `source_file` `source_path` `source_format` `output_mode` `source_size_bytes` `source_sha256` `title` `author` `created_at` `modified_at` `converted_at` `converter` `stats` `warnings`。
  * **値が `None` または空のキーは省略する** (`null` を出力しない)。
  * `output_mode` は `mode` が `None` なら省略する (Word/PowerPoint)。
  * 文字列値はダブルクォートで囲み、内部の `"` と `\` をエスケープする。
  * `stats` はネストしたマッピングとして2スペースインデントで出力する。空なら省略。
  * `warnings` はリストとして `  - "..."` の形で出力する。空なら省略。
  * 日時は ISO 8601 (オフセット付き)。
  * 先頭と末尾に `---` の行を置き、末尾は改行で終える。
  * **YAML ライブラリを使わず、自前で組み立てる** (依存を増やさない。キー順と省略の制御を完全に握るため)。
  * `strip_front_matter(markdown: str) -> str`: 先頭の front matter ブロックを除去して本文を返す (テストの冪等性比較で使う)。

### 【実装してはいけないこと】

* 行中の `*` `_` 等のエスケープ (過剰エスケープの禁止)。
* PyYAML 等の追加依存の導入。
* front matter のキー順をアルファベット順にすること (冪等性のため記載順固定)。

### 【Unit Test内容】

* **ファイル**: `app/tests/unit/test_escape.py`, `app/tests/unit/test_frontmatter.py`
* **`test_escape.py` のケース**:
  1. 行頭の `# 見出し` が `\# 見出し` になる。
  2. 行頭の `- 項目` が `\- 項目` になる。
  3. **行頭の `-abc` (直後が空白でない) は**エスケープ**されない**。
  4. 行頭の `> 引用` が `\> 引用` になる。
  5. 行頭の `1. 項目` が `1\. 項目` になる。
  6. **行中の `a*b*c` はエスケープされない**。
  7. **行中の `snake_case_name` はエスケープされない** (日本語文書での過剰エスケープ防止)。
  8. `escape_cell("a|b")` が `a\|b` になる。
  9. `escape_cell("a\nb")` が `a<br>b` になる。
  10. 複数行の文字列で、2行目の行頭も個別にエスケープされる。
  11. 日本語テキストがそのまま保持される。
* **`test_frontmatter.py` のケース**:
  1. 全項目が埋まった `DocumentMeta` で、キー順が P001 §7.1 のとおりである。
  2. `author` が `None` のとき、`author` キーが**出力されない** (`null` も出ない)。
  3. **`mode=OutputMode.TABLE` のとき `output_mode: "table"` が出力される**。
  4. **`mode=None` のとき `output_mode` キーが出力されない**。
  5. `warnings` が空のとき `warnings` キーが出力されない。
  6. `stats` が2スペースインデントでネスト出力される。
  7. タイトルに `"` を含む場合にエスケープされる。
  8. 日本語のタイトル・作成者が正しく出力される。
  9. 出力が `---\n` で始まり `---\n` で終わる。
  10. `strip_front_matter` が front matter を除去し、本文のみを返す。
  11. front matter を持たない文字列に `strip_front_matter` を適用しても壊れない。

### 【実行コマンド】

* `pytest tests/unit/test_escape.py tests/unit/test_frontmatter.py -v`

### 【完了条件】

* 上記22ケースすべてが合格する。
* **U001 の全タスクが `[x]` になっていること。**
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
* Executor Stepの停止条件(`SKILL.md` 参照。例: 単体テストが3回自己修正しても合格しない)に該当しない限り、次のタスクに自動的に進んでください。1タスクごとに人間の指示を待つ必要はありません。
