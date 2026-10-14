# Build History

バージョンの正本は `app/pyproject.toml` の `project.version` である (`app/src/office2ragknowledge/__init__.py` の `__version__` が同じ値を持ち、`office2rag --version` で確認できる)。`VERSION` ファイルは作成していない (定義の二重化を避けるため)。

| Build ID | Version | Date/Time | Commit | Build Command | Test Command | Result | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BLD-20260824-0847 | 1.0.0 | 2026-08-24 08:47 (JST) | `0923b6d` (作業ツリー未コミット。下記注記参照) | `python -m build --wheel --sdist --outdir dist` (`app/` で実行) | `pytest tests -q` (`app/` で実行) | **PASS** | wheel 92.7 KB / sdist 126.7 KB を生成。クリーンな仮想環境に wheel を導入して `office2rag --version`・`convert`・`inspect` の動作を確認した |
| BLD-20261014-0232 | 1.0.0 | 2026-10-14 02:32 (JST) | `81a04d2` (作業ツリー未コミット。※CR-001・CR-002 の PDF 対応を含む) | `uv build --wheel --sdist` (`app/` で実行) / `docker compose build` (`deploy/` で実行) | `pytest -q` (`app/` で実行) | **PASS** | wheel 120.0 KB / sdist 173.0 KB (P302 で開発時依存を `pypdf[crypto]` に是正した後の再ビルド)。クリーンな venv に wheel を導入して `--version`・`convert`・`inspect` を確認。**Docker イメージ (242 MB) のビルドと `docker compose run` での変換も確認** (前回は Docker 不在で未検証)。前回の 1.0.0 の生成物は `app/dist/archive-20260824/` に退避した。**版数は 1.0.0 のまま** (機能追加の版上げは人間の判断待ち。`docs/P302-deliver.md` 10章) |
| BLD-20261014-0750 | 1.0.0 | 2026-10-14 07:50 (JST) | `81a04d2` (作業ツリー未コミット。※CR-003: PDF ライブラリを pdfminer.six に差し替え) | `uv build --wheel --sdist` (`app/`) / `docker compose build` (`deploy/`) | `pytest -q` (`app/`) | **PASS** | wheel 119.9 KB / sdist 176.0 KB / Docker 203 MB (ラベル `MIT`)。**PyMuPDF を含まない**。前回 (BLD-20261014-0232) の生成物は `app/dist/archive-20261014-pymupdf/` に退避。版数は 1.0.0 のまま (`docs/P302-deliver.md` 10章) |
| **BLD-20261015-0019** | **1.1.0** | 2026-10-15 00:19 (JST) | 版数を上げたコミット (このビルド履歴を含むコミット) | `uv build --wheel --sdist` (`app/`) / `docker compose build` (`deploy/`) | `pytest -q` (`app/`) | **PASS** | 依頼者の指示で版数を 1.1.0 に上げた (PDF 入力の追加 = 後方互換な機能追加)。wheel 119.6 KB / sdist 174.1 KB / Docker `office2ragknowledge:1.1.0` 203 MB。706 passed。クリーンな venv で `--version` = `office2rag 1.1.0`、front matter の `converter` = `office2ragknowledge 1.1.0` を確認。1.0.0 (pdfminer.six 版) の生成物は `app/dist/archive-20261014-pdfminer-1.0.0/` に退避 |

## 注記

* **コミット**: 本ビルド時点で、リポジトリの唯一のコミットは `0923b6d` (Initial commit) であり、`app/` `docs/` `deploy/` などアプリケーション一式は**まだコミットされていない** (`git status` で untracked)。上記の Commit 欄はビルドを行った時点の HEAD を記録したものであり、ビルド対象のソースを指し示していない。この扱いは `docs/P302-deliver.md` 10章に未整備事項として記載している。
* **ビルド環境**: Windows 11 Pro (10.0.26200) / Python 3.14.2 / hatchling (隔離環境に自動導入) / pip 25.3。
* **テスト結果**: 539 passed, 1 skipped, 4 deselected (77.5 秒)。スキップは `test_runs_on_python_311` (本環境に Python 3.11 が無いため)。deselect されている4件は `-m perf` で別途実行する性能テスト。
* **Docker イメージ**: `deploy/Dockerfile` は作成済みだが、**本環境に Docker が無く (`docker: command not found`)、ビルド・起動の検証を行っていない**。したがって本表にビルド記録を持たない。

## 注記 (BLD-20261014-0232。※CR-001・CR-002)

* **ビルド環境**: WSL2 (Linux 5.15) / Python 3.12.12 / uv 0.x / Docker 29.7.2。
* **テスト結果**: 692 passed, 1 skipped, 4 deselected (`docs/test-records/20261014-0230-test-record.md`)。
* **同じ版数で中身が異なる生成物がある**: BLD-20260824-0847 と本ビルドはどちらも `1.0.0` だが、本ビルドは PDF 入力を含む。版数の扱いは `docs/P302-deliver.md` 10章で人間の判断を求めている。
* **ライセンス**: 本ビルドの wheel は依存に PyMuPDF (AGPL-3.0 / Artifex 商用のデュアルライセンス) を持ち、Docker イメージはそれを同梱する。イメージのラベルは `MIT AND AGPL-3.0-only` とした。

## 注記 (BLD-20261014-0750。※CR-003)

* 実行時依存は 20 件 (推移的) で、すべて MIT と両立するライセンス (受け入れテスト A007。`docs/test-records/20261014-0747-test-record.md`)。
* `1.0.0` の生成物が3種類ある (PDF 非対応 / PyMuPDF 版 / pdfminer.six 版)。版上げの判断は人間に委ねている。
