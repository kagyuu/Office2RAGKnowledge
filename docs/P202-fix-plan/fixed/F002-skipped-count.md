# F002 — スキップ件数の欠落の修正

| 項目 | 内容 |
| --- | --- |
| 由来 | `docs/P201-review-report.md` §3 失敗2 |
| 対象要求 | **REQ-F-094** (結果サマリにスキップ件数を表示する)、P002 §9.3 |
| 重大度 | 中 |
| 失敗テスト | `tests/integration/test_cli_screens.py::test_exit_codes` |

## 【症状】

`.doc` や `.txt` を含むディレクトリを変換したとき、サマリのスキップ件数が **0** と表示される。実際には対象外のファイルが存在する。

終了コード自体は 0 で正しい (ディレクトリ探索で見つかった非対応形式は「スキップ」であり失敗ではない。P002 §9.3)。

## 【原因】

CLI が2段階で探索している。

1. `cli/main.py` が `resolve_targets()` を呼び、**対応形式のファイルだけ**の一覧を得る
2. その一覧を `convert_batch(targets, ...)` に渡す
3. `convert_batch` は受け取った一覧に対して**再度 `scan_inputs` を実行**する

3の時点で一覧には非対応ファイルが含まれていないため、**スキップ情報が失われる**。

`resolve_targets` は `scan_inputs` の戻り値のうちスキップ側を捨てている:

```python
targets, _ = scan_inputs(inputs, recursive=recursive)   # スキップを捨てている
```

## 【修正内容】

### 1. `cli/options.py` — `resolve_targets` がスキップも返す

戻り値を `list[Path]` から `tuple[list[Path], list[tuple[Path, str]]]` に変える。

```python
def resolve_targets(...) -> tuple[list[Path], list[tuple[Path, str]]]:
    ...
    targets, skipped = scan_inputs(inputs, recursive=recursive)
    ...
    return targets, skipped
```

### 2. `batch.py` — 事前に判明しているスキップを受け取れるようにする

`convert_batch` に `pre_skipped: Sequence[tuple[Path, str]] = ()` を追加し、`BatchResult.skipped` に合流させる。

**`convert_batch` を単独で (CLI を介さず) 呼んだ場合の挙動は変えない。** 引数を省略すれば従来どおり自前の `scan_inputs` の結果だけを使う。

### 3. `cli/main.py` — 探索結果を引き継ぐ

`resolve_targets` が返したスキップを `convert_batch` に渡す。

## 【なぜ探索を1回にまとめないか】

「CLI 側の探索をやめ、`convert_batch` にディレクトリをそのまま渡す」案も検討した。**採用しない。**

理由: P002 §4.1 の検証順序 (5) が「`--stdout` の件数条件と Excel モード条件」を**変換開始前に**判定することを求めており、そのためには CLI 層で対象件数を確定する必要がある。探索を `convert_batch` に一本化すると、この事前検証ができなくなる。

★ACCEPTED★ 検討: 探索を1回にする案は、`--stdout` の事前検証 (E-014 / E-017) を「変換開始後に対象が2件と判明した」形に変えることになり、P002 §4.1 の「違反があれば1件も変換せずに終了する」に反する。探索を2回行うコストは、ディレクトリ走査のみで変換を伴わないため小さい。残存リスク: 探索結果を2箇所で持つため、片方だけ変更すると不整合が生じうる。`scan_inputs` を唯一の実装とし、両者がこれを呼ぶ形を保つことで防ぐ。

## 【実装してはいけないこと】

* 失敗しているテストの期待値を変えること。
* 非対応形式を「失敗」に分類すること (P002 §9.3 では「スキップ」)。
* `convert_batch` の既存の呼び出し側 (テスト・ライブラリ利用) を壊す変更。

## 【追加するテスト】

`tests/unit/test_batch.py` に次を追加する。

1. `convert_batch` に `pre_skipped` を渡すと `BatchResult.skipped` に合流する
2. `pre_skipped` を渡さない場合の挙動が変わらない (既存テストの維持)

`tests/unit/test_cli_options.py` に次を追加する。

3. `resolve_targets` が対象とスキップの両方を返す

## 【完了条件】

* `test_exit_codes` が合格し、`スキップ 1 件` が表示される。
* 上記の追加テストが合格する。
* 既存の `test_batch.py` が引き続き全件合格する。
