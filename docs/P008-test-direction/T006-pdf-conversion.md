あなたはExecutor(実装担当)です。実施後は、結果(PASS/FAIL/BLOCKED/NOT RUN)を記録したうえで、Executor Stepの「停止条件」に該当しない限り、自動的に次のテストタスクへ進んでください。

# 【テストID】T006 — PDF 変換の連携 ※CR-001・CR-002により追加

## 【目的】

* PDF が **形式判定 → `pdf/backend.py` → 構造木 / レイアウト → `PdfParser` → 中間表現 → `MarkdownRenderer` → ファイル出力**の連鎖を通して、P002 §5.12 の体裁どおりの Markdown になることを検証する。
* CLI (`convert` / `inspect`) から PDF を扱えることを検証する。

## 【参照テスト計画】

* `docs/P006-test-plan.md` §2.1 F-18〜F-21、§2.2 N-16・N-18、§3.4、§7.5
* `docs/P002-frontend-spec.md` §3.5, §5.3, §5.12, §9.1, §9.3

## 【対象モジュール】

* `detect.py` / `convert.py` / `inspection.py` / `pdf/*` / `parsers/pdf.py` / `render/markdown.py` / `render/frontmatter.py` / `writer.py` / `cli/main.py` / `cli/console.py`

## 【前提条件】全モジュールビルドが成功していること

* U006・U007 の単体テストが合格していること。

## 【使用するテストデータ】

* `tests/helpers/make_pdf.py` で生成する (リポジトリに PDF を置かない。P006 §3.4)。
  * **タグ付き報告書**: 日本語。`H1` → `P` (2行) → `H2` → 3段ネストの `L` → `Table` (見出し行 + 2行、`ColSpan=2` のセル1つ) → `Figure` (`/Alt` あり、内側に文字) → `H3` → 2ページ目にまたがる `P`。各ページに Artifact のヘッダー・フッター
  * **タグなし2段組み**: 3ページ。各ページの上端に文書名、下端に `- N -`。1ページ目に全幅の表題、その下が左右各5行の2段組み。2ページ目に枠付きの図 (枠内に2行)
  * **タグなし1ページ**: 上端・下端にテキストのある1ページ
  * 暗号化 (開くパスワードあり) / 所有者パスワードのみ + コピー禁止 / 破損 / 画像のみ (文字なし) のページを含む PDF

## 【事前準備】

* `tmp_path` に PDF を生成する。

## 【実行手順】

1. タグ付き報告書を `convert` (CLI) で `-o tmp_path/out` に変換し、出力を読む。
2. タグなし2段組みを既定と `--headers-footers` で変換し、出力を比べる。
3. 各 PDF を `convert_bytes` で2回変換し、`strip_front_matter` 後の本文が一致することを確認する。
4. `inspect` (人間可読・`--json`) に PDF を渡す。
5. 異常系の PDF をバッチ (正常な Word 1件と混在) で変換する。

## 【実行コマンド】

* `pytest tests/integration/test_pdf_conversion.py -v` (`app/` で実行)

## 【期待結果】

| # | 確認内容 | 期待 | 対象要求 |
| --- | --- | --- | --- |
| 1 | タグ付き: 出力ファイル | `{ステム}.md` が1つ。front matter に `source_format: "pdf"` と直後の `pdf_structure: "tagged"`、日本語の `title` | REQ-F-110, 120 |
| 2 | タグ付き: 見出し | `# ` (H1)・`## ` (H2)・`### ` (H3) の行が文書の順に現れる | REQ-F-112 |
| 3 | タグ付き: リスト | `- ` / `  - ` / `    - ` の3段のインデント | REQ-F-113 |
| 4 | タグ付き: 表 | GFM テーブル。`ColSpan` のセルの値が2列に複製され、全行の列数が等しい | REQ-F-114 |
| 5 | タグ付き: 図 | `![{代替テキスト}](画像は出力されていません)` と `> **[図形: 図]**` のブロック | REQ-F-117, 118 |
| 6 | タグ付き: ページをまたぐ段落 | 1つの段落 (途中に空行が無い) | REQ-F-115 |
| 7 | タグ付き: Artifact | ヘッダー・フッターの文字列が本文に無い。`stats.headers_footers_removed >= 1`、`multi_column_pages: 0` | REQ-F-123, 127 |
| 8 | タグなし: ヘッダー・フッター | 文書名と `- N -` が本文に無い。`headers_footers_removed: 6` | REQ-F-122 |
| 9 | タグなし: `--headers-footers` | 文書名とページ番号が本文に現れる。`headers_footers_removed: 0` | REQ-F-124 |
| 10 | タグなし: 段組み | 表題 → 左の段の5行 (1段落) → 右の段の5行 (1段落)。`multi_column_pages: 1` | REQ-F-125, 126 |
| 11 | タグなし: 図 | 枠内の2行が `> **[図形: 図]**` のブロックに入り、本文の段落に混ざらない | REQ-F-117 |
| 12 | タグなし: 記号 | 本文に `#` 見出し行・`- ` リスト行が1つも無い (front matter とタイトル行を除く) | REQ-F-116 |
| 13 | タグなし1ページ | 上端・下端のテキストが残る | REQ-F-122 |
| 14 | 冪等性 | 全 PDF で2回の変換結果 (front matter を除く) が一致 | REQ-NF-018, REQ-F-128 |
| 15 | inspect | 単位がページ数、`構造: {ファイル名}=タグ付き` / `タグなし` の行。`--json` に `"pdf_tagged": true/false`。暗号化 PDF は保護「あり」 | REQ-F-091 |
| 16 | 異常系 | 暗号化は種別 `パスワード保護` (E-005)、破損は種別 `破損ファイル` (E-007) として失敗一覧 (SCR-04。P002 §3.4) に出て、正常な Word は成功。終了コード 1 (※F004 により、失敗一覧がエラーコードではなく種別の表示名を出す仕様に合わせて修正) | REQ-F-121, REQ-F-006 |
| 17 | 警告 | 画像のみのページ → `ページ N からテキストを抽出できませんでした…`、コピー禁止 → 権限の警告が front matter の `warnings` に出る | REQ-F-119, 121 |
| 18 | 標準エラー | 破損 PDF の変換で PDF ライブラリ由来の出力 (※CR-003 で表現を一般化)が標準エラーに出ない (本アプリのエラー表示のみ) | REQ-NF-014, 020 |

## 【結果記録先】

* `docs/test-records/YYYYMMDD-HHMM-test-record.md`
