あなたはExecutor(実装担当)です。以下は1スプリント分の作業範囲と完了条件を定義したものです。実施後は、そのタスクの完了条件を満たしたことを確認したうえで、Executor Stepの「停止条件」(`SKILL.md` 参照)に該当しない限り、自動的に次のタスクへ進んでください。人間の指示を待って停止しないでください。

# 【スプリントID】U003 — shape-text

> **このスプリントは本アプリの中核その2である。** 利用者が最初に挙げた要求 (オートシェープから文字を抜き出して Markdown に追記する) がここにある。3形式で共有するため、誤りは3形式すべてに波及する。
> **P003 §1.3 のスパイクで、素朴な走査が同じテキストを2回拾うことが実測されている。** U003-T1 のケース4は必ず実装すること。

## タスク一覧(OKF副目次)

- [x] U003-T1 [図形テキスト抽出器](#u003-t1-図形テキスト抽出器) — 3形式共有・mc:Choice優先・グループ再帰
- [x] U003-T2 [SmartArtとグラフ](#u003-t2-smartartとグラフ) — データモデル採用・階層復元・グラフのラベル抽出
- [x] U003-T3 [図形ブロックの描画](#u003-t3-図形ブロックの描画) — 3体裁・図形内の表の外出し
- [x] U003-T4 [Excelへの組み込み](#u003-t4-excelへの組み込み) — drawing の解決とアンカーセル参照

---

## U003-T1: 図形テキスト抽出器

### 【目的】

* Word / Excel / PowerPoint で共有する図形テキスト抽出器を実装する (REQ-F-031〜033, 039, 040)。

### 【作成・編集対象ファイル】

* `app/src/office2ragknowledge/ooxml/shapes.py`

### 【参照すべき仕様箇所】

* `docs/P003-backend-spec.md` §1.3 (**スパイクの実測結果。二重取得の再現と対処**), §6.1 (方言表), §6.2 (走査の全体手順), §6.3 (`mc:AlternateContent` の規則1〜4)
* `docs/P002-frontend-spec.md` §5.8 (図形種別の日本語名対応表), §7.3.2 (ShapeText のフィールド)
* `docs/P001-requirement.md` REQ-F-031〜033, REQ-F-039, REQ-F-040

### 【実装内容】

* **方言オブジェクト** `@dataclass(frozen=True) class ShapeDialect` を定義し、P003 §6.1 の表の項目を保持する: `shape_tag` `group_tag` `text_body_tag` `paragraph_tag` `text_tag` `name_attr_path`。
  * `WORD_DIALECT`: `wps:wsp` / `wpg:wgp` / `w:txbxContent` / `w:p` / `w:t`
  * `EXCEL_DIALECT`: `xdr:sp` / `xdr:grpSp` / `xdr:txBody` / `a:p` / `a:t`
  * `PPTX_DIALECT`: `p:sp` / `p:grpSp` / `p:txBody` / `a:p` / `a:t`
* **`class ShapeTextExtractor`**: `__init__(self, dialect: ShapeDialect)`。
* **`extract(self, root, *, group_path=()) -> tuple[list[ShapeText], int]`** — (抽出した ShapeText のリスト, 走査した図形の総数) を返す。**図形の総数はテキストの有無によらず数える** (P003 §8.3: `inspect` の `shape_count` に必要。INV-05 によりテキストなしは ShapeText を作らないため、別途カウンタが要る)。
* **走査の規則** (P003 §6.2, §6.3):
  1. **`mc:AlternateContent` に遭遇したら、その配下を直接走査しない。** `mc:Choice` が1つ以上あれば**最初の `mc:Choice` のみ**を辿る。`mc:Choice` が無い場合に限り `mc:Fallback` を辿る。
     * `mc:Choice` が複数ある場合は、`Requires` 属性が `wps` または `wpg` のものを優先し、無ければ最初のものを採る。
     * この選択は再帰の各階層で行う (入れ子の `AlternateContent` にも適用)。
  2. グループ要素に遭遇したら、`group_path` にグループ名を積んで再帰する (REQ-F-033)。**入れ子の深さに制限を設けない。** ただし無限再帰を防ぐため、深さ 50 を超えたら打ち切って警告を残す。
  3. 図形要素に遭遇したら、その配下の `text_body_tag` を探し、段落ごとに `ShapeParagraph` を作る。
  4. その他の要素は子へ再帰する。
* **段落の構築**: `paragraph_tag` の各要素について、配下の `text_tag` のテキストを連結して1つの `ShapeParagraph` にする (REQ-F-040: 段落の区切りを保つ)。空段落は含めない。
  * 箇条書きの階層 (`a:pPr/@lvl`) があれば `ShapeParagraph.level` に入れる。無ければ 0。
* **図形内の表** (REQ-F-039): 図形配下に `a:tbl` (DrawingML の表) があれば、`Table` に変換して `ShapeText.tables` に入れる。行は `a:tr`、セルは `a:tc`、セル内テキストは `a:t` の連結。
* **INV-05 の担保**: `paragraphs` と `tables` の両方が空なら `ShapeText` を作らない。
* **図形種別の判定** (P002 §5.8): 関数 `classify_shape(el, dialect) -> str` を実装する。
  * `prstGeom` の `prst` 属性を見て、P002 §5.8 の表に従い日本語名を返す。
  * `rect` / `roundRect` / `snip*Rect` / `round*Rect` → `四角形`、`ellipse` → `円・楕円`、`triangle`/`rtTriangle` → `三角形`、`prst` に `Arrow` を含む → `矢印`、`Callout` を含む → `吹き出し`、テキストボックス属性 (`txBox="1"` または `wps:wsp` でテキストボックス) → `テキストボックス`、いずれでもない → `図形`。
  * コネクタ要素 (`p:cxnSp` 等) → `線・コネクタ`。
* **図形名**: `cNvPr` の `name` 属性を `ShapeText.shape_name` に入れる。無ければ `None`。
* **`anchor`**: この抽出器では常に `None` とする。アンカーの解決は形式ごとに異なるため、呼び出し元 (U003-T4 の Excel、U004 の Word) が `dataclasses.replace` で設定する。

### 【実装してはいけないこと】

* **`.//{text_body_tag}` のような素朴な全件検索。** `mc:Choice` / `mc:Fallback` の両方を拾い、すべての図形テキストが2回出力される (P003 §1.3 で実測済み)。必ず階層を辿る再帰で実装すること。
* SmartArt・グラフの処理 (U003-T2)。
* Markdown の生成 (U003-T3)。
* テキストを持たない図形に対する `ShapeText` の生成 (INV-05)。

### 【Unit Test内容】

* **ファイル**: `app/tests/unit/test_shapes.py`
* **テストデータ**: **XML 文字列を直接与える** (P006 §3.1)。ファイルを作らない。`docs/P003-backend-spec.md` §1.3 の再現 XML をそのまま使う。
* **ケース (P006 §7.1 の網羅表に対応)**:
  1. 単独の図形 (テキストあり) から `ShapeText` が1件、`paragraphs` にテキストが入る。
  2. **テキストを持たない図形から `ShapeText` が作られない** (INV-05)。ただし図形の総数には数えられる。
  3. **グループ図形 (2階層) の内部のテキストが抽出され、`group_path` に外側からのグループ名が入る** (REQ-F-033)。
  4. **`mc:Choice` と `mc:Fallback` に同じ内容を持つ XML で、`ShapeText` が1件だけ返る** (P003 §1.3 の実測。**このケースは必須**)。
  5. `mc:Choice` が無く `mc:Fallback` のみの XML で、`mc:Fallback` から抽出される。
  6. `mc:Choice` が複数あり、`Requires="wps"` のものが優先される。
  7. **図形内の複数段落が、段落ごとに分かれて `paragraphs` に入る** (REQ-F-040)。連結されて1段落にならないこと。
  8. **図形内の表が `ShapeText.tables` に入る** (REQ-F-039)。行数・列数・セル値が正しい。
  9. `classify_shape` が主要なプリセットを正しく分類する (`rect`→四角形、`ellipse`→円・楕円、`rightArrow`→矢印、`wedgeRectCallout`→吹き出し、未知の `prst`→図形)。
  10. 図形名が `shape_name` に入る。無い場合は `None`。
  11. 3方言 (Word/Excel/PowerPoint) それぞれの XML で抽出できる。
  12. 入れ子の深さ50を超えるグループで無限再帰にならず、打ち切られる。
  13. 空段落 (テキストのない `a:p`) が `paragraphs` に含まれない。
  14. `anchor` が常に `None` である。

### 【実行コマンド】

* `pytest tests/unit/test_shapes.py -v`

### 【完了条件】

* 上記14ケースすべてが合格する。
* **ケース4 (二重取得の回避) が合格していること。** これが失敗すると、利用者の最重要要求である図形テキストがすべて2回出力される。

### 【次タスクに進む前の停止条件】

* ケース4が3回自己修正しても合格しない場合は停止し、`docs/.stop-report.md` に記録して報告する。

---

## U003-T2: SmartArtとグラフ

### 【目的】

* SmartArt (REQ-F-034) とグラフ (REQ-F-047) のテキストを抽出する。

### 【作成・編集対象ファイル】

* `app/src/office2ragknowledge/ooxml/smartart.py`
* `app/src/office2ragknowledge/ooxml/charts.py`

### 【参照すべき仕様箇所】

* `docs/P003-backend-spec.md` §6.4 (SmartArt の手順1〜6と★FIXME★), §6.6 (グラフの抽出対象表)
* `docs/P002-frontend-spec.md` §5.7 (SmartArt の出力形), §5.10 (グラフの出力例)
* `docs/P001-requirement.md` REQ-F-034, REQ-F-047

### 【実装内容】

* **`smartart.py`**: `extract_smartart(reader: SafeZipReader, part_name: str, rel_id: str) -> ShapeText | None`
  * `dgm:relIds` の `r:dm` 属性から**データモデルパート** (`diagrams/dataN.xml`) を `resolve_rels` で解決する。
  * **`diagrams/drawingN.xml` は読まない** (重複防止。P003 §6.4)。
  * `dgm:ptLst/dgm:pt` のうち `type` 属性が `node` のもの (または `type` が無いもの) を走査する。**`type="pres"` は表示専用のため除外する。**
  * `dgm:cxnLst/dgm:cxn` のうち `type="parOf"` から親子関係を組み立て、各ノードの深さを算出する。
  * 各ノードの `dgm:t` 配下の `a:t` を連結し、`ShapeParagraph(runs, level=深さ)` を作る。
  * **階層が組み立てられない場合は、すべて `level=0` のフラットな並びに落とす** (P003 §6.4 の★FIXME★)。例外を送出しないこと。
  * ノードの順序は、`dgm:ptLst` の出現順を保つ (冪等性)。
  * `shape_kind` は `SmartArt`。
* **`charts.py`**: `extract_chart(reader: SafeZipReader, part_name: str, rel_id: str) -> ShapeText | None`
  * `c:chart` を参照するグラフィックフレームから、関係 ID でチャートパートを解決する。
  * **タイトル**: `c:chart/c:title` 配下の `a:t` を連結。
  * **系列名**: 各 `c:ser/c:tx/c:strRef/c:strCache/c:pt/c:v` のテキスト。
  * **カテゴリ名**: **最初の** `c:ser/c:cat` 配下の `c:strCache/c:pt/c:v` (系列間で共通のため1つ目のみ)。
  * **数値データ (`c:val`) は読まない** (REQ-F-047)。
  * 出力する `paragraphs` は P002 §5.10 の例に合わせる: 1段落目=タイトル、2段落目=`系列: A, B`、3段落目=`カテゴリ: Q1, Q2`。系列・カテゴリが空なら該当段落を出さない。
  * `shape_kind` は `グラフ`。
  * タイトルも系列もカテゴリも空なら `None` を返す (INV-05)。

### 【実装してはいけないこと】

* `diagrams/drawing*.xml` の走査 (重複の原因)。
* グラフの数値データ (`c:val`) の抽出 (REQ-F-047 の範囲外)。
* 階層が取れない場合に例外を送出すること (フラットに落とす)。

### 【Unit Test内容】

* **ファイル**: `app/tests/unit/test_smartart.py`, `app/tests/unit/test_charts.py`
* **テストデータ**: XML 文字列を直接与える。`SafeZipReader` は、`tests/helpers` に「メモリ上の辞書から ZIP を作る」ヘルパを用意して使う。
* **`test_smartart.py` のケース**:
  1. 3ノードのフラットな SmartArt から `ShapeParagraph` が3件、`level` がすべて0。
  2. **親子関係のある SmartArt で `level` が深さを反映する** (親0、子1)。
  3. **`type="pres"` のノードが除外される**。
  4. **`drawing*.xml` にも同じテキストがある場合に、二重に抽出されない** (data 側のみ採用)。
  5. `cxnLst` が無い場合に、すべて `level=0` で返る (例外にならない)。
  6. ノードの順序が `ptLst` の出現順を保つ。
  7. テキストが1件も無い SmartArt で `None` が返る。
  8. `shape_kind` が `SmartArt`。
* **`test_charts.py` のケース**:
  1. タイトル・系列2件・カテゴリ4件のグラフから、3段落が生成される。
  2. **`c:val` の数値が出力に含まれない**。
  3. カテゴリが最初の系列からのみ取られる (2つ目の系列の `c:cat` を見ない)。
  4. タイトルのみのグラフで1段落が返る。
  5. すべて空のグラフで `None` が返る。
  6. `shape_kind` が `グラフ`。

### 【実行コマンド】

* `pytest tests/unit/test_smartart.py tests/unit/test_charts.py -v`

### 【完了条件】

* 上記14ケースすべてが合格する。

### 【次タスクに進む前の停止条件】

* 単体テストが3回自己修正しても合格しない場合は停止して報告する。

---

## U003-T3: 図形ブロックの描画

### 【目的】

* `ShapeText` を Markdown の体裁に変換する (REQ-F-038)。3体裁 (`quote` / `heading` / `plain`) を実装する。

### 【作成・編集対象ファイル】

* `app/src/office2ragknowledge/render/shapes.py`
* `app/src/office2ragknowledge/render/excel_base.py` (U002-T3 で作ったスタブ `_render_shapes` を差し替える)

### 【参照すべき仕様箇所】

* `docs/P002-frontend-spec.md` §5.7 (既定の体裁・構成要素の表・代替の体裁・図形内の表・SmartArt の出力形・方眼紙モードにおける図形内の表の扱い)
* `docs/P001-requirement.md` REQ-F-035, REQ-F-038, REQ-F-039

### 【実装内容】

* `render_shape_block(shape: ShapeText, style: ShapeStyle) -> str` を実装する。
* **`quote` (既定)**:
  ```
  > **[図形: {種別}{位置情報}]**{グループ注記}
  > {1段落目}
  > {2段落目}
  ```
  * `{位置情報}`: `shape.anchor` があれば ` @ {anchor}` (Excel のみ)。
  * `{グループ注記}`: `shape.group_path` が空でなければ ` (グループ「{最も内側のグループ名}」内)`。複数階層ある場合は最も内側のものを用いる。
  * 各段落は `escape_line` を通してから `> ` を前置する。
  * SmartArt の場合、`level` に応じて `- ` を前置し、階層をインデントで表す (P002 §5.7 の SmartArt の出力形)。
* **`heading`**: `#### [図形] {種別}` の見出し + 通常段落 (引用にしない)。
* **`plain`**: マーカーなしの通常段落のみ。
* **図形内の表** (REQ-F-039): **引用ブロックの外に出す**。
  ```
  > **[図形: 四角形] 内の表**

  | A | B |
  | --- | --- |
  | 1 | 2 |
  ```
  * 表は GFM テーブルとして出力し、セルは `escape_cell` を通す。
  * `heading` / `plain` でも、表は同様に引用の外に置く。
* `render_shape_blocks(shapes, style) -> str`: 複数の図形ブロックを空行で区切って連結する。空なら空文字を返す。
* `excel_base.py` の `_render_shapes` を、この関数を呼ぶよう差し替える。**表計算モード・方眼紙モードの両方で、シートの章の末尾に同じ内容が出力される** (REQ-F-035)。
* `stats["shapes_with_text"]` を、レンダリングした図形の数で更新する。

### 【実装してはいけないこと】

* 引用ブロック内への GFM テーブルの埋め込み (`> | A | B |`)。P002 §5.7 の★ACCEPTED★のとおり、処理系によって表として解釈されないため。
* 方眼紙モードで図形内の表を出力しないこと。**REQ-F-063 が禁じているのはシートのセル配置を表として構造化することであり、図形内の表は対象外** (P002 §5.7 末尾)。

### 【Unit Test内容】

* **ファイル**: `app/tests/unit/test_render_shapes.py`
* **ケース**:
  1. `quote` で `> **[図形: テキストボックス]**` の見出し行と引用本文が出力される。
  2. **`anchor="B3"` で ` @ B3` が付く** (Excel の位置情報)。
  3. **`group_path=("業務フロー図",)` で ` (グループ「業務フロー図」内)` が付く**。
  4. `group_path` が2階層のとき、最も内側の名前が使われる。
  5. **複数段落が段落ごとの引用行になる** (1行に連結されない)。
  6. `heading` で `#### [図形] 四角形` と通常段落になる。
  7. `plain` でマーカーが付かない。
  8. **図形内の表が引用ブロックの外に出る** (`>` で始まる行に `|` が現れない)。
  9. 図形内の表の直前に `> **[図形: 四角形] 内の表**` の見出し行が出る。
  10. SmartArt の段落が `- ` 付きの箇条書きになり、`level` がインデントに反映される。
  11. 段落テキストの行頭 `#` がエスケープされる。
  12. `render_shape_blocks(())` が空文字を返す。
  13. 複数の図形が空行で区切られる。
  14. **表計算モードと方眼紙モードで、同じ `Sheet.shapes` から同一の図形ブロックが出力される** (REQ-F-035)。両レンダラの出力から図形部分を取り出して比較する。

### 【実行コマンド】

* `pytest tests/unit/test_render_shapes.py -v`

### 【完了条件】

* 上記14ケースすべてが合格する。
* U002 のレンダラのテストが引き続き全件合格する (スタブ差し替えによる退行がないこと)。

### 【次タスクに進む前の停止条件】

* 単体テストが3回自己修正しても合格しない場合は停止して報告する。

---

## U003-T4: Excelへの組み込み

### 【目的】

* Excel のシートと図形を対応付け、`Sheet.shapes` を埋める (REQ-F-035)。U002 で空タプルとしていた箇所を実装する。

### 【作成・編集対象ファイル】

* `app/src/office2ragknowledge/parsers/excel.py` (図形抽出の組み込み)

### 【参照すべき仕様箇所】

* `docs/P003-backend-spec.md` §7.6 (手順1〜6。`_rels` による解決、0起点→1起点の変換、`absoluteAnchor` の扱い)
* `docs/P001-requirement.md` REQ-F-035

### 【実装内容】

* `options.shapes` が偽なら、図形の抽出を行わず `shapes=()` のままとする。
* 手順 (P003 §7.6):
  1. `xl/workbook.xml` の `sheets/sheet` から `r:id` を得る (U002-T2 で実装済み)。
  2. `xl/_rels/workbook.xml.rels` でシート XML のパスを解決する (実装済み)。
  3. **`xl/worksheets/_rels/sheetN.xml.rels` から `drawing` 関係を探し、`xl/drawings/drawingM.xml` を解決する。** 関係の Type が `.../drawing` で終わるものを選ぶ。
  4. `drawingM.xml` の `xdr:twoCellAnchor` / `xdr:oneCellAnchor` / `xdr:absoluteAnchor` を走査する。
  5. **`xdr:from/xdr:col` と `xdr:from/xdr:row` は0起点**であるため、`col_to_letter(col+1)` と `row+1` で A1 形式のセル参照を作る。
  6. `xdr:absoluteAnchor` はセル位置を持たないため `anchor=None`。
* 各アンカー配下について `ShapeTextExtractor(EXCEL_DIALECT).extract(...)` を呼び、得た `ShapeText` に `dataclasses.replace(st, anchor=セル参照)` でアンカーを設定する。
* SmartArt (`dgm:relIds`) とグラフ (`c:chart`) を含むグラフィックフレームがあれば、U003-T2 の関数を呼ぶ。
* 図形の総数を `Sheet` 単位で集計し、**`docs/P002-frontend-spec.md` §7.3.3 で定義済みの `Sheet.shape_count` に格納する** (テキストを持たない図形も含む総数。P003 §8.3 が定めた「抽出器が別途カウンタを返す」事項の受け皿)。**設計書の変更は不要である** (※P011 の矛盾点 No.3 にもとづき、設計書の追記を求める旧記述を削除した)。
* シートが drawing を持たない場合は `shapes=()` とし、エラーにしない。

### 【実装してはいけないこと】

* ファイル名の数値 (`sheet1.xml` の `1`) でシートと drawing を対応付けること (P003 §7.6: 誤ったシートに図形が付く)。
* 打ち切り (`max_rows`) によって図形を除外すること (図形は打ち切りの影響を受けない。P003 §7.5)。

### 【Unit Test内容】

* **ファイル**: `app/tests/unit/test_excel_shapes.py`
* **テストデータ**: openpyxl は図形を作れないため、**生成した `.xlsx` の ZIP に `xl/drawings/drawing1.xml` と関係ファイルを注入する**ヘルパを `tests/helpers/make_office.py` に実装する (`add_drawing(path, sheet_index, drawing_xml)`)。
* **ケース**:
  1. 図形を持つシートで `Sheet.shapes` が1件以上になる。
  2. **`anchor` がセル参照 (`B3`) になる。0起点→1起点の変換が正しい** (`col=1, row=2` → `B3`)。
  3. `absoluteAnchor` の図形で `anchor=None`。
  4. **シートの並び順と `sheet1.xml` の番号が一致しないブックで、正しいシートに図形が付く** (`_rels` による解決の確認)。
  5. `options.shapes=False` で `shapes` が空タプル。
  6. drawing を持たないシートで `shapes` が空タプル、例外にならない。
  7. **`max_rows` で打ち切られたシートでも図形が抽出される** (打ち切りの影響を受けない)。
  8. **表計算モード・方眼紙モードの両方で、図形ブロックが章の末尾に出力される** (REQ-F-035)。レンダラを通した出力で確認する。
  9. `Sheet.shape_count` がテキストなしの図形も含めた総数になる。

### 【実行コマンド】

* `pytest tests/unit/test_excel_shapes.py -v`
* スプリント全体: `pytest tests/unit -v`

### 【完了条件】

* 上記9ケースすべてが合格する。
* **U003 の全タスクが `[x]` になっていること。**
* `pytest tests/unit` が全件合格 (U001・U002 の分も含む)。
* `ruff check src tests` と `mypy src` がエラー0件。
* `Sheet.shape_count` に、テキストを持たない図形も含めた総数が入っていること (設計書の変更は不要)。

### 【次タスクに進む前の停止条件】

* 単体テストが3回自己修正しても合格しない場合は停止して報告する。

---

## 重要

* 各タスクの範囲外のファイルは編集しないでください。
* タスクの実装後、実行したテストコマンドと結果を報告してください。
* タスクが完了したら、上記「タスク一覧」の該当行を `[x]` に更新してください。
* 全タスクが完了したら、`docs/P007-impl-direction.md` の本スプリント行を `[x]` に更新してください。
* Executor Stepの停止条件に該当しない限り、次のタスクに自動的に進んでください。
