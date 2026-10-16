# Effectual Change

**既存ソフトウェアの変更における、不確実性を扱うためのAI意思決定フレームワーク**

Effectual Change は、エフェクチュエーションの5原則に着想を得て、AIコーディングエージェントが既存ソフトウェアに変更を加えるとき、「次に何をすべきか」を判断するためのフレームワークを検討するプロジェクトです。

> 現状理解が不完全なまま、正しい最終設計を最初から決めつけない。既存実装から手段と制約を発見し、変更の損失を限定し、人間と確認し、実験から学びながら、目標に到達する。

**ステータス：** 議論・検証中の仮説です。エフェクチュエーション理論の公式なソフトウェア開発手法でも、有効性が実証された方法論でもありません。

## 問題設定

現実のプロダクト開発では、新規開発よりも既存機能の追加・修正・改善・移行が頻繁に発生します。

たとえば以下の要求です。

- 「この画面に機能を追加したい」
- 「スクロールのカクツキを改善したい」
- 「このオンボーディングを特定の属性のユーザーにだけ見せたい」
- 「この画面をKotlin Multiplatform（KMP）に置き換えたい」

目標はある程度明確でも、実現経路は不明です。担当者自身が、仕様、暗黙の要件、依存関係、歴史的経緯、変更できない制約をすべて把握しているわけではありません。AIも同じです。

**このフレームワークの目的は、目標をAIが勝手に決め直すことではなく、目標への安全で合理的な到達経路を、調査・実験・合意によって選び直すことです。**

## 5原則の翻訳

| エフェクチュエーションの原則 | 既存ソフトウェア変更での問い |
| --- | --- |
| **手中の鳥 / Bird in Hand** | 既存のコード・動作・テスト・知識から、何がわかり、何を使えるか？ |
| **許容可能な損失 / Affordable Loss** | 何を維持し、どの範囲なら変更・実験してよいか？ |
| **クレイジーキルト / Crazy Quilt** | どの判断には誰の知識・確認・具体的な合意が必要か？ |
| **レモネード / Lemonade** | 調査・実験での予想外の発見は、設計をどう変えるか？ |
| **飛行機のパイロット / Pilot in the Plane** | 不確かな将来を予測しすぎず、現在の変更・検証・復旧をどう制御可能にするか？ |

詳しくは [原則の解釈と注意点](skills/effectual-change/references/principles.md) を参照してください。

## 意思決定ループ

1. **観測する：** 既存実装・動作を調べ、事実と仮説を分ける。
2. **境界を決める：** 維持すべき動作、許容できる変更、停止・復旧条件を整理する。
3. **次の行動を選ぶ：** 追加調査、最小実験、担当者への確認、設計見直し、実装、停止から選ぶ。
4. **検証と合意：** 計測値、スクリーンショット、動画、テスト結果などで確かめる。
5. **更新する：** 新しい発見を反映し、現時点で必要な設計に収束させる。

この番号は固定の工程順ではありません。状況に応じて繰り返します。

詳細は [意思決定ループ](skills/effectual-change/references/decision-loop.md) に記述しています。

## まず試す

[変更意思決定記録テンプレート](skills/effectual-change/assets/change-decision.md) に対象タスクを当てはめ、現状・未知・変更範囲を記録します。AIへの基本的な方針には [エージェント向け運用ガイド](skills/effectual-change/references/agent-playbook.md) を利用できます。


## Agent Skill

Claude Code と Codex で共有できる **Agent Skills形式のSkill** を提供します。入口は [SKILL.md](skills/effectual-change/SKILL.md)、詳細は `references/`、任意の記録テンプレートは `assets/` にあります。Skillとしてインストールするのは `skills/effectual-change/` ディレクトリだけで、npmパッケージや実行スクリプトは不要です。

### 使い方

既存のコードベースで変更を依頼するときに使用します。Claude Codeでは `/effectual-change`、Codexでは `$effectual-change` で明示的に呼び出せます。発見・自動起動は各製品の設定とSkillの説明文に依存します。

このSkillは「設計方針の相談のみ」で止めるものではありません。コード変更が依頼されている場合は既存コードとリスクを調べた上で、実装・検証まで進めます。担当者しか決められない仕様は、根拠とともに確認します。

### セキュリティ重視の導入（Git）

外部のnpm CLIを実行せず、内容を確認したGitコミットから導入する例です（macOS / Linux）。`REVIEWED_COMMIT_SHA`は実際に監査したコミットSHAに置き換えてください。**公開前のPrivateリポジトリではGitHubへのアクセス権が必要**です。

~~~bash
git clone https://github.com/9uiLe/effectual-change.git "$HOME/.local/share/effectual-change"
git -C "$HOME/.local/share/effectual-change" checkout --detach REVIEWED_COMMIT_SHA

# SKILL.md と参照資料を確認してから配置する
find "$HOME/.local/share/effectual-change/skills/effectual-change" -type f
~~~

ユーザー共通（全プロジェクト）に導入する場合、**既存の同名Skillがあれば両方のリンク作成を中止**します。通常の `ln -s SOURCE DEST` は、`DEST` が既存ディレクトリの場合、その中にリンクを作るため、事前に両方の配置先を検査します。壊れたシンボリックリンクも重複として扱います。

~~~bash
# Safe Skill symlink installation
set -eu

skill_source="$HOME/.local/share/effectual-change/skills/effectual-change"
claude_target="$HOME/.claude/skills/effectual-change"
codex_target="$HOME/.agents/skills/effectual-change"

if [ ! -f "$skill_source/SKILL.md" ]; then
  printf 'Skill not found: %s\n' "$skill_source" >&2
  exit 1
fi

mkdir -p "$HOME/.claude/skills" "$HOME/.agents/skills"

# Preflight BOTH targets before writing EITHER link.
for target in "$claude_target" "$codex_target"; do
  if [ -e "$target" ] || [ -L "$target" ]; then
    printf 'Skill already exists; refusing to modify: %s\n' "$target" >&2
    exit 1
  fi
done

ln -s "$skill_source" "$claude_target"
ln -s "$skill_source" "$codex_target"
~~~

既存の同名Skillを上書きしないでください。特定のプロジェクトだけに適用する場合は、そのプロジェクトの `.claude/skills/` と `.agents/skills/` に配置します。Gitによる更新時は `git fetch` の後に差分を確認し、承認したコミットへ切り替えてください。アンインストール時は該当するリンクのみ削除し、元のリポジトリを誤って削除しないでください。

### CLIによる簡易導入（任意）

[Vercel skills CLI](https://github.com/vercel-labs/skills) のインストール機能も利用できます。以下のコマンドは**外部CLIと依存コードを実行する**ため、組織のセキュリティポリシーに合わせてCLIの提供元・バージョン・依存を確認してください。未確認の最新版を無条件に実行せず、監査済みバージョンを明示してください。

~~~bash
# 監査したCLIのバージョン番号に置き換えてください
SKILLS_CLI_VERSION=REVIEWED_CLI_VERSION

# npm
npx "skills@$SKILLS_CLI_VERSION" add 9uiLe/effectual-change --skill effectual-change -a claude-code -a codex

# pnpm
pnpm dlx "skills@$SKILLS_CLI_VERSION" add 9uiLe/effectual-change --skill effectual-change -a claude-code -a codex
~~~

既定ではプロジェクト単位。ユーザー共通にする場合は `-g` を指定します。npmとpnpmのどちらかが一律に安全というわけではありません。導入後は各製品のSkill配置先に `SKILL.md` と参照資料が揃っているかを確認してください。これらのCLIによるインストールと実機での起動は、現時点で未検証です。

### Skillの検証

Python標準ライブラリのみで、Skillのfrontmatter・参照ファイル・自己完結性と、手動インストール時の既存Skillとの衝突防止を検査できます。frontmatterは汎用YAMLパーサーではなく、`name`と`description`をそれぞれ単一行・引用符なしの文字列に限定した形式として検証します。将来frontmatterの記法を拡張する場合はテストも更新してください。

~~~bash
python3 -m unittest discover -s tests -v
~~~

**検証できる範囲：** 限定的なfrontmatter文法、ファイル構造、リンクの静的整合性、および隔離環境でのリンク競合防止。汎用YAML仕様への準拠は保証しないため、公開前には[Agent Skills公式の検証方法](https://agentskills.io/specification#validation)（例：`skills-ref validate skills/effectual-change`）との照合も行ってください。Claude Code / Codexへの実インストール、発火判断、実務での意思決定品質は別途検証が必要です。進捗は [Issue #6](https://github.com/9uiLe/effectual-change/issues/6) で管理します。


## 大切な区別

- **観測事実 ≠ 正しい仕様：** コードがそう動いていても、意図された要件とは限りません。
- **予想外の発見 ≠ なんでも採用：** 発見は再現・検証して設計判断に利用します。
- **人間への提示 ≠ 合意：** 明示的な受け入れ条件や判断の記録が必要です。
- **将来を予測しすぎない ≠ 保守性を犠牲にする：** 現在のテスト可能性、低結合、段階移行、復旧可能性は重視します。
- **AIに任せる ≠ AIが全権を持つ：** セキュリティ、プライバシー、データ破壊、既存のレビュー・承認ルールを優先します。

## 評価・改善

現時点で効果は未検証です。[評価計画と未解決の論点](docs/evaluation.md) に従って、実際の変更タスクを使い、従来の開発プロセスとの差を調べていきます。反例も歓迎します。

## 理論的背景と出典

エフェクチュエーションは、起業家の意思決定についてSaras D. Sarasvathyが提唱した理論です。元の文脈では、手段、許容可能な損失、他者のコミットメント、偶然の活用、未来へのコントロールが重要です。本プロジェクトはその**独自の応用**です。

- [Sarasvathy (2001), *Causation and Effectuation*, Academy of Management Review](https://doi.org/10.5465/amr.2001.4378020)
- [Effectuation.org: The Five Principles of Effectuation](https://effectuation.org/the-five-principles-of-effectuation-detail)
- [Effectuation.org: Effectuation 101](https://effectuation.org/effectuation-101)

## ライセンス

未設定。公開前にライセンスを決定し、`LICENSE`を設置する必要があります。
