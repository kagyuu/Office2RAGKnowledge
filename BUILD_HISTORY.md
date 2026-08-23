# Build History

バージョンの正本は `app/pyproject.toml` の `project.version` である (`app/src/office2ragknowledge/__init__.py` の `__version__` が同じ値を持ち、`office2rag --version` で確認できる)。`VERSION` ファイルは作成していない (定義の二重化を避けるため)。

| Build ID | Version | Date/Time | Commit | Build Command | Test Command | Result | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BLD-20260824-0847 | 1.0.0 | 2026-08-24 08:47 (JST) | `0923b6d` (作業ツリー未コミット。下記注記参照) | `python -m build --wheel --sdist --outdir dist` (`app/` で実行) | `pytest tests -q` (`app/` で実行) | **PASS** | wheel 92.7 KB / sdist 126.7 KB を生成。クリーンな仮想環境に wheel を導入して `office2rag --version`・`convert`・`inspect` の動作を確認した |

## 注記

* **コミット**: 本ビルド時点で、リポジトリの唯一のコミットは `0923b6d` (Initial commit) であり、`app/` `docs/` `deploy/` などアプリケーション一式は**まだコミットされていない** (`git status` で untracked)。上記の Commit 欄はビルドを行った時点の HEAD を記録したものであり、ビルド対象のソースを指し示していない。この扱いは `docs/P302-deliver.md` 10章に未整備事項として記載している。
* **ビルド環境**: Windows 11 Pro (10.0.26200) / Python 3.14.2 / hatchling (隔離環境に自動導入) / pip 25.3。
* **テスト結果**: 539 passed, 1 skipped, 4 deselected (77.5 秒)。スキップは `test_runs_on_python_311` (本環境に Python 3.11 が無いため)。deselect されている4件は `-m perf` で別途実行する性能テスト。
* **Docker イメージ**: `deploy/Dockerfile` は作成済みだが、**本環境に Docker が無く (`docker: command not found`)、ビルド・起動の検証を行っていない**。したがって本表にビルド記録を持たない。
