# Moletta

**未知を掘り、作りたいものへ。**

Moletta（モレッタ）は、Codex と Claude Code で使う AI 開発ハーネスです。目的から必要な能力を洗い出し、未知の実現方法を探し、全体構成を比べ、実物の観測から判断します。小さく明確な変更には短い手順を使い、重要な判断では原文・計画・証拠を残します。

## 名前に込めた想い

**Moletta** は、モグラを意味する英語の **mole** を、親しみのある愛称に整えた造語です。

自分の知らないことを、作れるものの限界にしない。見えていない前提や可能性を探し、見つけた方法が目指す成果につながるかを実物で確かめる。そして、得た経験を次の開発へ残す。Moletta には、そうして一緒に作り上げる、小さな相棒への想いを込めています。

## 導入

macOS / Linux、Python 3.11 以上を使用します。特定のモデル、追加の Python パッケージ、外部 API、常駐サーバーは不要です。操作・調査・実装には、ホストが提供するツールと権限を使います。

```sh
git clone https://github.com/9uiLe/moletta.git
cd moletta
python3 scripts/install.py /absolute/path/to/project
```

既存プロジェクトの `.agents/skills/` と `.claude/skills/` に技能一式へのリンクを配置します。片方だけに導入する場合や、元の checkout から独立したコピーを置く場合は次のように指定します。

```sh
python3 scripts/install.py /absolute/path/to/project --host codex
python3 scripts/install.py /absolute/path/to/another-project --host claude --mode copy
```

全対象を配置前に確認し、既存項目を上書きしません。同じ checkout へのリンク導入は再実行できます。コピー導入では既存のリンクやコピーがあれば停止します。更新・削除する際は導入した技能だけを確認して取り除いてください。リンク導入は元の checkout の場所を維持します。

Claude Code はセッション専用プラグインとしても利用できます。

```sh
claude --plugin-dir /absolute/path/to/moletta
```

この導入方法の呼び出し名は `/moletta:moletta` です。プロジェクトへの導入と、どちらか一方を使います。

## 使う

普段の依頼に、ゴールと必須条件を添えます。手順や記録の操作は主担当 AI が行います。

- Codex: `$moletta このゴールに向けて調査・設計・実装・検証を進めてください。必須条件は…`
- Claude Code: `/moletta このゴールに向けて調査・設計・実装・検証を進めてください。必須条件は…`

技能の自動選択も許可されています。実際の選択はホストの設定と判断に依存します。

| 技能 | 責務 |
| --- | --- |
| `moletta` | 入口、作業規模に応じた経路の選択、再開 |
| `moletta-explore` | 原文からの能力抽出、未知の方式の調査 |
| `moletta-compare` | 全体構成の比較、条件付き採用、再考 |
| `moletta-verify` | 判断を変える実験、実物の観測、到達の判断 |
| `moletta-learn` | 限定した改善仮説と、変更前後の行動評価 |

すべての技能を順番に実行する必要はありません。明確で低リスクな小変更は、変更と相応の確認で完了します。未知の事実が選択を左右する場合だけ、探索や記録を追加します。

## 判断を支える仕組み

人の目的と必須制約を固定し、分解や実現方法は証拠に応じて更新します。各案は開始から成功までの構成として比較します。ある部品の高得点で、必須能力の欠落を相殺しません。

記録を使う作業では、編集可能な計画と、ツールが保存する観測・判定履歴を分けます。コマンド実行と、ブラウザー・画面・機器などホストの操作ツールによる観測を共通の手順で扱います。実験条件、対象の版、明示したローカル入力、結果の範囲を照合し、失敗や未確認事項から次の行動を選びます。[実行と再開](skills/moletta/references/workflow.md) に操作方法があります。

構造検査は、要求の意味上の網羅性、観測内容の真正性、全体最適を証明しません。原文からの別文脈レビューと、実物を読む判断を併用します。ホストの権限を強制するフックや、製品ごとの GUI 操作アダプターは含みません。

## 仕様・設計・開発

- [要件と保証範囲](docs/requirements.md)
- [アーキテクチャと責務](docs/architecture.md)
- [記録形式](skills/moletta/references/record-format.md)
- [行動評価と改善](docs/evaluation.md)
- [開発・検証・配布](docs/development.md)

ローカルと CI は同じ入口で、配布物、参照、公開評価コーパス、実行ツールのテストを確認します。

```sh
python3 scripts/validate.py
```

この検査はモデルを呼び出さず、技能による判断改善は採点しません。改善効果は、同条件の実行記録を独立に評価して確かめます。

## 出典

[pstack](https://github.com/cursor/plugins/tree/main/pstack) の必要な技能への振り分け、実物検証、振り返りから着想を得た独自実装です。NASA の要求追跡・全体設計・実証環境の区別、SEI の QAW・ATAM を設計上の問いに利用します。正式な準拠・認証を表すものではありません。[出典と適用範囲](skills/moletta/references/sources.md) を参照してください。

[MIT License](LICENSE) — Copyright (c) 2026 9uiLe.
