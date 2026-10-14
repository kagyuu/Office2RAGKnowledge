# PDF ライブラリの代替検討 — PyMuPDF (AGPL-3.0) を MIT 互換に置き換えられるか

| 項目 | 内容 |
| --- | --- |
| 作成日 | 2026-10-14 |
| 依頼 | 「いったん PyMuPDF での実装を最後までやってください。そのあと、Docling または PDF Inspector での代替が可能か検討してください。ライセンスを MIT に保つためです。」(依頼者、2026-10-14) |
| 関連 | ADR-012 (PyMuPDF の採用。暫定)、`docs/P302-deliver.md` 10.1章① (SPEC-PDF-LICENSE)、CR-001・CR-002 |
| **その後** | **CR-003 (2026-10-14) で推奨どおり pdfminer.six に差し替えた** (ADR-015。`docs/P903-cr-records/CR-003.md`)。PDF 50ページの変換は 1.18〜2.07 秒 (§5 の見込みどおり目標内) |
| 方法 | 各候補を隔離した venv に導入し、**本アプリのテストと同じサンプル PDF** (`app/tests/helpers/pdf_samples.py`: タグ付き報告書・タグなし2段組み (ヘッダー/フッター付き)・スキャンページ・暗号化・破損) で実際に動かした。WSL2 / Python 3.12 |

## 1. 結論

| 候補 | ライセンス | 代替できるか | 一言 |
| --- | --- | --- | --- |
| **Docling** 2.138.0 | MIT (本体・docling-parse・docling-ibm-models)。OCR の rapidocr は Apache-2.0。レイアウトモデルの重みのライセンスは未確認 | **できない** | タグ付き PDF の論理構造を使わず、機械学習で版面を推定する別方式。CR-001・CR-002 の要求の多くを満たさず、オフライン・配布・性能の非機能要求にも反する |
| **PDF Inspector** (firecrawl/pdf-inspector) 1.25.2 | MIT | **単独ではできない** (部品としては一部使える) | 文字列の座標・フォント・**MCID**・暗号化の判定は取れる。しかし構造ツリーの**階層・代替テキスト・属性**と、**ベクター図形**が取れない |
| (参考) **pdfminer.six** 20260107 | MIT | **できる** | 着手時のスパイク (P003 §1.4 #10) で、必要な情報をすべて取れることを確認済み。PyMuPDF より遅いが目標の範囲内 |

**推奨**: MIT を保つなら、`pdf/backend.py` を **pdfminer.six** で書き直す (他のモジュールと既存のテストはそのまま使える。ADR-012 の閉じ込めの効果)。PDF Inspector は、将来の高速化の部品として併用を検討する余地がある。Docling は採らない。**実施するかどうかは依頼者の判断事項であり、実施する場合は新しい CR (CR-003) として起票する。**

## 2. 本アプリが PDF ライブラリに求めるもの

`pdf/backend.py` は、次の情報を `PdfSource` (`pdf/model.py`) にして返す。差し替え先はこれを満たす必要がある。

| # | 必要な情報 | 使う要求 |
| --- | --- | --- |
| R1 | 文字ごとの座標・文字サイズ (行片・段組み・ヘッダー/フッター帯の判定) | REQ-F-116, 122〜126 |
| R2 | 文字が属する構造要素 (MCID) と、Artifact か否か | REQ-F-111, 115, 123 |
| R3 | 構造ツリーの**階層** (`/K` の順序・入れ子)。入れ子のリスト・表の行と列・`Sect` の深さに要る | REQ-F-112〜115 |
| R4 | 構造要素の属性: `/Alt`、`ListNumbering`、`ColSpan`/`RowSpan`、RoleMap | REQ-F-113, 114, 118 |
| R5 | ベクター図形 (矩形・線・曲線) の位置。タグなし PDF の図領域 | REQ-F-117 |
| R6 | 暗号化 (開くパスワード) の判定、権限 (コピー禁止) | REQ-F-121 |
| R7 | 圧縮ストリームの生データ (展開サイズ検査) | REQ-NF-020 |
| R8 | メタデータ (タイトル・作成者・日時) | REQ-F-120 |
| R9 | オフライン・外部バイナリ不要・pip で導入できる | REQ-NF-010, 019 |

## 3. Docling の評価

**方式**: PDF のタグを使わず、機械学習のレイアウトモデル (docling-layout-heron) と表構造モデルで、ページ画像から版面を推定する。既定で OCR (RapidOCR) も動く。

| 観点 | 結果 (実測) |
| --- | --- |
| タグ付き報告書 | **見出しのレベルがすべて `##` になった** (H1/H2/H3 の区別が消えた)。**3段の入れ子リストと表が `<!-- formula-not-decoded -->` (数式と誤認) になり、内容が失われた**。図中の文字は出た。代替テキストは出なかった |
| タグなし2段組み | ヘッダー・フッターは除かれた。**左右の段が2列の Markdown 表として出力された** (段を順に読む REQ-F-125 と異なる) |
| スキャンページ | 画像として扱われた (`<!-- image -->`)。既定では OCR が動く (本アプリの「OCR しない」方針と異なる。設定で止められる) |
| 導入の大きさ | venv 1.4 GB (torch・transformers・rapidocr・pypdfium2 を含む) |
| ネットワーク | **初回の変換時に HuggingFace と ModelScope からモデル (約 500 MB) をダウンロードした** (REQ-NF-010 オフライン動作に反する。事前配置は可能だが配布物が大きくなる) |
| 速度 | 3ページで 3.6 秒 (CPU)。50ページなら 1 分前後の見込み (REQ-NF-001 の 10 秒を超える)。現状は 50ページ 0.35〜0.58 秒 |
| ライセンス | 本体は MIT。rapidocr は Apache-2.0。モデルの重み (`docling-project/docling-layout-heron`・`docling-models`) のライセンスは本検討では確認していない |

**判定**: R3・R4 (構造の利用) を満たさず、R9 にも反する。CR-001 の期待する振る舞い #3〜#5 (見出し・リスト・表) を満たせない。**代替にならない。**

## 4. PDF Inspector の評価

**方式**: Rust 製の PDF パーサ (Python バインディング)。ルールベースで Markdown を生成する。OCR は任意 (既定で無効)。

| 観点 | 結果 (実測) |
| --- | --- |
| R1 文字座標 | △ `extract_text_with_positions` は**文字列の描画単位** (概ね `Tj` 1回分) の座標・幅・フォントサイズを返す。文字単位ではない (行片の分割は描画単位の幅から近似が要る) |
| R2 MCID・Artifact | ○ 各テキストに `mcid` が付く。Artifact の文字は `mcid=None` になり、**構造の後に現れる Artifact も正しく区別された** (PyMuPDF で必要だった補正 (Handbook §4-13) が不要) |
| R3 構造の階層 | × `extract_structure_elements` は (ページ, MCID, 最も内側のタグ) の**平らな一覧**のみ。親子関係が無く、入れ子のリスト・表の行・`Sect` の深さが復元できない |
| R4 属性 | × `/Alt`・`ListNumbering`・`ColSpan` を返す API が無い |
| R5 ベクター図形 | × 図形の位置を返す API が無い (表の検出に内部で使っているのみ) |
| R6 暗号化 | ○ 開くパスワードありは `ValueError("PDF is encrypted")`。所有者パスワードのみの PDF は読める。コピー禁止の判定 API は無い |
| R7 生ストリーム | × 取り出す API が無い (展開サイズ検査は別の手段が要る) |
| R8 メタデータ | ○ タイトル・作成者・日時 |
| R9 | ○ wheel 1つ (外部バイナリ不要。OCR を使う場合のみ PDFium・ONNX Runtime が要る) |
| 自身の Markdown 変換 | 参考: 2段組みの左右の行が交互になり、ヘッダーが残り、入れ子リストが1行になった。**本アプリの出力の代わりには使えない** (使うのは部品としての API のみ) |
| 備考 | 小さな PDF を `image_based` と分類した (分類の判定は本アプリでは使わない) |

**判定**: R3・R4・R5・R7 が欠けるため、**単独では代替にならない**。欠ける部分を別の MIT/BSD のライブラリ (pdfminer.six や pypdf) で補うなら、R1〜R8 をすべて満たす pdfminer.six を単独で使うほうが単純である。

## 5. pdfminer.six (参考。MIT)

P003 §1.4 #10 のスパイクと本検討の計測による。

| 観点 | 結果 |
| --- | --- |
| R1・R2 | ○ デバイスで `BDC`/`EMC` を受け取り、文字ごとに MCID と Artifact を判別できる (構造の後の Artifact も正しく区別) |
| R3・R4 | ○ 構造ツリーは PDF オブジェクトとして辿れる (MCR 辞書形式も可。**PyMuPDF では取れなかった形式**。Handbook §4-8) |
| R5 | ○ `LTRect`・`LTLine`・`LTCurve` |
| R6・R7・R8 | ○ `PDFPasswordIncorrect`、`is_extractable`、ストリームの生データ、文書情報辞書。注意: `/P` = 0 の暗号化 PDF で `struct.error` (Handbook §4-12。例外として E-007 に変換すればよい) |
| R9 | ○ 純 Python (依存の `cryptography` は wheel)。外部バイナリ不要 |
| 速度 | 50ページの文字抽出 0.37 秒 (PyMuPDF 0.04 秒)。変換全体でも目標 10 秒に対し十分な余裕の見込み |

## 6. 差し替える場合の作業量の見積り (CR-003 として起票する場合)

* 変更: `app/src/office2ragknowledge/pdf/backend.py` の書き直し (現状 約480行)。`pdf/content.py` (Artifact の補正) は不要になる見込み。`pyproject.toml` の依存 (`pymupdf` → `pdfminer.six`)、`cli/console.py` の版表示、Dockerfile のラベル。
* そのまま使えるもの: `pdf/model.py`・`text.py`・`structure.py`・`layout.py`・`parsers/pdf.py`、および PDF のテスト 153 件 (backend の単体テストの一部は、MuPDF 固有の挙動を固定したケース (MCR 形式が構造を返さない等) の期待を変える必要がある)。
* 設計書: ADR-012 の置き換え (新 ADR)、P001 §8.3、P003 §1.4・§4.4・§7A.2、Handbook §4-8〜4-14・§9-13。
* 留意: PyMuPDF の `cluster_drawings` 相当 (近い図形のまとめ) は自前で実装する必要がある。

## 7. 参照した情報源

* [firecrawl/pdf-inspector (GitHub)](https://github.com/firecrawl/pdf-inspector)
* [Is Firecrawl pdf-inspector Open Source? (instagit)](https://instagit.com/firecrawl/pdf-inspector/is-firecrawl-pdf-inspector-open-source/)
* [docling-project/docling (GitHub)](https://github.com/docling-project/docling)
* 各パッケージのメタデータ (`License` / `License-Expression`): pdf-inspector MIT、docling・docling-parse・docling-ibm-models MIT、rapidocr Apache-2.0、pdfminer.six MIT、PyMuPDF「Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License」
