# Phase 2 — plugins カタログ重複検出の比較検証

このディレクトリは **Agent Skillの有効性を検証するための実験器具**です。架空のユースケース集ではありません。Effectual Changeの配布物（`skills/effectual-change/`）には含めません。

[Issue #13](https://github.com/9uiLe/effectual-change/issues/13) で実験の状況を管理します。

## 対象と固定条件

- 対象: [9uiLe/plugins](https://github.com/9uiLe/plugins)
- ベースコミット: `78953271ced181e79016a28245dbdd1ca59e9dd8`（`master`）
- 変更要求: READMEのプラグイン一覧で同じプラグインを二重掲載すると検証が成功する問題を修正する。
- 必須条件: 既存の正常なカタログ、本文中の通常のリンク、既存の不足・余分なカタログ登録の検出を維持し、回帰テストを追加する。
- 採点環境: Python 3.10以上、Bash、jq。Node、pnpm、Xcode、GitHub Actionsは不要。

初期状態では `scripts/verify-plugin-catalog.sh` がREADMEの表行を `sort -u` で重複排除してから検査しており、重複行を検知できません。**実際のスクリプトを最小の隔離fixtureで動かし、正常ケース・重複ケースが両方とも終了コード0になることを確認しています。** これはベースライン不具合の再現であって、Skillによる開発改善の検証ではありません。

## 同一条件のA/B試行

同じ製品・同じモデルの新しいセッションを2つ用意し、対象リポジトリを同じコミットから別々に複製します。既存の`CLAUDE.md`などは両条件でそのまま維持し、Effectual Change以外の設定差を作らないでください。

| 条件 | 操作 |
| --- | --- |
| A：Control | Effectual Changeを利用可能なSkillの一覧から除外してから、下記の共通課題を実行 |
| B：Treatment | Effectual Changeをインストールし、明示的に `/effectual-change`（Claude Code）または `$effectual-change`（Codex）を起動して共通課題を実行 |

### 共通課題文（両条件で同じ）

> このリポジトリのREADMEのプラグイン一覧で、同じプラグインへの行が重複しても検証が成功してしまいます。既存の正しい検証仕様と表以外の通常リンクの扱いを維持しながら、重複する場合に検証が失敗するようにしてください。回帰テストも追加し、実行した検証と残る未確認事項を報告してください。

- **双方とも実際にコードを変更できる同じ権限**を与え、権限・ツール・モデルを揃える。
- Aのグローバル環境にEffectual Changeが入ったままにならないよう確認する。
- セッションを分離し、先行する条件の差分・実装結果・評価用のテストを他方に渡さない。可能ならA/Bの実行順序をランダムにする。
- `plugins`本体の`master`にマージ・プッシュしない。各試行のファイル・ログを分けて保存する。
- まず1ペアをパイロット実験とし、その結果を一般的な優位性とは呼ばない。確認したい効果とコストが分かれば追加ペアを検討する。

### ワークスペース準備の例

```bash
git clone https://github.com/9uiLe/plugins.git /tmp/effectual-plugins-control
git -C /tmp/effectual-plugins-control checkout --detach 78953271ced181e79016a28245dbdd1ca59e9dd8

git clone https://github.com/9uiLe/plugins.git /tmp/effectual-plugins-treatment
git -C /tmp/effectual-plugins-treatment checkout --detach 78953271ced181e79016a28245dbdd1ca59e9dd8
```

この後、それぞれ**別のAgentセッション**で同じ課題文を与えます。Skillあり・なしを同じ会話で順番に試す方法は、先行実行の記憶が残るため比較条件として認めません。

## 独立したブラックボックス採点

`grade.py`は、変更後の実装を**別の一時ディレクトリへコピーして**テストします。採点コードはA/Bの作業ディレクトリへ事前配置しないでください。

```bash
python3 evaluation/plugin-catalog/grade.py \
  --candidate /tmp/effectual-plugins-control \
  --output /tmp/effectual-control-grade.json

python3 evaluation/plugin-catalog/grade.py \
  --candidate /tmp/effectual-plugins-treatment \
  --output /tmp/effectual-treatment-grade.json
```

採点対象は、正常系、重複行（同一行・異なるラベル・2番目のプラグイン）、本文中のリンクに対する誤検出、既存の不足・余分・リンク切れの検出です。

採点前に、それぞれで既存のテストも実行します。

```bash
bash /tmp/effectual-plugins-control/scripts/tests/verify-plugin-catalog.test.sh
bash /tmp/effectual-plugins-treatment/scripts/tests/verify-plugin-catalog.test.sh
```

**実行時の注意：** 採点器は候補ワークツリーからBashスクリプトを一時ディレクトリへコピーして実行します。Agentが編集したスクリプトは信頼できるとは限りません。認証情報のない、ネットワークを制限した隔離環境でのみ実行してください。採点器は対象ワークツリー自体を変更しません。

## 比較指標と記録

| 項目 | 比較方法 |
| --- | --- |
| 主指標：正しさ | `grade.py`のケースごとのPASS/FAILと既存テストの結果 |
| 既存コード理解 | 元の検査仕様とテスト、既存の非カタログリンクを確認した根拠 |
| 調査・確認の適切さ | 不要な質問、重要な未知の見落とし、価値の薄い長時間探索の有無 |
| 変更影響 | `git diff --stat`と差分による保守性・局所性の評価 |
| 検証の誠実さ | 実際に実施したテストと未検証事項の報告 |
| 効率（補助） | 経過時間、turn、ツール回数、tokens／利用料（取得できたデータのみ） |

採点の`passed/total`は**この検査セットの充足率**であり、Skill自体の優劣スコアではありません。単発での勝敗を統計的な改善効果とみなさず、エージェント出力のばらつき・事前知識・モデル差・自動起動の差を記録してください。

## 現状

- 対象の選定とベースコミットの固定：完了
- 隔離fixtureでの元の不具合の再現：完了
- 独立採点器の追加：PRによる提案
- **A/BのAgent実行：未実施**
- **Skillによる性能・品質の改善：未検証**

この環境には`claude`と`codex`のCLIがないため、比較結果を作りません。実行できたデータが得られた時点で、[Issue #13](https://github.com/9uiLe/effectual-change/issues/13)へ根拠とともに記録します。
