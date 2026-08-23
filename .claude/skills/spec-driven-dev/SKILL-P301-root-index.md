---
name: root-index-dev
description: 仕様駆動でアプリケーションを開発するときに、プロジェクトリポジトリ全体のINDEX.mdを作成する。
---

# 全体INDEX作成

## 目的

* プロジェクトリポジトリ全体の目次となる `./INDEX.md` を作成する。各ソースツリーの `INDEX.md` と、`docs/` 配下の主要ドキュメントへのリンクをまとめ、主にAIが、人間も、リポジトリ全体を素早く把握できるようにする。
* ソースツリー自体は操作しない。あくまで各ソースツリーの `INDEX.md` をリンクするだけである。

## インプット文書

* `{ソースツリー}/INDEX.md` (P104で更新済みのもの)
* `docs/ArchitectureHandbook.md`
* `docs/ADR.md`
* `docs/P001-requirement.md` 〜 `docs/P009-acceptance-direction.md`

## アウトプット文書

* `./INDEX.md`

### アウトプットの記載内容

* INDEX形式(`SKILL.md` の「INDEX形式について」参照)にもとづき、次を一覧する。
  * 各ソースツリーの `INDEX.md` へのリンクと一言概要
  * `docs/` 配下の主要ドキュメント(`docs/P001-requirement.md` 〜 `docs/P302-deliver.md`、`docs/ArchitectureHandbook.md`、`docs/ADR.md`)へのリンクと一言概要
  * `docs/CR.md`(CR状態の台帳)/ `docs/P901-cr-direction/` / `docs/P903-cr-records/` (存在する場合)へのリンク

### アウトプットを参照する文書

* `docs/P302-deliver.md` (納品物まとめ)
* 人間がプロジェクト全体を把握する際の入口として使う。

## 動作

* 共通指示に加えて、以下の完了基準に従う。
* 品質基準: 各ソースツリーの`INDEX.md`が漏れなくリンクされている / `docs/`配下の主要ドキュメント(P001〜P009、ArchitectureHandbook、ADR)が漏れなくリンクされている / `docs/CR.md`等が存在する場合はリンクされている / 各リンク先のファイルが実在する(リンク切れが無い)。
* 本フェーズのアウトプット記載内容(上記3項目)は少数のため、各フェーズ共通指示の★FIXME★閾値のうち「4件以上」の基準は該当せず、「全体の半数以上」(=2件以上)の基準で判定する。1件のみの不足は「少数」分岐(不足箇所を補い★FIXME★を付す)として扱う。
