# F001 — 設定ファイルの優先順位の修正

| 項目 | 内容 |
| --- | --- |
| 由来 | `docs/P201-review-report.md` §3 失敗1 |
| 対象要求 | **REQ-F-098** (優先順位: コマンドライン引数 > 設定ファイル > 既定値) |
| 重大度 | 高 (要求未達) |
| 失敗テスト | `tests/integration/test_cli_screens.py::test_config_file_and_cli_precedence` |

## 【症状】

設定ファイルに `[excel] modes = "table"` を書き、CLI で `--excel-modes` を指定せずに実行すると、**両モードが出力される**。設定ファイルの値が無視されている。

同じ問題が次のオプションにも存在する:

* 列挙型: `--excel-modes` / `--images` / `--shape-style` / `--on-exists` / `--log-format`
* 真偽値: `--include-hidden` / `--headers-footers` / `--comments` / `--formulas` / `--recursive` / `--front-matter`

## 【原因】

`app/src/office2ragknowledge/cli/options.py` の `build_config` が、**CLI オプションの既定値と、利用者が明示指定した値を区別できていない**。

```python
# 現状 (誤り)
modes = ExcelModes(excel_modes)          # excel_modes は既定 "both"
excel = replace(excel, modes=modes) ...  # 常に実行され、設定ファイルの値を上書きする
```

真偽値についても `include_hidden or base.convert.include_hidden` のような OR 結合になっており、**設定ファイルで `true` にしたものを CLI で `false` に戻せない**という逆向きの問題も併発している。

`docs/P003-backend-spec.md` §8.5 は次のとおり明記していた。

> Typer は「指定されなかったオプション」と「既定値と同じ値が明示された」の区別がつきにくいため、**CLI 層のオプション既定値を `None` とし、`None` でないものだけを設定ファイルの値に上書き適用する**。

実装がこの方針に従っていない。

## 【修正内容】

### 1. `cli/main.py` — CLI オプションの既定値を `None` にする

次のオプションの既定値を `None` に変更し、型を `X | None` にする。

| オプション | 変更前 | 変更後 |
| --- | --- | --- |
| `--excel-modes` | `"both"` | `None` |
| `--images` | `"none"` | `None` |
| `--shape-style` | `"quote"` | `None` |
| `--on-exists` | `"skip"` | `None` |
| `--log-format` | `"text"` | `None` |
| `--include-hidden` | `False` | `None` (フラグ対 `--include-hidden/--no-include-hidden`) |
| `--headers-footers` | `False` | `None` (同上) |
| `--comments` | `False` | `None` (同上) |
| `--formulas` | `False` | `None` (同上) |
| `--recursive` | `False` | `None` (フラグ対にはせず、`-r` 指定時のみ `True`) |
| `--front-matter/--no-front-matter` | `True` | `None` |

`--recursive` は短縮形 `-r` を持つ慣用的なフラグであるため、フラグ対にはせず **`False` を「未指定」と同義に扱う** (設定ファイルで `true` にしたものを CLI で無効化する必要性が低いため)。
★ACCEPTED★ 検討: `-r/--no-recursive` のフラグ対にする案もあったが、`-r` は「再帰する」ことだけを意味する慣用があり、否定形を持つと利用者が混乱する。残存リスク: 設定ファイルで `recursive = true` にした場合、CLI から単発で無効化できない。この場合は `--config` で別の設定ファイルを指すか、設定ファイルを直す。

ヘルプの説明文には引き続き既定値を明記する (`(既定: both)` など)。**利用者から見た既定値は変わらない。**

### 2. `cli/options.py` — `None` でないものだけを上書きする

```python
# 修正後の形
if excel_modes is not None:
    excel = replace(excel, modes=validate_enum(excel_modes, ExcelModes, "--excel-modes"))
```

真偽値も同様に、`None` でないときのみ `replace` する (OR 結合をやめる)。

### 3. 既定値の出どころを1箇所にする

`load_config` が返す `Config` が既定値を持っているため、**CLI 層は既定値を持たない**。この関係を `build_config` の docstring に明記する。

## 【実装してはいけないこと】

* 失敗しているテストの期待値を変えること。
* `--excel-modes` の**ヘルプ表示上の既定値**を消すこと (利用者から見た既定は `both` のまま)。
* 検証の順序を変えること (P002 §4.1 の (1)〜(5))。

## 【追加するテスト】

`tests/unit/test_cli_options.py` に次を追加する。

1. **設定ファイルで指定した `excel.modes` が、CLI 未指定時に反映される**
2. 設定ファイルで指定した `convert.images` / `shape_style` / `on_exists` が反映される
3. **設定ファイルで `true` にした真偽値を、CLI の否定フラグで `false` に戻せる**
4. CLI で明示指定した値が設定ファイルより優先される (既存テストの維持)
5. 設定ファイルも CLI も未指定なら既定値になる (既存テストの維持)

## 【完了条件】

* `test_config_file_and_cli_precedence` が合格する。
* 上記の追加テストが合格する。
* 既存の `test_cli_options.py` / `test_cli_main.py` が引き続き全件合格する。
* `ruff check` / `mypy src` がエラー0件。
