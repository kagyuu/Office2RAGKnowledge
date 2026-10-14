あなたはExecutor(実装担当)です。以下は1スプリント分の作業範囲と完了条件を定義したものです。実施後は、そのタスクの完了条件を満たしたことを確認したうえで、Executor Stepの「停止条件」(`SKILL.md` 参照)に該当しない限り、自動的に次のタスクへ進んでください。人間の指示を待って停止しないでください。

# 【スプリントID】U008 — pdf-backend-mit ※CR-003により追加

> PDF 読み取りライブラリを PyMuPDF (AGPL-3.0) から **pdfminer.six (MIT)** に差し替える。**外部仕様は変えない。** U006・U007 の PDF のテストが差し替え後もそのまま合格することを受け入れの基準とする。PDF ライブラリを import してよいのは引き続き `pdf/backend.py` だけである。

## タスク一覧(OKF副目次)

- [x] U008-T1 [依存と図形のまとめ](#u008-t1-依存と図形のまとめ) — pyproject / drawings.py
- [x] U008-T2 [バックエンドの書き直し](#u008-t2-バックエンドの書き直し) — backend.py (pdfminer.six)
- [x] U008-T3 [構造木の順序と後片付け](#u008-t3-構造木の順序と後片付け) — kid_index / structure.py / content.py の削除 / Dockerfile

---

## U008-T1: 依存と図形のまとめ

### 【作成・編集対象ファイル】

* `app/pyproject.toml` (`pymupdf` を外し `pdfminer.six>=20260107`。mypy の上書き設定から `pymupdf.*`・`fitz.*` を外す)
* `app/src/office2ragknowledge/pdf/drawings.py` (新規)

### 【参照すべき仕様箇所】

* `docs/P003-backend-spec.md` §1.5, §7A.2 (pdfminer.six からの変換手順 5)

### 【実装内容】

* `cluster_rects(rects: Sequence[Rect], tolerance: float = 2.0) -> list[Rect]`: 重なる、または `tolerance` 以内に近接する矩形を推移的にまとめ、それぞれの外接矩形を返す。結果は (top, x0, ...) の順に並べる (決定性)。矩形が多い場合に備え、x0 で並べてから掃き出す方式とする。

### 【Unit Test内容】

* **ファイル**: `app/tests/unit/test_pdf_drawings.py`
  1. 重なる2矩形が1つにまとまる。2. 2pt 以内の近接もまとまる。3. 離れた矩形はまとまらない。4. A-B-C の連鎖 (A と C は離れている) が1つにまとまる。5. 空の入力。6. 同じ入力で同じ結果 (順序を入れ替えた入力でも同じ)。

---

## U008-T2: バックエンドの書き直し

### 【作成・編集対象ファイル】

* `app/src/office2ragknowledge/pdf/backend.py`
* `app/tests/unit/test_pdf_backend.py` (MuPDF 固有の期待のみ改める)

### 【参照すべき仕様箇所】

* `docs/P003-backend-spec.md` §1.5, §4.4, §7A.2, §12A

### 【実装内容】

* `open_pdf(data) -> PdfSource` を P003 §4.4 の手順1〜6・§7A.2 の変換手順1〜5で実装する。公開する名前 (`open_pdf`・`library_version`・`parse_pdf_date`) と戻り値の型は変えない。
* `library_version()` は `pdfminer.six {版}` を返す。
* ログと警告: 読み込み時に `logging.getLogger("pdfminer")` へ `NullHandler` を付け `propagate = False`。変換処理は `warnings.catch_warnings()` + `simplefilter("ignore")` の中で行う。
* pdfminer.six の型注釈は境界であるこのモジュールで `Any` として扱ってよい (PyMuPDF 採用時と同じ方針)。

### 【実装してはいけないこと】

* `pdf/backend.py` 以外での `pdfminer` の import。
* 外部仕様 (出力・警告文・エラーコード) の変更。

### 【Unit Test内容】

* 既存の `test_pdf_backend.py` を、次の点だけ改めて全件合格させる。
  1. `test_mcr_form_yields_no_paths` → **MCR 形式でも文字に経路が付く**ことを確認するテストに改める。
  2. `test_library_version` → `pdfminer.six ` で始まる。
  3. MuPDF の標準エラー出力を確かめていたテストは、ライブラリによらず「標準エラー・標準出力に何も出ない」ことの確認として残す。
* 追加: 構造の後の Artifact (`test_trailing_artifact_is_not_in_structure`) が、内容ストリームの補正なしに合格すること。

---

## U008-T3: 構造木の順序と後片付け

### 【作成・編集対象ファイル】

* `app/src/office2ragknowledge/pdf/model.py` (`PdfChar.kid_index: int | None = None`)
* `app/src/office2ragknowledge/pdf/structure.py` (`/K` の順序による並べ直し。P003 §7A.3)
* 削除: `app/src/office2ragknowledge/pdf/content.py`、`app/tests/unit/test_pdf_content.py`
* `app/tests/unit/test_pdf_parser.py` (MCR 形式の期待の変更と、被覆率不足の別データでの確認)
* `deploy/Dockerfile` (ラベル `licenses` = `MIT`、PyMuPDF の注記を削除)
* `app/README.md` (ライセンスの注記)

### 【Unit Test内容】

* `test_pdf_structure.py` に追加: 描画順と構造ツリーの順序が異なる PDF で、ノードの `items` が `/K` の順に並ぶ。要素内の MCID と子要素が `/K` の順に並ぶ。`kid_index` が無い文字のノードは並べ直さない。
* `test_pdf_parser.py`: `test_mcr_form_falls_back_with_warning` を、**MCR 形式がタグ付きとして見出しになる**テストと、**構造が本文の一部しか覆わない PDF がタグなし + 警告になる**テストの2つに分ける。

---

## 実施記録 (P102)

* 全タスク完了。単体テストは PDF 関連 119 → 125 件 (U008 で追加: 図形のまとめ 7 件・`kid_index`・Form XObject・(cid) の置き換え・`/K` の順序 3 件・被覆率不足の切り替え。削除: `test_pdf_content.py`)。全スイート 699 件合格 (2回連続)。
* **判明した事項1 (Handbook §4-18)**: `PDFPageAggregator` の派生クラスでマーク付きコンテンツの入れ子を `_stack` という名前で持つと、基底クラスが Form XObject の入れ子に使う `_stack` を上書きしてしまう。mypy strict が型の不一致として検出した。`_marked` に改め、Form XObject の中の文字を確かめるテストを加えた。
* **判明した事項2**: テスト用ヘルパ `make_pdf.py` は、複数ページにまたがる要素で整数の MCID と要素の `/Pg` (最後のページ) を使っており、PDF 仕様に反していた (整数の MCID は要素の `/Pg` のページを指す)。MuPDF は許容していたが pdfminer.six は仕様どおりに解釈する。ヘルパを、最初の MCID のページを `/Pg` とし、別ページの MCID を MCR 辞書で書く形に直した (テストの期待は変えていない)。
