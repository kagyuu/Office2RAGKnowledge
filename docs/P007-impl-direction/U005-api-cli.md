あなたはExecutor(実装担当)です。以下は1スプリント分の作業範囲と完了条件を定義したものです。実施後は、そのタスクの完了条件を満たしたことを確認したうえで、Executor Stepの「停止条件」(`SKILL.md` 参照)に該当しない限り、自動的に次のタスクへ進んでください。人間の指示を待って停止しないでください。

# 【スプリントID】U005 — api-cli

> このスプリントで**全7画面 (SCR-01〜07) と残り5つの公開API が出そろう**。ここまでのスプリントで作った部品を組み立てる。

## タスク一覧(OKF副目次)

- [x] U005-T1 [変換APIと書き出し](#u005-t1-変換apiと書き出し) — convert_file / convert_bytes / write_result
- [x] U005-T2 [バッチと構造確認](#u005-t2-バッチと構造確認) — convert_batch / inspect_file / 並列実行
- [x] U005-T3 [ログ基盤](#u005-t3-ログ基盤) — 出力先・形式・レベル・本文の非出力
- [x] U005-T4 [CLIのオプションと検証](#u005-t4-cliのオプションと検証) — V-01〜V-52 / SCR-06
- [x] U005-T5 [CLIの画面と公開面](#u005-t5-cliの画面と公開面) — SCR-01〜05,07 / __init__ の公開シンボル

---

## U005-T1: 変換APIと書き出し

### 【目的】

* API-01 (`convert_file`)、API-02 (`convert_bytes`)、API-06 (`write_result`) を実装する。

### 【作成・編集対象ファイル】

* `app/src/office2ragknowledge/convert.py`
* `app/src/office2ragknowledge/writer.py`

### 【参照すべき仕様箇所】

* `docs/P003-backend-spec.md` §8.1 (convert のフローチャート), §8.4 (write_result の手順1〜5)
* `docs/P002-frontend-spec.md` §6.3 API-01/02/06, §5.2 (出力ファイル名と on_exists の個別判定), §5.11 (画像)
* `docs/P001-requirement.md` REQ-F-004, REQ-F-005, REQ-F-065, REQ-F-069, REQ-F-100〜102

### 【実装内容】

* **`convert.py`**
  * `_convert_source(reader, filename, source_size, sha256, options, converted_at) -> ConversionResult` に共通処理を集約する。
  * 手順 (P003 §8.1): `detect_format` → `None` なら、OLE シグネチャなら `PasswordProtectedError` (E-005)、旧形式の拡張子なら `UnsupportedFormatError` (E-002)、それ以外も `UnsupportedFormatError`。
  * 形式に応じてパーサを呼び `Document` を得る → `render_document` で `MarkdownOutput` を1〜2件得る → `ConversionResult` を構築する。
  * `convert_file(path, options)`: ファイルを読み、SHA-256 を計算し、`SafeZipReader` を開いて `_convert_source` を呼ぶ。
  * `convert_bytes(data, filename, options)`: バイト列から同様。`FileNotFoundError` / `PermissionError` を送出しない。
  * **副作用を持たない** (ファイルを書かない)。
  * `converted_at` はこの層で `datetime.now().astimezone()` を1回だけ取得してパーサに渡す (規約11)。
  * 拡張子と実形式が食い違う場合、警告 `拡張子は {拡張子} ですが、実際の形式は {形式} です。実形式として変換しました` を `ConversionResult.warnings` に追加する。
* **`writer.py`**
  * `write_result(result, out_dir, on_exists=SKIP, images=NONE) -> WrittenFiles`
  * `result.outputs` の各要素について出力パス `{out_dir}/{ステム}{suffix}` を決める。ステムは `result.source_path.stem`。
  * **出力ファイルごとに個別に `on_exists` を判定する** (P002 §5.2)。`SKIP` かつ既存 → `skipped_paths` に入れて飛ばす。`FAIL` かつ既存 → `OutputError` (E-004)。`OVERWRITE` → 上書き。
  * **一時ファイル (`{目的名}.tmp{PID}`) に書いてから `os.replace` で置換する** (P003 §8.4)。中断時に壊れた Markdown を残さないため。
  * 書き込みは `encoding="utf-8"`, `newline="\n"` を明示する。
  * **画像は `outputs` のループの外で1回だけ書き出す** (REQ-F-069)。`images=EXTRACT` かつ `result.images` が非空のとき、`{out_dir}/{ステム}_assets/` を作り `{連番:04d}.{拡張子}` で保存する。画像も `on_exists` に従う。
  * 出力先ディレクトリが無ければ作成する。作成・書き込みに失敗したら `OutputError` (E-004)。

### 【実装してはいけないこと】

* `convert_file` からのファイル書き出し (書き出しは `write_result` の責務)。
* 出力ファイルの既存判定を「1つでも既存ならすべてスキップ」とすること (個別判定。P002 §5.2)。
* 画像を出力ごとに重複して書き出すこと (REQ-F-069)。
* 一時ファイルを経ずに目的名へ直接書くこと。

### 【Unit Test内容】

* **ファイル**: `app/tests/unit/test_convert.py`, `app/tests/unit/test_writer.py`
* **`test_convert.py` のケース**:
  1. `.docx` / `.xlsx` / `.pptx` がそれぞれ変換でき、`ConversionResult.format` が正しい。
  2. **Excel + `modes=BOTH` で `outputs` が2件**。
  3. Word で `outputs` が1件、`ConversionResult.markdown` が使える。
  4. **Excel + `BOTH` で `ConversionResult.markdown` が `ValueError`** (P002 §6.4)。
  5. 非対応形式 (`.txt` の中身) で `UnsupportedFormatError` (code が `E-002`)。
  6. OLE シグネチャのファイルで `PasswordProtectedError` (`E-005`)。
  7. 壊れた ZIP で `CorruptedFileError` (`E-007`)。
  8. **`convert_file` がファイルを書き出さない** (出力先を指定していないので当然だが、`tmp_path` に新しいファイルが増えないことを確認)。
  9. `convert_bytes` が同じ結果を返す (同じ内容のファイルとバイト列で `outputs` の本文が一致)。
  10. `source_sha256` が実際のハッシュと一致する。
  11. 拡張子偽装で警告が入る。
  12. **同じ入力を2回変換して、`converted_at` を除き本文が完全一致する** (REQ-NF-018)。
* **`test_writer.py` のケース**:
  1. Word で1ファイルが書かれる (`{ステム}.md`)。
  2. **Excel で2ファイルが書かれる (`{ステム}.table.md` と `{ステム}.grid.md`)**。
  3. `on_exists=SKIP` で既存ファイルがスキップされ、`skipped_paths` に入る。
  4. **Excel で `.table.md` のみ既存のとき、table はスキップされ grid は書かれる** (個別判定。P002 §5.2)。
  5. `on_exists=OVERWRITE` で上書きされる。
  6. `on_exists=FAIL` で既存があると `OutputError`。
  7. 出力先ディレクトリが無ければ作成される。
  8. 書き出したファイルが UTF-8 (BOM なし)・LF 改行である。
  9. **`images=EXTRACT` で `_assets/` に画像が1回だけ書かれる** (Excel の2出力でも重複しない)。
  10. `images=NONE` で `_assets/` が作られない。
  11. 一時ファイルが残っていない。
  12. `WrittenFiles.markdown_paths` が実際に書いたパスと一致する。

### 【実行コマンド】

* `pytest tests/unit/test_convert.py tests/unit/test_writer.py -v`

### 【完了条件】

* 上記24ケースすべてが合格する。

### 【次タスクに進む前の停止条件】

* 単体テストが3回自己修正しても合格しない場合は停止して報告する。

---

## U005-T2: バッチと構造確認

### 【目的】

* API-03 (`convert_batch`)、API-04 (`inspect_file`) を実装する。並列実行を含む。

### 【作成・編集対象ファイル】

* `app/src/office2ragknowledge/batch.py`
* `app/src/office2ragknowledge/inspection.py`

### 【参照すべき仕様箇所】

* `docs/P003-backend-spec.md` §8.2 (バッチの段階1〜6と探索順序の決定性), §8.3 (inspect の項目表), §10 (並列実行の決定表と Windows spawn 対応), §11 (冪等性)
* `docs/P002-frontend-spec.md` §6.3 API-03/04, §6.4 BatchResult/DocumentInfo
* `docs/P001-requirement.md` REQ-F-002, REQ-F-006, REQ-F-091, REQ-F-094, REQ-NF-015, REQ-NF-018

### 【実装内容】

* **`batch.py`**
  * `convert_batch(paths, options, on_progress=None) -> BatchResult`
  * 段階1 (探索): 各パスがファイルなら対象に、ディレクトリなら配下を走査。`recursive` が偽なら直下のみ。**対応拡張子のみを対象とし、それ以外はスキップに計上する**。
  * 段階2 (重複排除): 解決済み絶対パスで重複を除き、**最初に出現した順を保つ**。
  * **探索結果はパス文字列でソートする** (REQ-NF-018。P003 §8.2)。
  * 段階3: 出力先の決定。`output_dir` が `None` なら各入力ファイルと同じ階層。
  * 段階4 (事前検証): 出力先の作成と書き込み可否を確認。失敗すれば `OutputError` を送出し**1件も処理しない**。
  * 段階5 (並列変換): `jobs == 1` なら**プールを作らず逐次実行**。2以上なら `ProcessPoolExecutor`。
    * **`_worker_convert(args) -> _WorkerResult` をモジュールのトップレベル関数として定義する** (Windows の spawn で pickle 可能にするため。P003 §10)。
    * ワーカーに渡すのは入力パス (文字列)・`ConvertOptions`・出力先・`on_exists`・`images`。**`Document` や `ConversionResult` を返さない** (pickle コストのため)。成功時は書き出したパスと警告、失敗時はコード・メッセージ・パスを返す。
    * ワーカー内で例外を捕捉し `_WorkerResult` に変換する (例外オブジェクトを pickle させない)。
    * `as_completed` で受け取り、`on_progress(完了数, 全数, ファイル名)` を呼ぶ。**進捗は入力ファイル単位**で数える (REQ-F-094)。
  * 段階6 (集計): **結果を入力パスの順に並べ替えてから** `BatchResult` を構築する (REQ-NF-018。P003 §10)。
  * `written_files` に全出力ファイルを入れる (入力数と一致しない。REQ-F-094)。
* **`inspection.py`**
  * `inspect_file(path) -> DocumentInfo`
  * **`convert_file` と同じパーサを使う** (別実装を持たない。P003 §8.3)。
  * 非対応形式・破損・パスワード保護は**例外にせず** `status` に格納する (`ok`/`unsupported`/`protected`/`corrupted`)。`FileNotFoundError` / `PermissionError` のみ送出する。
  * `unit_count` / `unit_label`: Excel=シート数/`シート`、PowerPoint=スライド数/`スライド`、Word=段落数/`段落`。
  * `table_count`: Excel は表領域の総数、他は `Table` ブロックの数。
  * `shape_count` / `shape_with_text_count`: 図形の総数と、テキストを持つものの数。
  * `table_region_count` / `formula_without_cache_count`: **Excel のみ。他形式では `None`**。
  * `estimated_chars`: **実際に表計算モード (Excel) または通常モードでレンダリングして `len()` を取る** (推定式を使わない。P003 §8.3)。

### 【実装してはいけないこと】

* ワーカー関数をローカル関数・ラムダで定義すること (Windows の spawn で pickle できない)。
* `as_completed` の順序をそのまま `BatchResult` に入れること (冪等性が壊れる)。
* `inspect_file` で例外を送出すること (`FileNotFoundError` / `PermissionError` を除く)。
* `estimated_chars` を推定式で求めること。

### 【Unit Test内容】

* **ファイル**: `app/tests/unit/test_batch.py`, `app/tests/unit/test_inspection.py`
* **`test_batch.py` のケース**:
  1. 複数ファイルの変換で `succeeded` が全件になる。
  2. ディレクトリ入力で直下のファイルが対象になる。
  3. `recursive=True` で配下が再帰的に対象になる。
  4. `recursive=False` でサブディレクトリが対象にならない。
  5. **対応しない拡張子が `skipped` に計上される**。
  6. **1件が失敗しても他が処理される** (REQ-F-006)。`failures` に入り `exit_code` が 1。
  7. **`written_files` の件数が入力件数と異なる (Excel を含む場合)** (REQ-F-094)。
  8. `on_progress` が入力件数だけ呼ばれる (Excel の2出力で2回呼ばれない)。
  9. **`jobs=1` と `jobs=2` で `BatchResult.succeeded` の順序が一致する** (REQ-NF-018)。
  10. **同じディレクトリを2回処理して、`succeeded` の順序が一致する** (探索順の決定性)。
  11. 出力先が書き込み不可のとき `OutputError` が送出され、1件も処理されない。
  12. 重複したパスを渡しても1回だけ処理される。
  13. **`jobs=2` で実際に並列実行され、結果が正しい** (Windows の spawn 対応の確認)。
* **`test_inspection.py` のケース**:
  1. Excel で `unit_label` が `シート`、`unit_count` がシート数。
  2. PowerPoint で `スライド`、Word で `段落`。
  3. **Excel で `table_region_count` が表領域の総数になる**。
  4. **Excel で `formula_without_cache_count` がキャッシュ値なしの数式セル数になる**。
  5. **Word / PowerPoint で `table_region_count` と `formula_without_cache_count` が `None`**。
  6. `shape_with_text_count` がテキストを持つ図形の数、`shape_count` が総数 (テキストなしを含む)。
  7. 非対応形式で `status="unsupported"`、例外にならない。
  8. 壊れたファイルで `status="corrupted"`、例外にならない。
  9. 存在しないパスで `FileNotFoundError`。
  10. `estimated_chars` が実際のレンダリング結果の長さと一致する。

### 【実行コマンド】

* `pytest tests/unit/test_batch.py tests/unit/test_inspection.py -v`

### 【完了条件】

* 上記23ケースすべてが合格する。
* **ケース13 (`jobs=2` の並列実行) が合格していること。** P005 §7 R5 のリスク対象。

### 【次タスクに進む前の停止条件】

* 並列実行のテストが3回自己修正しても合格しない場合は停止して報告する。**ただし、実行環境の制約 (プロセス生成が許可されない等) が原因と最小再現で切り分けられた場合は、アプリケーションの欠陥として扱わず `docs/ArchitectureHandbook.md` の既知の制約に記録し、`jobs=1` で先に進む** (`SKILL.md` 共通指示)。

---

## U005-T3: ログ基盤

### 【目的】

* ログの出力先・形式・レベルを実装する (REQ-NF-013, REQ-NF-014, REQ-F-095)。

### 【作成・編集対象ファイル】

* `app/src/office2ragknowledge/logging_setup.py`

### 【参照すべき仕様箇所】

* `docs/P003-backend-spec.md` §12A (全体。特に §12A.3 の出力可否の区分表)
* `docs/P001-requirement.md` REQ-NF-013, REQ-NF-014, REQ-F-095

### 【実装内容】

* `setup_logging(level: str, fmt: str, log_file: Path | None) -> None` を実装する。**この関数は CLI 層からのみ呼ぶ。**
* ロガーは `logging.getLogger("office2ragknowledge")` を使う。**ルートロガーを設定しない** (ライブラリ利用者の設定を壊さないため)。
* ライブラリ側の `__init__.py` で `logging.getLogger("office2ragknowledge").addHandler(logging.NullHandler())` を行う。
* ハンドラ: 標準エラー出力へ。`log_file` があればファイルハンドラも追加する (`encoding="utf-8"`)。
* レベル対応 (P003 §12A.2): `quiet`→`WARNING`、`info`→`INFO`、`verbose`→`DEBUG`。
* フォーマッタ:
  * `text`: `{時刻} {レベル} {メッセージ}`
  * `json`: 1行1レコードの JSON。フィールドは `ts` `level` `event` `path` `code` `detail` (P003 §12A.4)。`event` 等は `logger.info("...", extra={"event": "...", ...})` で渡す。存在しないフィールドは省略する。
* **本文テキストをログに渡さないこと** (REQ-NF-014)。ログ出力箇所では、ファイルパス・件数・シート名・エラーコードのみを使う。
* 主なイベント識別子: `convert.start` `convert.done` `convert.failed` `sheet.truncated` `formula.no_cache` `region.abandoned` `shape.unanchored` `batch.start` `batch.done`。

### 【実装してはいけないこと】

* ルートロガーへのハンドラ追加。
* ライブラリ側のモジュール (`parsers/` `render/` `ooxml/`) でのハンドラ設定。
* セル値・段落テキスト・図形テキスト・`title`・`author` のログ出力 (REQ-NF-014)。

### 【Unit Test内容】

* **ファイル**: `app/tests/unit/test_logging.py`
* **ケース**:
  1. `setup_logging("info", "text", None)` でロガーにハンドラが付く。
  2. **ルートロガーにハンドラが追加されていない**。
  3. `quiet` で `WARNING` 未満が出力されない。
  4. `verbose` で `DEBUG` が出力される。
  5. `log_file` を指定するとファイルにも出力される。
  6. `json` 形式で1行1レコードの JSON が出力され、`ts` `level` `event` を含む。
  7. `extra` で渡さなかったフィールドが JSON に含まれない。
  8. **ログ出力が標準エラー側で、標準出力に混ざらない** (REQ-NF-013)。
  9. 日本語のメッセージが化けずに出力される。
  10. `setup_logging` を2回呼んでもハンドラが重複しない。

### 【実行コマンド】

* `pytest tests/unit/test_logging.py -v`

### 【完了条件】

* 上記10ケースすべてが合格する。

### 【次タスクに進む前の停止条件】

* 単体テストが3回自己修正しても合格しない場合は停止して報告する。

---

## U005-T4: CLIのオプションと検証

### 【目的】

* 全オプションの定義と検証 (V-01〜V-52) を実装し、SCR-06 (エラー画面) を成立させる。

### 【作成・編集対象ファイル】

* `app/src/office2ragknowledge/cli/options.py`

### 【参照すべき仕様箇所】

* `docs/P002-frontend-spec.md` §4 (検証一覧 V-01〜V-52 と検証順序), §9.1 (エラーコード表), §9.2 (終了コード)
* `docs/P003-backend-spec.md` §8.5 (CLI 引数と設定ファイルのマージ)
* `docs/P001-requirement.md` REQ-F-093, REQ-F-097, REQ-F-098, REQ-F-099

### 【実装内容】

* Typer のオプション定義を関数として持つ。**CLI 層のオプション既定値はすべて `None` とし、`None` でないものだけを設定ファイルの値に上書きする** (P003 §8.5)。
* 検証関数 `validate_and_build(...) -> tuple[Config, list[Path]]` を実装する。**検証順序は P002 §4.1 のとおり**: (1) 型・列挙値・範囲 → (2) 排他指定 → (3) パスの存在・権限 → (4) 入力探索と対象件数 → (5) `--stdout` の件数条件と Excel モード条件。**先に検出した違反で終了する** (まとめて報告しない)。
* 検証項目は P002 §4.1.1〜§4.1.4 と §4.2 の全項目。特に:
  * **V-09**: `--stdout` は対象がちょうど1件のときのみ (E-014)。
  * **V-10**: `--stdout` かつ対象が Excel かつ `--excel-modes both` は E-017。
  * **V-21**: `--grid-separator` は改行を含まず8文字以内 (E-018)。
  * **V-23**: `--max-table-regions` は 1〜10000 (E-019)。
  * **V-25**: `--max-rows` は 0〜1048576 (E-015)。0 は無制限。
  * **V-40**: `--jobs` は 1〜64 (E-016)。CPU コア数の4倍超は受理して警告。
  * **V-24**: `--excel-modes grid` かつ `--formulas` は**エラーにせず警告**。
  * **V-07**: `-r` を指定したがディレクトリ入力が無い場合は警告のみ。
* 検証違反は `Office2RagError` のサブクラスを送出する。CLI 層がこれを捕捉して SCR-06 を描画し、終了コード 2 を返す。
* 検証で使う範囲チェックは、**`config.py` の検証関数を再利用する** (U001-T5 で実装済み。二重実装しない)。

### 【実装してはいけないこと】

* 複数の違反をまとめて報告すること (P002 §4.1 の★ACCEPTED★)。
* 形式に意味を持たないオプション (PowerPoint に `--formulas` 等) をエラーにすること (無視する)。
* 検証を変換処理の途中で行うこと (すべて開始前)。

### 【Unit Test内容】

* **ファイル**: `app/tests/unit/test_cli_options.py`
* **ケース**:
  1. 既定値が P002 §4.1 のとおりになる。
  2. 入力パス未指定で E-010。
  3. 存在しないパスで E-001。
  4. 対象0件で E-011。
  5. `--output` と `--stdout` の併用で E-012。
  6. `--stdout` で対象2件以上のとき E-014。
  7. **`--stdout` + Excel + `--excel-modes both` で E-017**。
  8. **`--stdout` + Excel + `--excel-modes table` は通る**。
  9. `--excel-modes invalid` で E-013。
  10. `--grid-separator` に改行を含むと E-018。
  11. `--grid-separator` が9文字で E-018。
  12. `--max-table-regions 0` で E-019、`1` と `10000` は通る。
  13. `--max-rows 0` は通る (無制限)、`-1` で E-015。
  14. `--jobs 0` で E-016、`65` で E-016、`1` と `64` は通る。
  15. `-q` と `-v` の併用で E-012。
  16. **`--excel-modes grid` + `--formulas` が警告になりエラーにならない**。
  17. `-r` を指定してディレクトリ入力が無い場合に警告のみで通る。
  18. **CLI 引数が設定ファイルの値より優先される** (REQ-F-098)。
  19. 設定ファイルの値が既定値より優先される。
  20. **検証順序が仕様どおり** (パス不存在と値不正の両方があるとき、値不正 (段階1) が先に報告される)。

### 【実行コマンド】

* `pytest tests/unit/test_cli_options.py -v`

### 【完了条件】

* 上記20ケースすべてが合格する。

### 【次タスクに進む前の停止条件】

* 単体テストが3回自己修正しても合格しない場合は停止して報告する。

---

## U005-T5: CLIの画面と公開面

### 【目的】

* SCR-01〜05, 07 を実装し、公開シンボルを確定する。**このタスクで全7画面が完成する。**

### 【作成・編集対象ファイル】

* `app/src/office2ragknowledge/cli/main.py`
* `app/src/office2ragknowledge/cli/console.py`
* `app/src/office2ragknowledge/__init__.py`

### 【参照すべき仕様箇所】

* `docs/P002-frontend-spec.md` §2 (コマンド体系), §3.1〜§3.7 (全画面のレイアウトと表示項目), §6.1 (公開シンボル), §9.2 (終了コード)
* `docs/P003-backend-spec.md` §12B (標準出力のエンコーディング)
* `docs/P001-requirement.md` REQ-F-090〜097, REQ-F-100, REQ-F-103

### 【実装内容】

* **`cli/main.py`**: Typer アプリ。`convert` と `inspect` のサブコマンド、`--version` / `--help`。
  * **`if __name__ == "__main__":` の保護下にエントリポイントを置く** (Windows の spawn で再帰起動しないため。P003 §10)。
  * サブコマンド省略時はヘルプを表示して終了コード 2。
  * `Office2RagError` を捕捉して SCR-06 を描画し、終了コード 2 (実行前異常) を返す。
  * `--verbose` 時のみスタックトレースを表示する (REQ-NF-005)。
  * **標準出力・標準エラーを UTF-8 に再設定する** (`sys.stdout.reconfigure(encoding="utf-8", newline="\n")`。P003 §12B)。Windows の cp932 対策。
* **`cli/console.py`**: Rich による描画。
  * **SCR-03** (進捗): 標準エラーへ。TTY なら進捗バー、非TTY なら1行ログ。`--quiet` で抑止。
  * **SCR-04** (サマリ): 標準出力へ。`変換結果: 成功 N 件 / スキップ N 件 / 失敗 N 件 (所要 N.N 秒)` + **`出力ファイル: N 件`** の行 + 出力先 + 失敗一覧 (表) + 警告一覧。`--quiet` でも1行目のみ出す。
  * **SCR-05** (構造確認): 表形式。**Excel のみ `領域` と `数式` 列に値を入れ、他形式は `-`**。`--json` で `DocumentInfo` を JSON 配列にして標準出力へ。
  * **SCR-07** (標準出力モード): Markdown 本文のみを標準出力へ。進捗とサマリは標準エラーへ退避。
  * **SCR-06** (エラー): 標準エラーへ。`エラー: {種別}` / `パス: ...` / `対処: {hint}`。`ERROR_CATALOG` を参照する。
  * **SCR-01/02**: Typer の自動生成 + バージョン情報 (アプリ版・Python版・依存ライブラリ版)。
  * Excel 関連オプションを独立したヘルプパネルにまとめる (P002 §3.1)。`rich_help_panel="Excel オプション"` を用いる。
* **終了コード** (P002 §9.2): 全件成功/スキップ → 0、ファイル失敗が1件以上 → 1、実行前異常 → 2。
* **`__init__.py`**: P002 §6.1 の公開シンボルを `__all__` に列挙して再輸出する。`__version__ = "1.0.0"`。`NullHandler` の設定。

### 【実装してはいけないこと】

* 標準出力への進捗・ログの出力 (REQ-NF-013: 標準出力は変換結果とサマリのみ)。
* `--stdout` 時に標準出力へ Markdown 以外を出すこと。
* スタックトレースの既定表示 (REQ-NF-005)。

### 【Unit Test内容】

* **ファイル**: `app/tests/unit/test_cli_main.py`
* **方法**: Typer の `CliRunner` を用いる。
* **ケース**:
  1. `--version` でバージョンが表示され、終了コード 0。
  2. `--help` でヘルプが表示され、終了コード 0。
  3. サブコマンドなしでヘルプが出て終了コード 2。
  4. `convert` で正常終了し終了コード 0。
  5. **1件失敗すると終了コード 1**。
  6. 引数不正で終了コード 2。
  7. **サマリに `出力ファイル: N 件` の行が含まれる** (REQ-F-094)。
  8. **Excel を含むバッチで、成功件数 (入力単位) と出力ファイル数が異なる**。
  9. 失敗があるとき失敗一覧が表示され、エラー種別と理由を含む。
  10. 警告があるとき警告一覧が表示される。
  11. `--quiet` でサマリの1行目のみ出る。
  12. **`--stdout` で標準出力が Markdown のみになる** (進捗・サマリが混ざらない)。
  13. `inspect` で表が表示され、終了コード 0。
  14. **`inspect` の Excel 行に `領域` と `数式` の値が入り、Word 行は `-`**。
  15. `inspect --json` が妥当な JSON を返す。
  16. **エラー時にスタックトレースが表示されない**。
  17. **`--verbose` でスタックトレースが表示される**。
  18. 日本語のファイル名・メッセージが化けない。
  19. `office2ragknowledge` から P002 §6.1 の全シンボルが import できる。
  20. `__all__` に列挙されたシンボルがすべて実在する。

### 【実行コマンド】

* `pytest tests/unit/test_cli_main.py -v`
* スプリント全体: `pytest tests/unit -v`
* CLI の実動作: `python -m office2ragknowledge.cli.main --version` および `office2rag --version`

### 【完了条件】

* 上記20ケースすべてが合格する。
* **U005 の全タスクが `[x]` になっていること。**
* **`pytest tests/unit` が全件合格** (U001〜U005 のすべて)。
* `ruff check src tests` と `mypy src` がエラー0件。
* **`office2rag --version` が実際に実行でき、バージョンが表示される** (エントリポイントが機能していること)。
* `docs/P007-impl-direction.md` の5行すべてが `[x]` になっていること。

### 【次タスクに進む前の停止条件】

* 単体テストが3回自己修正しても合格しない場合は停止して報告する。

---

## 重要

* 各タスクの範囲外のファイルは編集しないでください。
* タスクの実装後、実行したテストコマンドと結果を報告してください。
* タスクが完了したら、上記「タスク一覧」の該当行を `[x]` に更新してください。
* 全タスクが完了したら、`docs/P007-impl-direction.md` の本スプリント行を `[x]` に更新してください。
* Executor Stepの停止条件に該当しない限り、次のタスクに自動的に進んでください。
