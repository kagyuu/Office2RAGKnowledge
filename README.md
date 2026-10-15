# Office2RAGKnowledge

Office 文書 (Word / Excel / PowerPoint) と PDF を、AI の RAG (Retrieval-Augmented Generation) パイプライン向けの Markdown に変換する CLI ツール兼 Python ライブラリです。

* 版数: 1.1.0
* ライセンス: MIT
* 動作環境: Python 3.11 以上 (Windows / Linux / macOS)。LibreOffice や OCR エンジンなどの外部バイナリは不要です。

## 概要

| 入力 | 拡張子 | 出力 |
| --- | --- | --- |
| Word | `.docx` `.docm` | `{名前}.md` |
| PowerPoint | `.pptx` `.pptm` | `{名前}.md` (スライドごとの章 + 発表者ノート) |
| Excel | `.xlsx` `.xlsm` | `{名前}.table.md` と `{名前}.grid.md` の **2つ** |
| PDF | `.pdf` | `{名前}.md` |

旧バイナリ形式 (`.doc` `.xls` `.ppt`) には対応していません。マクロ有効形式はマクロを実行せず、本文だけを読み取ります。

出力する Markdown には、元ファイル名・形式・変換日時などを記した front matter (YAML) が付きます。

## 目的

RAG では、文書をチャンクに分割してベクトル DB に格納し、質問に近いチャンクを検索して LLM に渡します。このとき検索の精度は、**元の文書の構造がどれだけ保たれているか**に大きく左右されます。見出しが失われれば章の区切りでチャンクを切れず、表が崩れれば行と列の対応が失われます。

本ツールの出力の読み手は人間ではなく、チャンク分割器と埋め込みモデルです。そのため見た目の再現は行わず、次の**構造**を保つことを目的としています。

* 見出し階層・箇条書き・表
* シート / スライド / ページの境界
* オートシェープ・テキストボックス・SmartArt の中の文言

### オートシェープ内のテキストを取りこぼしません

日本のビジネス文書では、要点・注意事項・構成図の説明がテキストボックスや図形の中に書かれていることがよくあります。多くの変換ツールはこれを落としますが、本ツールは OOXML を直接走査して回収します。グループ化された図形も入れ子の深さによらず再帰的に辿ります。

**OCR は行いません。** 抽出するのはファイル内にテキストとして格納されている文字だけです (スキャン PDF の画像ページからは文字を取り出さず、front matter に警告を記録します)。

### Excel は「表」と「方眼紙」の両方で出力します

Excel には、正規の表計算として使う用法と、セルを方眼紙のように使って文書を組む用法 (いわゆる Excel 方眼紙) があります。適した Markdown 表現はまったく異なりますが、**本ツールはどちらであるかを判別せず、両方を常に出力します。** 判別を誤ると情報が失われ、しかも失われたことを後段で検知できないためです。どちらを採用するかは RAG パイプライン側で選べます。

| 出力 | 内容 |
| --- | --- |
| `{名前}.table.md` | シートごとの章 + Markdown テーブル (表計算モード。結合セルの値は各セルに複製) |
| `{名前}.grid.md` | シートごとの章 + セルを連結した本文 (方眼紙モード) |

### PDF

* **タグ付き PDF** (アクセシビリティ対応) は、論理構造をもとに見出し・箇条書き・表に変換します。
* **タグの無い PDF** は、見出しを推定せずに段落の並びとして出力します。ページ上下に繰り返し現れるヘッダー・フッターを除き、段組みは段ごとの読み順に並べ替えます。
* front matter の `pdf_structure` (`tagged` / `untagged`) で、どちらの方法で変換したかが判ります。

### その他の性質

* **決定的**: 同じ入力と同じオプションからは、`converted_at` (変換日時) を除いて同一の Markdown を出力します。差分検知や再インデックスの判断に使えます。
* **外部通信を行いません**: 変換処理はネットワークに一切アクセスしません。
* **文書の内容をログに出しません**: ログに記録するのはパス・件数・シート名・エラーコードだけです。

## インストール

本ツールは PyPI には公開していません。ソースから wheel を作って導入するか、Docker イメージを作って使います。

* [インターネットにつながる環境](#インターネットにつながる環境)
* [閉域環境 (Sonatype Nexus を使う)](#閉域環境-sonatype-nexus-を使う)

### インターネットにつながる環境

#### 方法 A: pip で導入する

```bash
# GitHub から直接導入する (パッケージ本体は app/ 配下にある)
pip install "git+https://github.com/kagyuu/Office2RAGKnowledge.git#subdirectory=app"

# または、取得したソースから導入する
git clone https://github.com/kagyuu/Office2RAGKnowledge.git
cd Office2RAGKnowledge/app
pip install .
```

仮想環境 (venv) の中に導入することを勧めます。

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install "git+https://github.com/kagyuu/Office2RAGKnowledge.git#subdirectory=app"
office2rag --version
```

#### 方法 B: wheel を作って配る

複数の端末に配る場合は、wheel を1度作って配ると便利です。

```bash
cd Office2RAGKnowledge/app
pip install build
python -m build --wheel            # uv を使う場合: uv build --wheel
# → dist/office2ragknowledge-1.1.0-py3-none-any.whl

# 導入する側
pip install office2ragknowledge-1.1.0-py3-none-any.whl
```

wheel は純 Python (`py3-none-any`) なので、OS を問わず同じファイルを使えます。

#### 方法 C: Docker で使う

```bash
cd Office2RAGKnowledge/deploy
docker compose build               # → イメージ office2ragknowledge:1.1.0
docker compose run --rm convert --version
```

本ツールは常駐サービスではないため、`docker compose up` ではなく `docker compose run --rm` で都度実行します (使い方は[後述](#docker-で使う))。

### 閉域環境 (Sonatype Nexus を使う)

インターネットに出られない環境では、社内の Sonatype Nexus Repository を経由して依存パッケージとベースイメージを取得します。ここでは次の構成を前提にします (リポジトリ名は例です。自組織の名前に読み替えてください)。

| Nexus のリポジトリ | 種類 | 用途 |
| --- | --- | --- |
| `pypi-proxy` | PyPI (proxy) | PyPI (`https://pypi.org/`) の代理。依存ライブラリを取得する |
| `pypi-hosted` | PyPI (hosted) | 本ツールの wheel を置く |
| `pypi-group` | PyPI (group) | 上の2つをまとめた参照用の入口 |
| `docker-proxy` | Docker (proxy) | Docker Hub の代理。ベースイメージ `python:3.12-slim` を取得する |
| `docker-hosted` | Docker (hosted) | 本ツールのイメージを置く |

以下では Nexus の URL を `https://nexus.example.local` とします。

> **補足**: Nexus 自体もインターネットに出られない完全な閉域の場合は、インターネット側の端末で `pip download` した wheel 一式を `pypi-hosted` へ登録しておけば、以降の手順はそのまま使えます ([付録](#付録-nexus-がインターネットに出られない場合))。

#### 1. 必要なパッケージ

`pypi-proxy` (または `pypi-hosted`) から、次のパッケージが取得できる必要があります。

| 区分 | パッケージ |
| --- | --- |
| 実行時の依存 | `openpyxl` `python-docx` `python-pptx` `lxml` `typer` `rich` `pdfminer.six` (と、これらの推移的依存) |
| wheel のビルド時のみ | `hatchling` (`python -m build` を使う場合は `build` も) |

`lxml` はプラットフォームごとのバイナリ wheel を持つため、導入先の OS・CPU・Python 版に合った wheel が取得できることを確認してください。

#### 2. pip の参照先を Nexus にする

`pip.conf` (Linux / macOS: `~/.config/pip/pip.conf`、Windows: `%APPDATA%\pip\pip.ini`) に次を書きます。

```ini
[global]
index-url = https://nexus.example.local/repository/pypi-group/simple
trusted-host = nexus.example.local
```

* `trusted-host` は、Nexus が社内 CA の証明書を使っていて検証できない場合にだけ書きます。社内 CA を信頼させられるなら `cert = /path/to/corp-ca.pem` を使う方が安全です。
* 認証が必要な Nexus の場合は、URL に資格情報を埋め込まず、`~/.netrc` (Windows: `%USERPROFILE%\_netrc`) に書くか、keyring を使ってください。

```text
machine nexus.example.local
login <ユーザー名>
password <パスワード>
```

環境変数で一時的に指定することもできます。

```bash
export PIP_INDEX_URL=https://nexus.example.local/repository/pypi-group/simple
```

#### 3. 本ツールの wheel を Nexus に登録する (管理者が1度だけ)

ソースを閉域内に持ち込み、wheel を作って `pypi-hosted` に登録します。ビルドに使う `hatchling` も手順 2 の設定で Nexus から取得されます。

```bash
cd Office2RAGKnowledge/app
pip install build twine
python -m build --wheel --sdist
# → dist/office2ragknowledge-1.1.0-py3-none-any.whl
#    dist/office2ragknowledge-1.1.0.tar.gz

twine upload \
  --repository-url https://nexus.example.local/repository/pypi-hosted/ \
  dist/*
```

`twine` はユーザー名とパスワードを対話的に尋ねます。`~/.pypirc` に登録先を書いておくこともできます。

```ini
[distutils]
index-servers = nexus

[nexus]
repository = https://nexus.example.local/repository/pypi-hosted/
username = <ユーザー名>
```

```bash
twine upload -r nexus dist/*
```

#### 4. 利用者の端末に導入する

手順 2 の設定をした端末で、通常どおり導入します。

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install office2ragknowledge==1.1.0
office2rag --version
```

wheel を Nexus に登録せず、ファイルとして配る運用もできます。その場合も依存ライブラリは Nexus から取得されます。

```bash
pip install ./office2ragknowledge-1.1.0-py3-none-any.whl
```

#### 5. Docker イメージを閉域内で作る

`deploy/Dockerfile` はベースイメージに `python:3.12-slim` を使い、ビルド中に `pip install` を実行します。閉域内でビルドするには、この2つを Nexus 経由にします。

**(1) ベースイメージを Nexus から取得する。** Docker デーモンの設定 (`/etc/docker/daemon.json`) でミラーを指定します。`docker-proxy` には Nexus 側で HTTP(S) のコネクタ (例: ポート `8082`) を割り当てておきます。

```json
{
  "registry-mirrors": ["https://nexus.example.local:8082"]
}
```

```bash
sudo systemctl restart docker
docker login nexus.example.local:8082   # 匿名アクセスを許していない場合
docker pull python:3.12-slim
```

`registry-mirrors` を使えない場合は、Nexus から取得したイメージに元の名前を付け直します。

```bash
docker pull nexus.example.local:8082/library/python:3.12-slim
docker tag  nexus.example.local:8082/library/python:3.12-slim python:3.12-slim
```

**(2) ビルド中の pip を Nexus に向ける。** `Dockerfile` を変更せずに、環境変数 `PIP_INDEX_URL` をビルド引数として渡します。pip は `PIP_` で始まる環境変数を設定として読みます。`deploy/compose.yml` の `build.args` に追加するか、`docker build` で直接渡します。

```bash
# リポジトリのルートで実行する
docker build -f deploy/Dockerfile \
  --build-arg UID=$(id -u) \
  --build-arg PIP_INDEX_URL=https://nexus.example.local/repository/pypi-group/simple \
  --build-arg PIP_TRUSTED_HOST=nexus.example.local \
  -t office2ragknowledge:1.1.0 .
```

> **注意**: ビルド引数を `ARG` として宣言していない場合、`docker build` は引数を受け取っても `RUN` に渡しません。`deploy/Dockerfile` の両方のステージの `FROM` の直後に次の2行を加えてください。資格情報を含む URL をビルド引数に渡すとイメージの履歴に残るため、認証が必要な場合は BuildKit のシークレット (`--secret`) で `pip.conf` を渡してください。
>
> ```dockerfile
> ARG PIP_INDEX_URL
> ARG PIP_TRUSTED_HOST
> ```

**(3) 作ったイメージを Nexus に登録して配る。** `docker-hosted` に割り当てたコネクタ (例: ポート `8083`) へ push します。

```bash
docker tag  office2ragknowledge:1.1.0 nexus.example.local:8083/office2ragknowledge:1.1.0
docker login nexus.example.local:8083
docker push nexus.example.local:8083/office2ragknowledge:1.1.0

# 利用者の端末
docker pull nexus.example.local:8083/office2ragknowledge:1.1.0
```

変換の実行時にはネットワークを使わないため、`deploy/compose.yml` は `network_mode: none` で動かす設定になっています。

#### 付録: Nexus がインターネットに出られない場合

`pypi-proxy` が PyPI に到達できない場合は、インターネット側の端末で依存一式を wheel として集め、閉域へ持ち込んで `pypi-hosted` に登録します。**導入先と同じ OS・CPU・Python 版を指定して**集めてください (`lxml` がプラットフォーム依存のため)。

```bash
# インターネット側の端末 (例: 導入先が Linux x86_64 / Python 3.12 の場合)
pip download office2ragknowledge-1.1.0-py3-none-any.whl hatchling \
  --dest wheelhouse \
  --only-binary=:all: \
  --platform manylinux2014_x86_64 --python-version 3.12

# 閉域側 (wheelhouse を持ち込んだ後)
twine upload --repository-url https://nexus.example.local/repository/pypi-hosted/ wheelhouse/*
```

Windows 端末向けには `--platform win_amd64` で同様に集めます。ベースイメージも同様に、インターネット側で `docker pull python:3.12-slim` → `docker save` したものを閉域で `docker load` し、`docker-hosted` へ push してください。

## 使い方

### 基本

```bash
# 1ファイルを変換する (出力は入力と同じディレクトリ)
office2rag convert ./会議資料.pptx

# ディレクトリを再帰的に変換して ./out に出力する
office2rag convert ./docs -r -o ./out

# 変換せずに構造 (シート数・スライド数・図形数・表領域数) を確認する
office2rag inspect ./docs -r
office2rag inspect ./売上.xlsx --json

# 標準出力に書き出して、別のツールにパイプで渡す (対象1件のときのみ)
office2rag convert ./規程.docx --stdout | your-rag-tool

# Excel を --stdout で出す場合は、出力するモードを1つに絞る
office2rag convert ./売上.xlsx --stdout --excel-modes table

# バージョンと依存ライブラリの版を表示する
office2rag --version
```

`-o` を指定すると、入力のサブディレクトリ構成は再現されず、すべての出力が指定したディレクトリの直下に書き出されます (`-o` を省略すると、各入力ファイルと同じディレクトリに出力します)。出力先に同名のファイルがある場合は、既定では変換を飛ばします (`--on-exists overwrite` で上書き)。

### 主なオプション

| オプション | 既定 | 説明 |
| --- | --- | --- |
| `-o, --output DIR` | 入力と同じ場所 | 出力先ディレクトリ |
| `-r, --recursive` | 無効 | ディレクトリを再帰的に探索する |
| `--on-exists {skip,overwrite,fail}` | `skip` | 出力先に同名ファイルがある場合の扱い |
| `--stdout` | 無効 | 標準出力に書き出す (対象1件のみ。`-o` とは併用不可) |
| `--excel-modes {both,table,grid}` | `both` | Excel で生成する Markdown の種類 |
| `--grid-separator TEXT` | なし | 方眼紙モードで同じ行のセルを連結するときの区切り文字 |
| `--table-regions / --no-table-regions` | 有効 | 1シート内の複数の表を分割して検出する |
| `--formulas / --no-formulas` | 無効 | 数式を値と併記する (表計算モードのみ) |
| `--max-rows N` | `10000` | 1シートあたりの出力行数の上限 (`0` で無制限) |
| `--shapes / --no-shapes` | 有効 | 図形内のテキストを抽出する (PDF では図の中の文字) |
| `--shape-style {quote,heading,plain}` | `quote` | 図形ブロックの体裁 |
| `--notes / --no-notes` | 有効 | PowerPoint の発表者ノートを出力する |
| `--headers-footers` | 無効 | Word のヘッダー・フッターを出力する / PDF のヘッダー・フッターを除去しない |
| `--comments` | 無効 | Word のコメントを出力する |
| `--include-hidden` | 無効 | 非表示のシート・スライドなども出力する |
| `--images {none,extract}` | `none` | 画像バイナリを書き出す |
| `--front-matter / --no-front-matter` | 有効 | front matter を出力する |
| `-j, --jobs N` | CPU コア数 | 並列ワーカー数 (1〜64) |
| `-c, --config FILE` | 自動探索 | 設定ファイル (TOML) |
| `-q, --quiet` / `-v, --verbose` | - | 進捗表示を抑止する / 詳細ログを出す |
| `--log-file FILE` / `--log-format {text,json}` | - / `text` | ログの出力先と形式 |

すべてのオプションは `office2rag convert --help` で確認できます。

### 設定ファイル

よく使うオプションは `office2rag.toml` に書いておけます。カレントディレクトリから上位に向かって自動で探索するほか、`-c` で明示的に指定できます。優先順位は「コマンドライン引数 > 設定ファイル > 既定値」です。

```toml
[convert]
output = "./out"
recursive = true
on_exists = "skip"
shapes = true
shape_style = "quote"
notes = true
headers_footers = false
jobs = 4

[excel]
modes = "both"           # both | table | grid
grid_separator = ""
table_regions = true
max_rows = 10000

[log]
level = "info"           # quiet | info | verbose
format = "text"          # text | json
```

綴り間違いが黙って無視されないよう、未知のキーやテーブルが含まれる場合はエラーになります。

### 終了コード

| コード | 意味 |
| --- | --- |
| `0` | 全対象が成功またはスキップした (`inspect` `--help` `--version` の正常終了を含む) |
| `1` | 1件以上のファイルの変換に失敗した (他のファイルは変換を続ける) |
| `2` | 引数の誤り・入力パスの不存在・対象0件・設定エラーなどで、1件も処理しなかった |

パスワード付きのファイルや壊れたファイルは、そのファイルだけを失敗として記録し、残りの変換を続けます。

### Docker で使う

`deploy/compose.yml` は、入力ディレクトリを `/work/in` (読み取り専用)、出力ディレクトリを `/work/out` にマウントします。マウント元は環境変数で切り替えられます。

```bash
cd deploy
INPUT_DIR=/path/to/docs OUTPUT_DIR=/path/to/out \
  docker compose run --rm convert convert /work/in -r -o /work/out

# 設定ファイルを使う場合
CONFIG_FILE=/path/to/office2rag.toml INPUT_DIR=/path/to/docs OUTPUT_DIR=/path/to/out \
  docker compose run --rm convert convert /work/in -o /work/out

# 構造の確認
INPUT_DIR=/path/to/docs docker compose run --rm convert inspect /work/in -r
```

出力ファイルの所有者はビルド時の環境変数 `UID` (未設定なら `1000`) になります。ホストの利用者に揃えるには `UID=$(id -u) docker compose build` でビルドしてください。

### ライブラリとして使う

```python
from office2ragknowledge import convert_file, ConvertOptions

result = convert_file("会議資料.pptx")
print(result.markdown)

# Excel は既定で2つの出力を返す
result = convert_file("売上.xlsx")
for output in result.outputs:
    print(output.mode, output.filename_suffix, len(output.markdown))
```

Excel を渡した場合、`result.markdown` は `ValueError` を送出します。表計算モードだけを黙って受け取り、方眼紙モードの出力を取りこぼす事故を防ぐためです。複数の出力は `outputs` から取り出してください。

## 開発者向け

開発環境の作り方、テストと品質ゲートの実行方法、設計の要点は [CLAUDE.md](./CLAUDE.md) と [docs/ArchitectureHandbook.md](./docs/ArchitectureHandbook.md) を参照してください。モジュールの一覧は [app/INDEX.md](./app/INDEX.md)、設計文書の一覧は [INDEX.md](./INDEX.md) にあります。

```bash
cd app
pip install -e ".[dev]"
pytest -q
ruff check src tests && ruff format --check src tests && mypy src
```

## ライセンス

[MIT](./LICENSE) © 2026 HONDOH Atsushi

実行時の依存ライブラリは、推移的な依存を含めてすべて MIT と両立するライセンス (MIT・BSD・Apache-2.0 など) に限っています。PDF の読み取りには pdfminer.six (MIT) を使っています。
