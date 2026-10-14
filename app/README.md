# office2ragknowledge

Office 文書 (Word / Excel / PowerPoint) と PDF を、AI の RAG パイプライン向けの Markdown に変換します。

出力の読み手は人間ではなくチャンク分割器と埋め込みモデルです。そのため見た目の再現は行わず、**構造** (見出し階層・表・シート/スライド境界・**図形内の文言**) を保つことを目的としています。

## 特徴

### オートシェープ内のテキストを取りこぼしません

日本のビジネス文書では、要点・注意事項・構成図の説明がテキストボックスや図形の中に書かれていることが多くあります。多くの変換ツールはこれを落としますが、本ツールは OOXML を直接走査して回収します。グループ化された図形も入れ子の深さによらず再帰的に辿り、SmartArt にも対応します。

**OCR は行いません。** 抽出するのはファイル内にテキストとして格納されているものだけです。

### Excel の二面性に、判別なしで両対応します

Excel には「正規の表計算として使う」用法と、「セルを方眼紙のように使って文書を組む」用法があります。適切な Markdown 表現はまったく異なりますが、**本ツールはどちらであるかを判別しません。両方の Markdown を常に出力します。**

判別を誤ると情報が失われ、しかも失われたことを後段から検知できないためです。どちらを採用するかは RAG パイプライン側で選べます。

| 出力 | 内容 |
| --- | --- |
| `{名前}.table.md` | シートごとの章 + Markdown テーブル (表計算モード) |
| `{名前}.grid.md` | シートごとの章 + セルを連結した本文 (方眼紙モード) |

### PDF にも対応します

* **アクセシビリティ対応 (タグ付き) の PDF** は、論理構造をもとに見出し (`#` `##` `###`)・箇条書き (入れ子)・表に変換します。
* **論理構造の無い PDF** は、見出しを推定せずにテキストを段落の並びとして出力します。ページ上下に繰り返し現れるヘッダー・フッター (文書名・ページ番号) を除き、2段組み・3段組みは段ごとの読み順に並べ替えます。
* 図や表の中の文字は、Office の図形テキストと同じ形 (`> **[図形: 図]**`) で出力します。
* 画像だけのページ (スキャン PDF) からは文字を取り出しません (OCR は行いません。front matter に警告を記録します)。
* front matter の `pdf_structure` (`tagged` / `untagged`) で、どちらの方法で変換したかが判ります。

> **ライセンスについて**: 本パッケージは MIT です。PDF の読み取りには **pdfminer.six (MIT)** を使っており、実行時依存はすべて MIT と両立するライセンス (MIT・BSD・Apache-2.0 等) です。

## インストール

```bash
pip install office2ragknowledge
```

外部バイナリ (LibreOffice や OCR エンジン) は不要です。Python 3.11 以上で動作します。

## 使い方

```bash
# ディレクトリを再帰的に変換
office2rag convert ./docs -r -o ./out

# 変換せずに構造を確認
office2rag inspect ./会議資料.pptx

# パイプ処理
office2rag convert ./規程.docx --stdout | your-rag-tool
```

### 主なオプション

| オプション | 既定 | 説明 |
| --- | --- | --- |
| `-o, --output DIR` | 入力と同階層 | 出力先ディレクトリ |
| `-r, --recursive` | 無効 | ディレクトリを再帰探索 |
| `--on-exists {skip,overwrite,fail}` | `skip` | 出力先に同名ファイルがある場合 |
| `--excel-modes {both,table,grid}` | `both` | Excel で生成する Markdown の種類 |
| `--grid-separator TEXT` | なし | 方眼紙モードでセルを連結する際の区切り文字 |
| `--table-regions / --no-table-regions` | 有効 | 1シート内の複数の表を分割して検出 |
| `--shapes / --no-shapes` | 有効 | オートシェープ内テキストの抽出 (PDF では図の中の文字) |
| `--headers-footers` | 無効 | Word のヘッダー・フッターを出力 / PDF のヘッダー・フッターを除去しない |
| `-j, --jobs N` | CPU コア数 | 並列ワーカー数 |

すべてのオプションは `office2rag convert --help` を参照してください。設定ファイル `office2rag.toml` でも指定できます。

## ライブラリとして使う

```python
from office2ragknowledge import convert_file, ConvertOptions

result = convert_file("会議資料.pptx")
print(result.markdown)

# Excel は既定で2つの出力を返す
result = convert_file("売上.xlsx")
for output in result.outputs:
    print(output.mode, output.filename_suffix, len(output.markdown))
```

Excel を渡した場合、`result.markdown` は `ValueError` を送出します。表計算モードだけを黙って受け取り、方眼紙モードの出力を取りこぼす事故を防ぐためです。複数出力を扱う場合は `outputs` を参照してください。

## ライセンス

MIT © 2026 HONDOH Atsushi
