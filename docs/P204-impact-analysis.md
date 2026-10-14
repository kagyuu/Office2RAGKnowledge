# P204 影響分析結果 — Office2RAGKnowledge

| 項目 | 内容 |
| --- | --- |
| 版 | 1.0 |
| 実施日 | 2026-08-24 |
| インプット | `docs/P202-fix-plan/F001〜F003`、P203 の修正結果 |
| 目的 | P203 の修正が他機能を壊していないかを確認する |

---

## 1. 結論

**他機能を壊していない。P205 (結合テスト再実施) へ進む。**

修正後の全テスト: **539件合格 / 0件失敗**。P203 の修正前 (528合格 / 2失敗) と比べ、**失敗が2件解消し、新規の失敗は無い**。

---

## 2. F001 (設定ファイルの優先順位) の影響範囲

### 2.1 変更した箇所

| ファイル | 変更内容 |
| --- | --- |
| `cli/main.py` | 10個のオプションの既定値を `None` に変更。真偽値5個をフラグ対 (`--x/--no-x`) 化 |
| `cli/options.py` | `build_config` を「`None` でないものだけ上書き」に書き換え。`_enum_or_fail` ヘルパを追加 |

### 2.2 波及しうる箇所と確認結果

| # | 波及先 | 懸念 | 確認結果 |
| --- | --- | --- | --- |
| 1 | **利用者から見た既定の挙動** | 既定値を `None` にしたことで、オプション未指定時の動作が変わらないか | **変わっていない。** 既定値は `load_config` が返す `Config` が持ち、`ConvertOptions()` / `BatchOptions()` の既定と一致する。`test_defaults` が引き続き合格 |
| 2 | **ヘルプ表示** | 既定値の表示が消えていないか | **消えていない。** ヘルプ文言に `(既定: both)` 等を明記したまま。`test_help` / `test_version_and_help` が合格 |
| 3 | **真偽値のフラグ対化** | `--formulas` などが `--formulas/--no-formulas` になり、既存の指定方法が壊れないか | **壊れていない。** `--formulas` 単独の指定は従来どおり有効。否定形が追加されただけ。`test_grid_with_formulas_warns` が合格 |
| 4 | `-r` (再帰) | フラグ対にしなかったため、設定ファイルの `recursive = true` を CLI で無効化できない | **意図した設計** (F001 の★ACCEPTED★)。`-r` 未指定時は設定ファイルの値を尊重する。`test_recursive` / `test_recursive_without_directory_warns` が合格 |
| 5 | 検証順序 (P002 §4.1 の (1)〜(5)) | 順序が変わっていないか | **変わっていない。** `test_validation_order` が合格 (値不正が段階1で先に報告される) |
| 6 | エラーコード | E-013 等の割り当てが変わっていないか | **変わっていない。** `test_invalid_enum_values` が5種すべてで E-013 を確認 |
| 7 | `--stdout` の事前検証 | Excel モード条件 (E-017) の判定が `cfg.convert.excel.modes` を見ているため、優先順位の変更に影響されるか | **正しく機能している。** 設定ファイルで `modes = "table"` にした場合、`--stdout` が通るようになった (仕様どおり)。`test_stdout_excel_requires_single_mode` / `test_stdout_with_excel_single_mode_works` が合格 |
| 8 | ログ設定 | `--log-format` の既定値変更でログ形式が変わらないか | **変わっていない。** `test_config_log_format` で設定ファイル・CLI の双方を確認 |
| 9 | ライブラリ利用 (`convert_file` 等) | CLI 層の変更がライブラリ API に波及するか | **波及しない。** `cli/` は上位層であり、`convert.py` / `batch.py` は変更していない |

### 2.3 修正で新たに可能になったこと (退行ではない)

* 設定ファイルの `[excel] modes` / `[convert] images` / `shape_style` / `on_exists` / `[log] format` が**実際に効くようになった**。
* 設定ファイルで `true` にした真偽値を、CLI の否定フラグで `false` に戻せるようになった。

---

## 3. F002 (スキップ件数の欠落) の影響範囲

### 3.1 変更した箇所

| ファイル | 変更内容 |
| --- | --- |
| `cli/options.py` | `resolve_targets` の戻り値を `list[Path]` → `tuple[list[Path], list[tuple[Path, str]]]` に変更 |
| `batch.py` | `convert_batch` に `pre_skipped` 引数を追加 (既定 `()`) |
| `cli/main.py` | `resolve_targets` の戻り値の受け取りと、`convert_batch` への引き継ぎ |

### 3.2 波及しうる箇所と確認結果

| # | 波及先 | 懸念 | 確認結果 |
| --- | --- | --- | --- |
| 1 | **`convert_batch` の既存の呼び出し側** | 引数追加で既存コードが壊れないか | **壊れない。** `pre_skipped` は既定値 `()` を持つ位置引数の最後。既存の `convert_batch(paths, options)` / `convert_batch(paths, options, on_progress)` はそのまま動く。`test_pre_skipped_default_keeps_behaviour` で確認 |
| 2 | **公開 API の契約** | `convert_batch` は API-03 として公開されている。シグネチャ変更は破壊的か | **後方互換である。** 既定値付きの追加であり、既存の呼び出しは影響を受けない。P002 §6.3 の API-03 の契約 (戻り値 `BatchResult`) は不変 |
| 3 | `resolve_targets` の呼び出し側 | 戻り値がタプルになったことで呼び出し側が壊れないか | **`cli/main.py` の2箇所と単体テスト2箇所を追随済み。** `resolve_targets` は `cli/options.py` の内部関数であり、公開 API ではない (`__all__` には含まれるが、`office2ragknowledge` パッケージの公開面には出していない) |
| 4 | `inspect` サブコマンド | `resolve_targets` を使っている | **追随済み** (`targets, _ = resolve_targets(...)`)。`test_inspect_columns` / `test_inspect_json_excel_vs_word` が合格 |
| 5 | スキップの重複計上 | `pre_skipped` と `convert_batch` 自身の `scan_inputs` の結果が二重に計上されないか | **二重にならない。** CLI から渡される `targets` は既に対応形式のみであるため、`convert_batch` 内の `scan_inputs` はスキップを1件も返さない。`test_exit_codes` で `スキップ 1 件` を確認 |
| 6 | 終了コード | スキップが計上されるようになったことで終了コードが変わらないか | **変わっていない。** スキップは失敗ではないため `exit_code` は 0 のまま。`test_exit_codes` / `test_all_success_exit_zero` が合格 |
| 7 | 探索が2回行われること | 性能への影響 | **無視できる。** ディレクトリ走査のみで変換を伴わない。性能テスト (A004) の実測値に変化なし |

---

## 4. F003 (設計書の追随) の影響範囲

**アプリケーションコードを変更していない**ため、動作への影響は無い。

| 更新した文書 | 内容 |
| --- | --- |
| `docs/P002-frontend-spec.md` §7.3.1 | `Document` の型定義表に `images` を追加 |
| `docs/P002-frontend-spec.md` §7.2 | ER 図に `EXTRACTED_IMAGE` を追加 |
| `docs/P003-backend-spec.md` §2.2 | モジュールツリーに `models/media.py` を追加 |
| `docs/ArchitectureHandbook.md` §3 | 中間表現の表に `Document.images` を追加 |

**確認**: `docs/P002-frontend-spec.md` §7.3.1 の `Document` のフィールド一覧と、`app/src/office2ragknowledge/models/document.py` の実装が一致することを確認した (`format` / `title` / `meta` / `blocks` / `warnings` / `images` の6フィールド)。

---

## 5. 静的検査と全体テストの結果

| 検査 | 修正前 (P201) | 修正後 (P203) |
| --- | --- | --- |
| `pytest` | 528合格 / **2失敗** | **539合格 / 0失敗** |
| `ruff check` | エラー0件 | **エラー0件** |
| `ruff format --check` | 整形済み | **整形済み** |
| `mypy src` (strict) | エラー0件 | **エラー0件** |

テスト件数が 528 → 539 に増えたのは、F001/F002 の回帰テストを **11件追加**したためである (設定ファイルの優先順位6件、`resolve_targets` のスキップ1件、`pre_skipped` の引き継ぎ2件、ほか2件)。

---

## 6. 他機能を壊していないことの根拠

| 中核機能 | 確認 |
| --- | --- |
| **要求A: オートシェープの文字抽出** | A001 の16ケースが引き続き全件合格。CLI 層の変更は抽出器に触れていない |
| **要求B: Excel の二重出力** | T001 の17ケース・A001 の該当ケースが引き続き全件合格 |
| **要求①: 表領域の分割** | `test_excel_regions.py` の17ケースが引き続き全件合格 |
| **要求②: 数式キャッシュ値** | `test_excel_formula.py` の11ケースが引き続き全件合格 |
| 冪等性 | A004 の冪等性6ケースが引き続き全件合格 |
| セキュリティ | `test_zip_reader.py` / `test_xml_utils.py` が引き続き全件合格 |
| 再実行 (O-01/O-02) | A003 の11ケースが引き続き全件合格 |

**P202 への差し戻しは不要。** P205 (結合テスト再実施) へ進む。


---

## ※CR-001・CR-002 の修正 F004〜F006 の影響分析 (2026-10-14)

| ID | 変更したもの | 他機能への影響 | 確認方法 |
| --- | --- | --- | --- |
| F004 | テスト指示 T006 の期待16、`test_pdf_conversion.py` の判定1箇所 | **なし。** アプリケーションコードを変更していない。失敗一覧の表示 (`cli/console.py`) は既存の T004・T005 が前提とする表示のまま | 全スイートの合格 |
| F005 | `test_pdf_acceptance.py` の参照パス2箇所 | **なし。** テストコードのみ | 同上 |
| F006 | テストコード3ファイルの整形・行の分割 | **なし。** 判定内容は変えていない (分割した式は同じ値を比較する) | 同上 + 静的検査 |

**結論**: 修正はすべてテスト指示・テストコードに限られ、他機能を壊していない。P205 へ進む。
